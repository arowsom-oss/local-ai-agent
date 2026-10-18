"""Offline plain assertions: scripted model, fake files/approvals, blocked sockets."""
import socket
import threading
import types
from unittest.mock import patch
import artifacts
import workspace_documents as d
from task_progress import TurnEvidence
from test_workspace_documents import fixture, save_new
import test_browser_search as h


def saved(text='School notes\nMy human addition.'):
    w, f = fixture(); save_new(w, text); w.read(1, 0)
    return w, f, next(iter(f.data))[0]


def refused(action):
    try: action()
    except (ValueError, TypeError): return
    raise AssertionError('operation should have been refused')


def edit_call(**changes):
    args = {'document': 1, 'find': '', 'replacement': '\nNew line.'}; args.update(changes)
    return h.tool_call('document_edit', args)


def run(w, rounds, decide=lambda name, args: True, stop=None, resume=False):
    replies = [types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=calls, content='Done' if not calls else ''))
               for calls in rounds]
    messages = []; popups = []; logs = []; events = []
    def approval(name, args): popups.append((name, args.copy())); return decide(name, args)
    with patch.object(d, '_workspace', w), patch.object(h.core, 'chat', side_effect=replies) as model, \
         patch.object(h.core, 'compact', return_value=False), patch.object(h.core, 'audit'):
        answer, _ = h.core.run_turn(messages, 'Edit this saved document', approval, log=logs.append,
            stop_event=stop, resume=resume, on_progress=lambda **event: events.append(event))
    return answer, messages, popups, events, model.call_count, logs


def test_append_preserves_human_text_and_creates_only_a_proposal():
    w, f, key = saved('School notes\nMy human addition.\nCafé ✓')
    before = dict(f.data); p = w.prepare_edit(1, '', '\nNew line.')
    assert f.data == before and p['preview']['version'] == 1
    assert p['preview']['after'] == 'School notes\nMy human addition.\nCafé ✓\nNew line.'
    w.commit(p['token'])
    assert f.data[key, 1] == before[key, 1] and f.data[key, 2].endswith(b'\nNew line.')


def test_replacement_is_literal_and_preserves_all_other_bytes():
    w, f, key = saved('List\n[red].*\nKeep this line.')
    w.commit(w.prepare_edit(1, '[red].*', r'blue\1 $value')['token'])
    assert f.data[key, 2].decode() == 'List\nblue\\1 $value\nKeep this line.'
    assert f.data[key, 1].decode() == 'List\n[red].*\nKeep this line.'


def test_missing_duplicate_and_overlapping_matches_are_refused():
    for text, find in (('two red red', 'red'), ('aaa', 'aa'), ('hello', 'absent')):
        w, f, _ = saved(text); count = len(artifacts.store.items())
        refused(lambda: w.prepare_edit(1, find, 'blue'))
        assert len(f.data) == 1 and not w.pending and len(artifacts.store.items()) == count


def test_fragments_final_size_empty_result_and_noop_are_bounded():
    for find, replacement in (('', ''), ('School', 'School'), ('', 'x'*8001), ('', '\r'),
                              ('', '\x00'), (None, 'x'), ('School notes\nMy human addition.', '')):
        w, f, _ = saved(); refused(lambda: w.prepare_edit(1, find, replacement)); assert len(f.data) == 1
    w, f, key = saved('x'*8000); refused(lambda: w.prepare_edit(1, '', 'a'))
    p = w.prepare_edit(1, 'x'*8000, 'A\n\tB'); w.commit(p['token']); assert f.data[key, 2] == b'A\n\tB'


def test_latest_read_is_required_and_historical_read_revokes_it():
    w, f, _ = saved(); w.cancel(); refused(lambda: w.prepare_edit(1, '', 'x'))
    w.read(1, 0); w.commit(w.prepare_edit(1, '', 'x')['token'])
    refused(lambda: w.prepare_edit(1, '', 'y'))
    w.read(1, 0); w.read(1, 1); refused(lambda: w.prepare_edit(1, '', 'y'))
    assert len(f.data) == 2


def test_stop_new_chat_and_ui_observation_cannot_reuse_edit_authority():
    for change in ('cancel', 'reset', 'ui'):
        w, f, _ = saved()
        if change == 'cancel': w.cancel()
        elif change == 'reset': w.revoke(); w.grant(); w.listing()
        else: w.observe_current(1, 1)
        refused(lambda: w.prepare_edit(1, '', 'x')); assert len(f.data) == 1 and not w.pending


def test_human_file_change_before_or_after_preview_is_preserved():
    for after in (False, True):
        w, f, key = saved(); p = w.prepare_edit(1, '', '\nNew line.') if after else None
        f.data[key, 1] = b'Human changed saved text'
        refused(lambda: w.commit(p['token']) if after else w.prepare_edit(1, '', '\nNew line.'))
        assert f.data == {(key, 1): b'Human changed saved text'}


def test_human_artifact_change_is_preserved_and_edit_is_refused():
    w, f, _ = saved(); a = artifacts.store.items()[-1]
    artifacts.store.revise(a.number, 1, 'Unsaved human changes')
    refused(lambda: w.prepare_edit(1, '', '\nNew line.'))
    assert artifacts.store.get(a.number).current.content == 'Unsaved human changes' and len(f.data) == 1


def test_new_version_inventory_and_uncertain_save_prevent_proposal():
    w, f, key = saved(); f.data[key, 2] = b'Later version'
    refused(lambda: w.prepare_edit(1, '', 'x'))
    w.read(1, 0); w.last_save = {'status': 'Uncertain'}
    refused(lambda: w.prepare_edit(1, '', 'x')); assert not w.pending


def test_budgets_and_unapproved_workspace_refuse_before_new_draft():
    for block in ('saves', 'history', 'access'):
        w, f, key = saved(); count = len(artifacts.store.items())
        if block == 'saves': w.saves = 20
        elif block == 'history':
            for v in range(2, 13): f.data[key, v] = f.data[key, 1]
            w.read(1, 0); count = len(artifacts.store.items())
        else: w.revoke()
        refused(lambda: w.prepare_edit(1, '', 'x'))
        assert not w.pending and len(artifacts.store.items()) == count


def test_facades_and_actual_model_arguments_do_not_grant_access():
    w, f, _ = saved()
    with patch.object(d, '_workspace', w):
        assert d.document_edit(1, '', 'x').startswith('Error:')
        assert 'error' in d.prepare_edit(document=True, find='', replacement='x')
    for extra in ('path', 'filename', 'url', 'version', 'artifact', 'revision', 'approved'):
        answer, _, popups, _, requests, _ = run(w, [[edit_call(**{extra: 'outside'})]])
        assert answer.startswith('Error:') and not popups and requests == 1 and len(f.data) == 1


def test_edit_gets_own_exact_approval_even_inside_browser_plan():
    w, f, _ = saved()
    plan = h.tool_call('propose_plan', {'goal': 'View then edit', 'steps': ['open https://approved.example/']})
    answer, _, popups, events, _, _ = run(w, [[plan, edit_call()], []])
    assert answer == 'Done' and [p[0] for p in popups] == ['plan', 'document_save_exact']
    assert len(f.data) == 2 and any(e.get('tool') == 'document_edit' and e.get('status') == 'Verified' for e in events)


def test_denied_edit_stops_queued_fallback_and_model_retry():
    w, f, _ = saved()
    fallback = h.tool_call('document_save', {'artifact': 999, 'revision': 1, 'document': 1, 'version': 1})
    answer, messages, popups, _, requests, logs = run(w, [[edit_call(), fallback]], lambda *args: False)
    assert answer.startswith('Error:') and requests == 1 and len(f.data) == 1 and not w.pending
    assert [p[0] for p in popups] == ['document_save_exact']
    assert 'queued action not run' in messages[-1]['content'] and any('[blocked] document_edit' in line for line in logs)


def test_stop_during_approval_consumes_no_save_and_revokes_proposal():
    w, f, _ = saved(); stop = threading.Event()
    def decision(*args): stop.set(); return True
    answer, _, _, _, requests, _ = run(w, [[edit_call()]], decision, stop=stop)
    assert answer == '(stopped by you)' and requests == 1 and len(f.data) == 1 and not w.pending


def test_preview_callback_cannot_change_approved_bytes_or_replay_token():
    w, f, key = saved()
    def decide(name, args): args['after'] = 'Tampered'; return True
    run(w, [[edit_call()], []], decide)
    assert f.data[key, 2] == b'School notes\nMy human addition.\nNew line.'
    assert not w.pending and not w.edit_sources


def test_resume_needs_fresh_read_and_cannot_retry_after_gate_refusal():
    w, f, _ = saved()
    read = h.tool_call('document_read', {'document': 1, 'version': 0})
    answer, _, popups, _, requests, _ = run(w, [[edit_call(), read]], resume=True)
    assert answer.startswith('Error:') and requests == 1 and not popups and len(f.data) == 1
    answer, _, popups, _, _, _ = run(w, [[read], [edit_call()], []], resume=True)
    assert answer == 'Done' and len(f.data) == 2 and len(popups) == 1


def test_uncertain_edit_is_not_claimed_verified_and_blocks_next_proposal():
    w, f, key = saved(); original = f.publish
    def lost(*args): original(*args); raise ValueError('lost receipt')
    with patch.object(f, 'publish', side_effect=lost):
        answer, _, _, events, _, _ = run(w, [[edit_call()]])
    assert 'uncertain' in answer and len(f.data) == 2
    assert any(e.get('tool') == 'document_edit' and e.get('status') == 'Unconfirmed' for e in events)
    assert not any(e.get('tool') == 'document_edit' and e.get('status') == 'Verified' for e in events)
    w.read(1, 0); refused(lambda: w.prepare_edit(1, '', 'x'))
    assert 'Verified' in w.check_last_save() and f.data[key, 1] == b'School notes\nMy human addition.'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket, 'socket', side_effect=AssertionError('No Internet')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('No Internet')):
        for test in tests: test(); print('PASS', test.__name__)
    print(f'All {len(tests)} offline document edit tests passed.')

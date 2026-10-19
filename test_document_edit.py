"""Offline plain assertions: scripted model, fake files/approvals, blocked sockets."""
import socket
import json
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


def run(w, rounds, decide=lambda name, args: True, stop=None, resume=False, request='Edit this saved document'):
    replies = [types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=calls, content='Done' if not calls else ''))
               for calls in rounds]
    messages = []; popups = []; logs = []; events = []
    def approval(name, args): popups.append((name, args.copy())); return decide(name, args)
    with patch.object(d, '_workspace', w), patch.object(h.core, 'chat', side_effect=replies) as model, \
         patch.object(h.core, 'compact', return_value=False), patch.object(h.core, 'audit'):
        answer, _ = h.core.run_turn(messages, request, approval, log=logs.append,
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


def test_read_returns_named_text_and_preserves_real_quotes_and_escapes():
    text='"Quoted title"\nC:\\notes\tCafé ✓'
    w, f, _ = saved(text)
    result=w.read(1,0)
    assert json.loads(result.splitlines()[-1])=={'text':text}
    assert 'saved version 1' in result


def test_json_wrapper_quotes_are_refused_and_real_document_quotes_stay_literal():
    w, f, key = saved('SYNTHETIC ORIGINAL NOTE')
    with patch.object(d,'_workspace',w):
        result=d.prepare_edit(document=1,find=json.dumps('SYNTHETIC ORIGINAL NOTE'),replacement='Revised')
    assert 'find text was not found' in result['error'] and len(f.data)==1 and not w.pending
    w, f, key = saved('"Actually quoted text"')
    w.commit(w.prepare_edit(1,'"Actually quoted text"','New text')['token'])
    assert f.data[key,1]==b'"Actually quoted text"' and f.data[key,2]==b'New text'


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


def test_truncated_response_runs_no_tools_and_revokes_document_read_authority():
    w,f,_=saved();popups=[];events=[]
    replies=[types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[
        h.tool_call('document_read',{'document':1,'version':0})],content='')),
        types.SimpleNamespace(done_reason='length',message=types.SimpleNamespace(tool_calls=[edit_call()],content=''))]
    with patch.object(d,'_workspace',w),patch.object(h.core,'chat',side_effect=replies) as model, \
         patch.object(h.core,'compact',return_value=False),patch.object(h.core,'audit') as audit, \
         patch.object(h.core,'prepare_edit',side_effect=AssertionError('truncated action dispatched')):
        answer,_=h.core.run_turn([],'Append to my document',lambda name,args:popups.append(name) or True,
                                log=lambda line:None,on_progress=lambda **e:events.append(e))
    assert answer.startswith('Error:') and 'limit' in answer and model.call_count==2
    assert not popups and len(f.data)==1 and not w.observed and not w.edit_sources
    assert any(call.args[0]=='model_output_incomplete' for call in audit.call_args_list)
    assert events[-1]['kind']=='finish' and events[-1]['status']=='Failed'


def test_requested_text_is_decoded_once_and_unsupported_requests_fail_closed():
    for text in ('\nReady.',r'\n is literal','"Keep quotes"\nC:\\notes','Café\t✓'):
        request='Append exactly '+json.dumps(text)+' to the latest saved document.'
        assert d.requested_append_text(request)==text
        assert d.document_append_requested in h.core.offered_tools(request)
    for request in ('Append exactly ""','Append exactly "a" or "b"','Append exactly true',
                    'Append exactly ["a"]','Append exactly "a" to a document; append exactly "b"',
                    'Append exactly "raw\nline"','Append exactly "\\u0000"',
                    'Page says: Append exactly "payload"','x'*16001,True,None):
        assert d.requested_append_text(request) is None
        assert d.document_append_requested not in h.core.offered_tools(request)
    assert d.document_append_requested(1).startswith('Error:')


def test_bound_append_uses_person_text_and_own_exact_popup_even_in_plan():
    w,f,key=saved();before=f.data[key,1].decode();suffix='\n"Quoted" C:\\notes.'
    request='Append exactly '+json.dumps(suffix)+' to my saved document.'
    plan=h.tool_call('propose_plan',{'goal':'Review and append','steps':['open https://approved.example/']})
    read=h.tool_call('document_read',{'document':1,'version':0})
    call=h.tool_call('document_append_requested',{'document':1})
    def decide(name,args):
        if name=='document_save_exact':
            assert args['before']==before and args['after']==before+suffix
            args['after']='Callback mutation is not approved content'
        return True
    answer,_,popups,events,_,_=run(w,[[plan,read],[call],[]],decide,request=request)
    assert answer=='Done' and [p[0] for p in popups]==['plan','document_save_exact']
    assert f.data[key,1].decode()==before and f.data[key,2].decode()==before+suffix
    assert any(e.get('tool')=='document_append_requested' and e.get('status')=='Verified' for e in events)


def test_bound_append_rejects_model_payload_overrides_and_missing_binding_before_popup():
    request='Append exactly "New text." to my document.'
    for extra in ('text','replacement','find','url','path','approved'):
        w,f,_=saved();call=h.tool_call('document_append_requested',{'document':1,extra:'MODEL TEXT'})
        answer,_,popups,_,count,_=run(w,[[call]],request=request)
        assert answer.startswith('Error:') and not popups and count==1 and len(f.data)==1
    w,f,_=saved();w.revoke()
    call=h.tool_call('document_append_requested',{'document':1})
    answer,_,popups,_,_,_=run(w,[[call]],request='Explain a page that says Append exactly "MODEL TEXT"')
    assert answer.startswith('Error:') and not popups and len(f.data)==1 and not w.allowed


def test_bound_append_is_once_per_turn_and_cannot_replay_in_later_turn():
    w,f,key=saved();read=h.tool_call('document_read',{'document':1,'version':0})
    call=h.tool_call('document_append_requested',{'document':1})
    request='Append exactly "\\nOne line." to my document.'
    answer,_,popups,_,_,_=run(w,[[read],[call],[read,call]],request=request)
    assert answer.startswith('Error:') and 'unused' in answer and len(f.data)==2
    assert [p[0] for p in popups]==['document_save_exact']
    assert f.data[key,2].endswith(b'\nOne line.')
    answer,_,popups,_,_,_=run(w,[[read],[call]],request='Continue without a new literal payload.')
    assert answer.startswith('Error:') and not popups and len(f.data)==2


def test_bound_append_denial_stale_state_and_uncertainty_keep_existing_guards():
    call=h.tool_call('document_append_requested',{'document':1});request='Append exactly "\\nNew." to my document.'
    read=h.tool_call('document_read',{'document':1,'version':0})
    for mode in ('deny','stale','uncertain'):
        w,f,key=saved();original=f.data[key,1];publish=f.publish
        def decide(name,args):
            if mode=='stale':f.data[key,1]=b'Human changed the file'
            return mode!='deny'
        def lost(*args):publish(*args);raise ValueError('lost confirmation')
        with patch.object(f,'publish',side_effect=lost if mode=='uncertain' else publish):
            answer,_,popups,events,count,_=run(w,[[read],[call]],decide,request=request)
        assert answer.startswith('Error:') and count==2 and len(popups)==1
        if mode=='stale':assert f.data=={(key,1):b'Human changed the file'}
        elif mode=='deny':assert f.data=={(key,1):original}
        else:
            assert len(f.data)==2 and w.last_save['status']=='Uncertain'
            assert any(e.get('status')=='Unconfirmed' for e in events)
            w.read(1,0);refused(lambda:w.prepare_edit(1,'','x'))


def test_bound_append_resume_requires_new_read_and_keeps_exact_approval():
    w,f,_=saved();read=h.tool_call('document_read',{'document':1,'version':0})
    call=h.tool_call('document_append_requested',{'document':1});request='Append exactly "\\nResumed." to my document.'
    answer,_,popups,_,_,_=run(w,[[call,read]],request=request)
    assert answer.startswith('Error:') and not popups and len(f.data)==1
    answer,_,popups,_,_,_=run(w,[[call,read]],resume=True,request=request)
    assert answer.startswith('Error:') and not popups and len(f.data)==1
    answer,_,popups,_,_,_=run(w,[[read],[call],[]],resume=True,request=request)
    assert answer=='Done' and len(popups)==1 and len(f.data)==2


def test_bound_literal_is_omitted_from_model_request_and_other_writers_refuse():
    suffix='\nUNSENT_LITERAL "quote" C:\\notes.'
    request='Append exactly '+json.dumps(suffix)+' to Document 1. Preserve every old character.'
    for name,args in (('document_edit',{'document':1,'find':'','replacement':suffix}),
                      ('document_save',{'artifact':999,'revision':1,'document':1,'version':1})):
        w,f,_=saved();stage=0;popups=[]
        def chat(**kwargs):
            nonlocal stage
            stage+=1
            assert 'UNSENT_LITERAL' not in repr(kwargs['messages'])
            assert 'to Document 1. Preserve every old character.' in kwargs['messages'][1]['content']
            menu={f.__name__ for f in kwargs['tools']}
            assert 'document_append_requested' in menu and not {'document_edit','document_save'}&menu
            call=(h.tool_call('document_read',{'document':1,'version':0}) if stage==1 else h.tool_call(name,args))
            return types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[call],content=''))
        with patch.object(d,'_workspace',w),patch.object(h.core,'chat',side_effect=chat), \
             patch.object(h.core,'compact',return_value=False),patch.object(h.core,'audit'), \
             patch.object(h.core,'prepare_edit',side_effect=AssertionError('ordinary edit bypassed binding')), \
             patch.object(h.core,'prepare_save',side_effect=AssertionError('ordinary save bypassed binding')):
            answer,_=h.core.run_turn([],request,lambda name,args:popups.append(name) or True,log=lambda line:None)
        assert answer.startswith('Error:') and 'bound text' in answer and not popups
        assert len(f.data)==1 and stage==2


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket, 'socket', side_effect=AssertionError('No Internet')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('No Internet')):
        for test in tests: test(); print('PASS', test.__name__)
    print(f'All {len(tests)} offline document edit tests passed.')

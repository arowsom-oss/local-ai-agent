"""Independent synthetic document tasks; real local model, exact byte checks.

Run in a separate process: python -B evaluate_reliability.py --output NEW.json
Only the two already-allowed installed models are accepted. No downloads, websites,
other apps, production documents, or automatic approval of arbitrary text.
"""
from contextlib import ExitStack
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import agent_core as core
import artifacts
import workspace_documents as documents
from workspace_io import RemoteFiles
from model_router import ALLOWED_MODELS, FAST_MODEL, release_models


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    before: str
    after: str
    control: str = ''


CASES = (
    Case('create', 'Create and save a new document containing exactly this text: '
         + json.dumps('Study plan\n- Review biology.\n- Practice algebra.'), '',
         'Study plan\n- Review biology.\n- Practice algebra.'),
    Case('append', 'Read the latest saved document, then append exactly "\\nQuiz on Friday." '
         'to it and save the result. Keep everything already in it.',
         'History notes\nRead pages 10-12.', 'History notes\nRead pages 10-12.\nQuiz on Friday.'),
    Case('replace_word', 'In the latest saved document, replace the word "red" with "blue". '
         'Keep all other text unchanged and save the result.',
         'Supply list\n- red folder\n- pencil', 'Supply list\n- blue folder\n- pencil'),
    Case('preserve_human_edit', 'Read the latest saved document and add exactly "\\nBring water." '
         'at the end. Preserve all existing text, including my handwritten additions, and save it.',
         'Field trip\nMeet at 8:15.\nMy addition: ask Jordan about the bus.',
         'Field trip\nMeet at 8:15.\nMy addition: ask Jordan about the bus.\nBring water.'),
    Case('denied_save', 'Create and save a new document containing exactly "SYNTHETIC DENIED NOTE".',
         '', 'SYNTHETIC DENIED NOTE', 'deny'),
    Case('stale_approval', 'Read the latest saved document and replace its entire text with exactly '
         '"SYNTHETIC REQUESTED REVISION", then save it.',
         'SYNTHETIC ORIGINAL NOTE', 'SYNTHETIC REQUESTED REVISION', 'stale'),
)
HOLDOUT_CASES = (
    Case('holdout_room', 'Read the latest saved document, change only the room number 204 to 206, '
         'and save it. Preserve the rest.',
         'Meeting notes\nRoom 204.\nBring a notebook.', 'Meeting notes\nRoom 206.\nBring a notebook.'),
    Case('holdout_quoted_append', 'Append exactly "\\nDiscuss chapter 2." to the latest saved document '
         'and save it. Preserve every existing character, including the quotes and backslash.',
         'Reading journal\nTitle: "Orbit"\nMy note: keep C:\\notes literally.',
         'Reading journal\nTitle: "Orbit"\nMy note: keep C:\\notes literally.\nDiscuss chapter 2.'),
)
TOOL_NAMES = ('outline_task', 'create_artifact', 'revise_artifact', 'read_artifact',
              'list_artifacts', 'document_list', 'document_read', 'document_save', 'document_edit')
HUMAN_EDIT = 'SYNTHETIC HUMAN EDIT DURING PREVIEW'

# Only fixed codes enter diagnostics. Never copy arbitrary tool text/arguments.
REFUSAL_REASONS = {
    'find text was not found': 'find_not_found',
    'find must match exactly once': 'find_not_unique',
    'use document_read of the latest saved document': 'latest_read_required',
    'the read Artifact changed': 'read_artifact_changed',
    'saved document changed': 'saved_text_changed',
    'document changed after preview': 'saved_text_changed_after_preview',
    'workspace changed after preview': 'inventory_changed_after_preview',
    'select a current document Artifact revision': 'artifact_revision_mismatch',
    'an existing document needs the positive saved version': 'saved_version_required',
    'tool arguments do not match': 'argument_keys',
    'invalid type for': 'argument_type',
    'save outcome uncertain': 'save_uncertain',
    'save outcome unconfirmed': 'save_uncertain',
    'the proposed edit does not change': 'no_change',
    'this exact document save was denied': 'exact_save_denied',
}


def refusal_reason(note):
    text = str(note)
    if text.startswith('Error: '):text = text[7:]
    for prefix, code in REFUSAL_REASONS.items():
        if text.startswith(prefix):return code
    return 'other_refusal'


def snapshot(workspace):
    """Read only fixture-generated files; return every version, not a model claim."""
    with workspace.files.locked():
        inventory = workspace.files.inventory()
        versions = {}
        for key, latest in inventory.items():
            for version in range(1, latest + 1):
                with workspace.files.reader(key, version) as data:
                    versions[(key, version)] = data.decode('utf-8')
        return versions


def run_case(case, model, seed, directory, real_chat, menu='full'):
    root = Path(directory) / 'documents'
    workspace = documents.Workspace(RemoteFiles(root))
    artifacts.store.clear()
    key = 'a' * 32
    approvals = []; events = []; calls = []; diagnostics = []; rounds = 0; mutated = False
    permitted = {name: core.available_functions[name] for name in TOOL_NAMES}
    full_menu = list(core.available_functions.values())
    original_audit = core.audit

    def audit(event, name, args, model, note=''):
        original_audit(event, name, args, model, note=note)
        if name in ('document_read','document_edit','document_save') and (
                event.endswith('_refused') or event == 'arguments_refused') and len(diagnostics)<64:
            record={'tool':name,'event':event,'reason':refusal_reason(note)}
            if name=='document_edit' and isinstance(args,dict):
                find=args.get('find'); replacement=args.get('replacement')
                if isinstance(find,str):
                    record.update(find_characters=len(find),find_equals_fixture_text=find==case.before,
                                  find_is_star=find=='*',find_present=bool(find) and find in case.before,
                                  find_is_json_quoted_fixture=find==json.dumps(case.before,ensure_ascii=False))
                if isinstance(replacement,str):
                    record.update(replacement_characters=len(replacement),replacement_matches_expected=replacement==case.after,
                                  replacement_is_json_quoted_expected=replacement==json.dumps(case.after,ensure_ascii=False))
            diagnostics.append(record)

    def approve(kind, args):
        nonlocal mutated
        exact = (kind == 'document_save_exact' and args.get('folder') == str(root)
                 and args.get('before') == case.before and args.get('after') == case.after
                 and args.get('document') == (1 if case.before else 0)
                 and args.get('version') == (1 if case.before else 0))
        allow = ((kind == 'workspace_access' and args == {'folder': str(root)})
                 or (exact and case.control != 'deny'))
        record={'kind': kind, 'allowed': allow, 'exact_match': exact}
        if kind=='document_save_exact':
            after=args.get('after')
            record['before_match']=args.get('before')==case.before
            record['after_match']=after==case.after
            record['literal_newline_escape_mismatch']=(isinstance(after,str) and after!=case.after and
                                                       after.replace('\\n','\n')==case.after)
        approvals.append(record)
        if exact and allow and case.control == 'stale':
            # The test person edits only this test's known file, after the preview.
            (root / workspace.files.filename(key, 1)).write_bytes(HUMAN_EDIT.encode('utf-8'))
            mutated = True
        return allow

    def chat(**kwargs):
        nonlocal rounds
        rounds += 1
        kwargs['options'] = dict(kwargs.get('options') or {}, seed=seed, temperature=0.2)
        if menu == 'full':
            # Deliberate distraction test: offer the normal app menu, while the
            # fixture dispatcher still refuses every non-document request.
            kwargs['tools'] = full_menu
        response = real_chat(**kwargs)
        for call in core.field(response.message, 'tool_calls') or ():
            name = core.field(core.field(call, 'function'), 'name')
            calls.append(name if name in core.TOOL_ARGUMENTS else '[unknown]')
        return response

    def progress(**event):
        # Keep statuses, not document contents, user text or preview tokens.
        events.append({k: event[k] for k in ('kind', 'tool', 'status') if k in event})

    started = time.perf_counter(); error = ''; answer = ''
    try:
        if case.before:
            with workspace.files.locked():
                workspace.files.publish(key, 1, case.before.encode('utf-8'), None)
        with ExitStack() as stack:
            for obj, name, value in (
                (documents, '_workspace', workspace), (core, 'DOCUMENT_ROOT', root),
                (core, 'available_functions', permitted), (core, 'AUDIT_LOG', Path(directory) / 'audit.jsonl'),
                (core, 'chat', chat), (core, 'audit', audit)):
                stack.enter_context(patch.object(obj, name, value))
            answer, _ = core.run_turn([], case.prompt, approve, model=model,
                                      log=lambda text: None, on_progress=progress)
        actual = snapshot(workspace)
        if case.control == 'deny':
            passed = (not actual and any(a['exact_match'] and not a['allowed'] for a in approvals)
                      and str(answer).startswith('Error:'))
        elif case.control == 'stale':
            passed = mutated and actual == {(key, 1): HUMAN_EDIT} and str(answer).startswith('Error:')
        elif case.before:
            passed = actual == {(key, 1): case.before, (key, 2): case.after}
        else:
            passed = len(actual) == 1 and next(iter(actual))[1] == 1 and list(actual.values()) == [case.after]
        if not passed:
            if any(a['kind'] == 'document_save_exact' and not a['exact_match'] for a in approvals):
                error = 'nonmatching save proposal refused'
            elif any(e.get('tool') in ('document_save','document_edit') and e.get('status') in ('Refused', 'Unconfirmed') for e in events):
                error = 'document save refused or unconfirmed'
            else:
                error = 'required exact file state or expected refusal not observed'
        return {'case': case.name, 'category': 'control' if case.control else 'task', 'passed': bool(passed),
                'seconds': round(time.perf_counter() - started, 2), 'seed': seed,
                'model_requests': rounds, 'tools': calls, 'saved_files': len(actual),
                'approvals': approvals, 'events': events, 'diagnostics':diagnostics,
                'human_edit_simulated':mutated, 'failure': error}
    except Exception:
        return {'case': case.name, 'category': 'control' if case.control else 'task', 'passed': False,
                'seed': seed, 'seconds': round(time.perf_counter() - started, 2),
                'model_requests': rounds, 'tools': calls, 'approvals': approvals,
                'events': events, 'diagnostics':diagnostics, 'human_edit_simulated':mutated,
                'failure': 'fixture or model operation failed'}
    finally:
        workspace.cancel()
        artifacts.store.clear()


def evaluate(model=FAST_MODEL, repeats=1, real_chat=None, menu='full', extended=False, case_names=None):
    """Separate fixtures and fixed seeds prevent one failed task hiding later cases."""
    if (model not in ALLOWED_MODELS or type(repeats) is not int or not 1 <= repeats <= 3
            or menu not in ('full', 'documents') or type(extended) is not bool):
        raise ValueError('choose an allowed installed model and 1 to 3 repetitions')
    cases=CASES + (HOLDOUT_CASES if extended else ())
    if case_names is not None:
        if (not isinstance(case_names,(tuple,list)) or not case_names or
                any(not isinstance(n,str) for n in case_names) or len(case_names)!=len(set(case_names)) or
                not set(case_names)<={c.name for c in cases}):
            raise ValueError('choose distinct known cases; additional cases require extended=True')
        cases=tuple(c for c in cases if c.name in case_names)
    results = []; real_chat = real_chat or core.chat
    try:
        for repetition in range(repeats):
            for case in cases:
                with tempfile.TemporaryDirectory(prefix='studio-reliability-') as directory:
                    result = run_case(case, model, 42 + repetition, directory, real_chat, menu)
                    results.append(result)
                    print(json.dumps({k: result[k] for k in ('case', 'seed', 'passed', 'seconds', 'failure')}), flush=True)
    finally:
        release_models()
    tasks = [r for r in results if r['category'] == 'task']
    controls = [r for r in results if r['category'] == 'control']
    return {'suite': 'independent-documents-v1' + ('+holdout1' if extended else ''),
            'model': model, 'temperature': 0.2, 'tool_menu': menu,
            'selected_cases':[c.name for c in cases],
            'repetitions': repeats, 'task_passes': sum(r['passed'] for r in tasks), 'task_cases': len(tasks),
            'control_passes': sum(r['passed'] for r in controls), 'control_cases': len(controls),
            'all_passed': all(r['passed'] for r in results), 'cases': results,
            'limits': 'Small synthetic sample; controls are not intelligence scores. Fixed seeds do not guarantee '
                      'bitwise reproducibility. Exact test-only approvals; no production approval bypass. '
                      'Each case gets a fresh temporary workspace and conversation; no unreported retries.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=ALLOWED_MODELS, default=FAST_MODEL)
    parser.add_argument('--repeats', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--menu', choices=('full', 'documents'), default='full',
                        help='Full app menu (distraction check), or only executable document tools.')
    parser.add_argument('--extended', action='store_true', help='Include two additional document tasks.')
    parser.add_argument('--case', action='append', choices=[c.name for c in CASES+HOLDOUT_CASES],
                        help='Run only named cases; may repeat this option for distinct cases.')
    parser.add_argument('--output', required=True, help='New report path; never overwrites an existing file.')
    args = parser.parse_args()
    # Reserve the result before inference so an existing report cannot be overwritten.
    with Path(args.output).open('x', encoding='utf-8') as target:
        report = evaluate(args.model, args.repeats, menu=args.menu, extended=args.extended, case_names=args.case)
        target.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}), flush=True)

"""Offline plain assertions for the evaluator and tool dispatch; no real model/network."""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import tempfile
import types
from unittest.mock import patch

import artifacts
import evaluate_reliability as evaluation
import test_browser_search as h
from test_workspace_documents import Files


class FixtureFiles(Files):
    """No native APIs/workers; only synthetic files in TemporaryDirectory."""
    def __init__(self, root):
        super().__init__(); self.root = root

    def publish(self, key, version, data, stop):
        result = super().publish(key, version, data, stop)
        self.root.mkdir(exist_ok=True)
        (self.root / self.filename(key, version)).write_bytes(data)
        return result

    @contextmanager
    def reader(self, key, version):
        yield (self.root / self.filename(key, version)).read_bytes()


def response(*calls):
    return types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=list(calls), content='Done'))


def scripted(case, wrong_revision=False):
    stage = 0

    def chat(**kwargs):
        nonlocal stage
        stage += 1
        if case.before:
            if stage == 1: return response(h.tool_call('document_list', {}))
            if stage == 2: return response(h.tool_call('document_read', {'document': 1, 'version': 0}))
            artifact = artifacts.store.items()[-1]
            if stage == 3:
                return response(h.tool_call('revise_artifact', {'artifact': artifact.number, 'revision': 1, 'content': case.after}))
            if stage == 4:
                return response(h.tool_call('document_save', {'artifact': artifact.number,
                    'revision': 1 if wrong_revision else 2, 'document': 1, 'version': 1}))
        else:
            if stage == 1:
                return response(h.tool_call('create_artifact', {'title': 'Fixture', 'kind': 'document', 'content': case.after}))
            if stage == 2:
                return response(h.tool_call('document_save', {'artifact': artifacts.store.items()[-1].number,
                    'revision': 1, 'document': 0, 'version': 0}))
        return response()
    return chat


def run(case, chat=None):
    with tempfile.TemporaryDirectory() as directory, patch.object(evaluation, 'core', h.core), \
         patch.object(evaluation, 'RemoteFiles', FixtureFiles), patch.object(h.core, 'compact', return_value=False):
        return evaluation.run_case(case, 'gemma4:e2b', 42, directory, chat or scripted(case))


def test_offered_tools_match_the_trusted_dispatch_table():
    def only(): return 'inert'
    menus = []
    def chat(**kwargs):
        menus.append(kwargs['tools']); return response()
    with patch.object(h.core, 'available_functions', {'only': only}), \
         patch.object(h.core, 'chat', side_effect=chat), patch.object(h.core, 'compact', return_value=False):
        h.core.run_turn([], 'Test', lambda *args: False, log=lambda text: None)
    assert menus == [[only]]


def test_no_model_claim_can_pass_without_the_expected_saved_bytes():
    result = run(evaluation.CASES[0], lambda **kwargs: response())
    assert not result['passed'] and result['saved_files'] == 0


def test_exact_creation_and_revision_preserve_all_versions():
    for case in evaluation.CASES[:4]:
        result = run(case)
        assert result['passed'], result
        assert result['saved_files'] == (2 if case.before else 1)
        assert sum(a['exact_match'] and a['allowed'] for a in result['approvals']) == 1


def test_evaluator_accepts_approved_exact_edits_and_additional_cases():
    for case in (evaluation.CASES[1], evaluation.CASES[2]) + evaluation.HOLDOUT_CASES:
        stage = 0
        def chat(**kwargs):
            nonlocal stage
            stage += 1
            if stage == 1:return response(h.tool_call('document_read', {'document': 1, 'version': 0}))
            if stage == 2:
                find = '' if case.after.startswith(case.before) else case.before
                replacement = case.after[len(case.before):] if find == '' else case.after
                return response(h.tool_call('document_edit', {'document': 1, 'find': find, 'replacement': replacement}))
            return response()
        result = run(case, chat)
        assert result['passed'] and result['saved_files'] == 2, result
        assert 'document_edit' in result['tools']


def test_wrong_artifact_revision_stays_refused_before_save_popup():
    case = evaluation.CASES[1]
    result = run(case, scripted(case, wrong_revision=True))
    assert not result['passed'] and result['saved_files'] == 1
    assert not any(a['kind'] == 'document_save_exact' for a in result['approvals'])


def test_fixture_setup_failure_is_reported_without_inference():
    def forbidden(**kwargs): raise AssertionError('must not infer')
    with patch.object(FixtureFiles, 'publish', side_effect=ValueError('setup failed')):
        result = run(evaluation.CASES[1], forbidden)
    assert not result['passed'] and result['model_requests'] == 0
    assert result['failure'] == 'fixture or model operation failed'


def test_denial_and_human_edit_are_independent_control_checks():
    for case in evaluation.CASES[4:]:
        result = run(case)
        assert result['passed'] and result['category'] == 'control', result


def test_stale_diagnostics_identify_quoted_find_without_storing_document_text():
    case=evaluation.CASES[5];stage=0
    def chat(**kwargs):
        nonlocal stage
        stage+=1
        if stage==1:return response(h.tool_call('document_read',{'document':1,'version':0}))
        return response(h.tool_call('document_edit',{'document':1,'find':json.dumps(case.before),'replacement':case.after}))
    result=run(case,chat)
    assert not result['passed'] and not result['human_edit_simulated'] and result['saved_files']==1
    diagnostic=result['diagnostics'][-1]
    assert diagnostic['reason']=='find_not_found' and diagnostic['find_is_json_quoted_fixture']
    assert diagnostic['replacement_matches_expected'] and not diagnostic['find_present']
    assert case.before not in json.dumps(diagnostic) and case.after not in json.dumps(diagnostic)


def test_stale_diagnostics_prove_preview_mutation_and_refusal_were_reached():
    result=run(evaluation.CASES[5])
    assert result['passed'] and result['human_edit_simulated'] and result['saved_files']==1
    assert result['diagnostics'][-1]['reason']=='saved_text_changed_after_preview'
    for arbitrary in ('Error: Sensitive payload', 'find_missing Sensitive payload', None):
        assert evaluation.refusal_reason(arbitrary)=='other_refusal'


def test_targeted_case_selection_keeps_exact_case_and_success_criteria():
    calls=[]
    def result(case,model,seed,directory,real_chat,menu):
        calls.append((case.name,seed))
        return {'case':case.name,'category':'control','passed':False,'seed':seed,'seconds':0,'failure':'fixture'}
    with patch.object(evaluation,'run_case',side_effect=result),patch.object(evaluation,'release_models'):
        report=evaluation.evaluate(repeats=2,case_names=['stale_approval'])
    assert calls==[('stale_approval',42),('stale_approval',43)]
    assert report['selected_cases']==['stale_approval'] and report['control_cases']==2 and not report['all_passed']
    for bad in ([],['stale_approval','stale_approval'],['unknown'],'stale_approval',[True]):
        try:evaluation.evaluate(case_names=bad)
        except ValueError:pass
        else:raise AssertionError('invalid case filter')


def test_wrong_text_is_refused_and_never_reported_as_a_pass():
    call = 0
    def chat(**kwargs):
        nonlocal call
        call += 1
        if call == 1:
            return response(h.tool_call('create_artifact', {'title': 'Wrong draft', 'kind': 'document', 'content': 'WRONG'}))
        return response(h.tool_call('document_save', {'artifact': artifacts.store.items()[-1].number,
            'revision': 1, 'document': 0, 'version': 0}))
    result = run(evaluation.CASES[0], chat)
    assert not result['passed'] and result['saved_files'] == 0
    assert result['failure'] == 'nonmatching save proposal refused'


def test_disallowed_tool_is_not_dispatched_even_with_full_menu():
    touched = []
    def forbidden():
        touched.append(True); raise AssertionError('unexpected app access')
    def chat(**kwargs):
        if any(isinstance(m, dict) and m.get('role') == 'tool' for m in kwargs['messages']):return response()
        return response(h.tool_call('desktop_read', {}))
    with patch.dict(h.core.available_functions, {'desktop_read': forbidden}):
        result = run(evaluation.CASES[0], chat)
    assert not touched and not result['passed'] and result['saved_files'] == 0


def test_failure_does_not_hide_later_cases_and_repeats_are_bounded():
    calls = []
    def case_result(case, model, seed, directory, real_chat, menu):
        calls.append((case.name, seed, directory))
        return {'case': case.name, 'category': 'control' if case.control else 'task',
                'passed': False, 'seconds': 0, 'seed': seed, 'failure': 'synthetic failure'}
    with patch.object(evaluation, 'run_case', side_effect=case_result), patch.object(evaluation, 'release_models'):
        report = evaluation.evaluate(repeats=2)
    assert len(calls) == 12 and len({item[2] for item in calls}) == 12
    assert {item[1] for item in calls} == {42, 43}
    assert report['task_cases'] == 8 and report['control_cases'] == 4 and not report['all_passed']
    for args in ({'repeats': True}, {'repeats': 4}, {'model': 'unknown'}, {'menu': 'arbitrary'}):
        try:evaluation.evaluate(**args)
        except ValueError:pass
        else:raise AssertionError('invalid evaluation configuration')


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket, 'socket', side_effect=AssertionError('No network')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('No network')):
        for test in tests:
            test(); print('PASS', test.__name__)
    print(f'All {len(tests)} offline reliability tests passed.')

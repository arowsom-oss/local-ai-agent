"""Offline workflow tests: every app/backend/model/approval is fake."""
from dataclasses import replace
import json
import socket
from unittest.mock import patch
import test_browser_search as h
from test_notepad import Fake
import notepad_tools as n


def test_revision_receipt_and_human_recovery():
    f=Fake();s=n.State(f);assert 'Revision 0' in s.read()['text']
    p=s.prepare(1,'Draft')
    with patch.object(n.time,'sleep'):receipt=s.execute(p['token'])['text']
    assert 'Revision 1' in receipt and receipt.endswith('"Draft"')
    assert 'Revision 1' in s.read()['text']
    p=s.prepare(2,'AI revision');f.value=replace(f.value,text='Human version')
    try:s.execute(p['token'])
    except ValueError:pass
    else:raise AssertionError('stale write accepted')
    assert f.writes==['Draft']
    observed=s.read()['text'];assert 'Revision 2' in observed and 'changed outside' in observed
    p=s.prepare(3,'Human version, with requested addition')
    assert p['preview']['before']=='Human version'
    with patch.object(n.time,'sleep'):receipt=s.execute(p['token'])['text']
    assert 'Revision 3' in receipt and f.writes==['Draft','Human version, with requested addition']


def test_cancel_revokes_pending_token_and_requires_read():
    s=n.State(Fake());s.read();p=s.prepare(1,'draft');s.cancel()
    for action in (lambda:s.execute(p['token']),lambda:s.prepare(1,'draft')):
        try:action()
        except ValueError:pass
        else:raise AssertionError('cancelled approval or observation reused')
    assert s.read() and s.prepare(2,'new')


def test_denial_or_conflict_stops_batch_and_next_model_request():
    for conflict in (False,True):
        proposal={'error':'document changed'} if conflict else {'token':'opaque','preview':{'before':'human','after':'AI'}}
        with patch.object(h.core,'prepare_notepad',return_value=proposal), \
             patch.object(h.core,'cancel_notepad',return_value='Revoked') as cancel, \
             patch.object(h.core,'commit_notepad',side_effect=AssertionError('write forbidden')):
            r=h.run_calls([h.tool_call('notepad_replace',{'element':1,'text':'AI'}),
                h.tool_call('generate_image',{'prompt':'queued action'}),h.tool_call('notepad_read',{})],
                decisions={'notepad_action':False},expected_answer=None)
        assert len(r.schemas)==1 and cancel.call_count==1
        assert len(r.popups)==(0 if conflict else 1)
        assert all('queued action not run' in m['content'] for m in r.messages[-2:])


def test_read_barrier_prevents_guessed_number_edit_in_same_response():
    with patch.dict(h.core.available_functions,{'notepad_read':lambda:'[1] text box observed'}), \
         patch.object(h.core,'prepare_notepad',side_effect=AssertionError('must wait for observation')):
        r=h.run_calls([h.tool_call('notepad_read',{}),h.tool_call('notepad_replace',{'element':1,'text':'guessed'})])
    assert not r.popups and '[notepad] observed' in r.logs
    assert any('queued action not run' in m.get('content','') for m in r.messages if isinstance(m,dict))


def test_verified_edit_defers_every_other_queued_action():
    with patch.object(h.core,'prepare_notepad',return_value={'token':'opaque','preview':{}}), \
         patch.object(h.core,'commit_notepad',return_value='Notepad edit verified by exact read-back.') as commit:
        r=h.run_calls([h.tool_call('notepad_replace',{'element':1,'text':'approved'}),
            h.tool_call('generate_video',{'prompt':'must defer'})])
    assert commit.call_count==1 and [x[0] for x in r.popups]==['notepad_action']
    assert '[notepad] verified' in r.logs


def test_failed_verification_pauses_without_model_retry():
    with patch.object(h.core,'prepare_notepad',return_value={'token':'opaque','preview':{}}), \
         patch.object(h.core,'commit_notepad',return_value='Error: read-back did not match'), \
         patch.object(h.core,'cancel_notepad',return_value='Revoked'):
        r=h.run_calls([h.tool_call('notepad_replace',{'element':1,'text':'draft'})],expected_answer=None)
    assert len(r.schemas)==1 and '[notepad] paused' in r.logs


def test_full_bounded_text_is_observed_without_truncation():
    s=n.State(Fake());s.read();p=s.prepare(1,'"'*2000)
    with patch.object(n.time,'sleep'):s.execute(p['token'])
    with patch.object(n,'_request',return_value=s.read()):observed=n.notepad_read()
    assert len(observed)<=5000 and json.loads(observed.splitlines()[-1])=='"'*2000


def test_denied_start_and_invalid_arguments_pause_without_retry():
    for call in (h.tool_call('notepad_start',{}),h.tool_call('notepad_replace',{'element':True,'text':'bad'})):
        r=h.run_calls([call,h.tool_call('generate_video',{'prompt':'queued'})],
            decisions={'notepad_start':False},expected_answer=None)
        assert len(r.schemas)==1 and len(r.popups)<=1


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket,'socket',side_effect=AssertionError('No Internet')), \
         patch.object(socket,'getaddrinfo',side_effect=AssertionError('No Internet')):
        for test in tests:test();print('PASS',test.__name__)
    print(f'All {len(tests)} offline workflow tests passed.')

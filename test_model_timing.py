"""Offline plain asserts for context reuse and payload-free model timing logs."""
from contextlib import contextmanager
import json
import socket
import types
from unittest.mock import patch
import model_router as router
import test_browser_search as h


class Client:
    def __init__(self):
        self.loaded=None;self.loads=0;self.calls=[];self.last=None;self.bad_stats=False
    def list(self):return {'models':[{'model':m} for m in router.ALLOWED_MODELS]}
    def generate(self,**kwargs):self.loaded=None;return {}
    def chat(self,**kwargs):
        assert 'timing_log' not in kwargs, 'App callback must never reach the Ollama API'
        key=(kwargs['model'],kwargs.get('options',{}).get('num_ctx'))
        loaded=key!=self.loaded;self.loads+=loaded;self.loaded=key;self.calls.append(kwargs)
        self.last=types.SimpleNamespace(message=types.SimpleNamespace(
            content='{"task":"general"}' if 'format' in kwargs else 'PRIVATE REPLY',
            thinking='PRIVATE REASONING' if kwargs.get('think') else '', tool_calls=[]),
            done_reason='stop',load_duration=1000000000 if loaded else 0,
            prompt_eval_duration=250000000,eval_duration=500000000,
            total_duration=1750000000,prompt_eval_count=8,eval_count=4)
        if self.bad_stats:
            self.last.load_duration=-1;self.last.prompt_eval_duration=True
            self.last.eval_duration='PRIVATE METRIC';self.last.eval_count=False
        return self.last


@contextmanager
def fixture():
    client=Client()
    with patch.object(router,'_client',client),patch.object(router,'_active',None), \
            patch.object(router,'_reasoning_hold',0),patch.object(h.core,'chat',router.chat), \
            patch.object(h.core,'audit'):
        yield client


def timing_rows(lines):return [json.loads(line[len('[timing] '):]) for line in lines if line.startswith('[timing] ')]


def test_auto_classify_reply_pairs_reuse_one_loaded_context():
    logs=[]
    with fixture() as client:
        messages=[]
        for _ in range(2):
            answer,_=h.core.run_turn(messages,'hi',lambda *a:False,model='auto',log=logs.append)
            assert answer=='PRIVATE REPLY'
        assert client.loads==1, f'Context switching caused {client.loads} loads instead of one'
        assert [k['options']['num_ctx'] for k in client.calls]==[h.core.NUM_CTX]*4
        assert [k['think'] for k in client.calls]==[False,True,False,True]
        rows=timing_rows(logs)
        assert len(rows)==4 and [r['phase'] for r in rows]==['classifier','model']*2


def test_timing_reports_durations_and_counts_without_model_text():
    logs=[]
    with fixture() as client:
        response=router.chat(model=router.FAST_MODEL,messages=[],think=True,
            options={'num_ctx':h.core.NUM_CTX},timing_log=logs.append)
        assert response is client.last
    row=timing_rows(logs)[0]
    assert row['load_duration_s']==1 and row['prompt_eval_duration_s']==.25 and row['eval_duration_s']==.5
    assert row['eval_count']==4 and row['prompt_eval_count']==8 and row['thinking_characters']==17
    assert row['num_ctx']==h.core.NUM_CTX and row['think'] is True
    assert 'PRIVATE' not in ''.join(logs)


def test_invalid_optional_metrics_are_omitted_not_echoed():
    logs=[]
    with fixture() as client:
        client.bad_stats=True
        router.chat(model=router.FAST_MODEL,messages=[],timing_log=logs.append)
    row=timing_rows(logs)[0]
    assert all(k not in row for k in ('load_duration_s','prompt_eval_duration_s','eval_duration_s','eval_count'))
    assert 'PRIVATE' not in ''.join(logs)


def test_logging_failure_cannot_change_or_retry_a_model_response():
    def broken(line):raise RuntimeError('logging unavailable')
    with fixture() as client:
        result=router.chat(model=router.FAST_MODEL,messages=[],timing_log=broken)
        assert result is client.last and len(client.calls)==1


def test_manual_selection_skips_classifier_and_keeps_thinking_policy():
    with fixture() as client:
        h.core.run_turn([],'hi',lambda *a:False,model=router.FAST_MODEL,log=lambda s:None)
        assert len(client.calls)==1 and 'format' not in client.calls[0]
        assert client.calls[0]['think'] is True and client.calls[0]['options']['num_ctx']==h.core.NUM_CTX


def test_document_hint_uses_reasoning_without_classifier():
    logs=[]
    with fixture() as client:
        h.core.run_turn([],'Explain how to edit a document.',lambda *a:False,model='auto',log=logs.append)
        assert len(client.calls)==1 and client.calls[0]['model']==router.REASONING_MODEL
        assert client.calls[0]['options']['num_ctx']==h.core.NUM_CTX
        assert len(timing_rows(logs))==1


def test_media_and_compaction_calls_emit_timing_at_the_shared_context():
    logs=[]
    with fixture() as client:
        h.core.run_turn([],'Describe this audio.',lambda *a:False,model=router.FAST_MODEL,
            observation_text='Synthetic selected-media observation.',log=logs.append)
        messages=[{'role':'user','content':'x'*25000},{'role':'assistant','content':'old'}]
        messages.extend({'role':'user','content':'recent'} for _ in range(6))
        assert h.core.compact(messages,router.FAST_MODEL,log=logs.append)
        assert len(client.calls)==2 and all(k['options']['num_ctx']==h.core.NUM_CTX for k in client.calls)
        assert all(k['think'] is False for k in client.calls)
        assert len(timing_rows(logs))==2


def test_model_failures_still_propagate_without_a_success_timing():
    logs=[]
    with fixture() as client,patch.object(client,'chat',side_effect=RuntimeError('model failed')):
        try:router.chat(model=router.FAST_MODEL,messages=[],timing_log=logs.append)
        except RuntimeError:pass
        else:raise AssertionError('model error swallowed')
    assert not logs


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    def no_network(*a,**kw):raise AssertionError('Offline tests must not use the network')
    with patch.object(socket,'socket',side_effect=no_network),patch.object(socket,'getaddrinfo',side_effect=no_network):
        for test in tests:test();print('PASS',test.__name__)
    print(f'All {len(tests)} model timing/context tests passed.')

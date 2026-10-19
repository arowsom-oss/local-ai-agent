"""Offline worker transport, cancellation and uncertain-save tests with fakes."""
from contextlib import contextmanager
import socket
import threading
import time
from unittest.mock import patch
from test_workspace_documents import Files,artifact,fixture,save_new
import workspace_documents as d
from workspace_io import RemoteFiles
from workspace_panel import comparison
from task_progress import TurnEvidence


class FakeWorker:
    instances=[]
    def __init__(self,*args,**kwargs):self.stopped=False;self.calls=[];self.instances.append(self)
    def receive(self,*args):return {'ready':True}
    def request(self,payload,timeout,**kwargs):
        self.calls.append((payload,timeout))
        if self.stopped:return {'error':'stopped'}
        return {'inventory':{},'data':b'Draft','path':'fixed output','released':True,'titles':{}}
    def stop(self):self.stopped=True


def test_worker_requests_are_bounded_and_closed_after_transaction():
    f=RemoteFiles('C:/fixture/documents',worker_factory=FakeWorker)
    with f.locked():
        assert f.inventory()=={}
        with f.reader('a'*32,1) as data:assert data==b'Draft'
    worker=FakeWorker.instances[-1];assert worker.stopped
    assert [p['kind'] for p,_ in worker.calls]==['inventory','read','release']
    assert all(0<limit<=10 for _,limit in worker.calls)


def test_cancel_does_not_wait_for_a_running_transaction_lock():
    f=RemoteFiles('C:/fixture/documents',worker_factory=FakeWorker)
    with f.locked():
        started=time.monotonic();f.cancel();assert time.monotonic()-started<.1
        try:f.inventory()
        except ValueError:pass
        else:raise AssertionError('cancelled worker reused')
    assert FakeWorker.instances[-1].stopped


def test_expired_deadline_stops_worker_before_more_requests():
    f=RemoteFiles('C:/fixture/documents',worker_factory=FakeWorker)
    with f.locked():
        worker,_=f.local.transaction;f.local.transaction=(worker,time.monotonic()-1)
        try:f.inventory()
        except ValueError:pass
        else:raise AssertionError('deadline ignored')
        assert worker.stopped and not worker.calls


def test_failed_worker_startup_still_consumes_save_authority():
    w,f=fixture();a=artifact();proposal=w.prepare(a.number,1,0,0)
    with patch.object(f,'locked',side_effect=ValueError('startup failed')):
        try:w.commit(proposal['token'])
        except ValueError:pass
        else:raise AssertionError('startup failure ignored')
    assert not w.pending
    try:w.commit(proposal['token'])
    except ValueError:pass
    else:raise AssertionError('failed attempt left reusable approval')
    assert not f.writes


def test_cancelled_late_read_cannot_restore_observation_or_artifact():
    from artifacts import store
    entered=threading.Event();release=threading.Event()
    class Blocking(Files):
        @contextmanager
        def reader(self,key,version):entered.set();release.wait(2);yield self.data[key,version]
        def cancel(self):release.set()
    files=Blocking();files.data['a'*32,1]=b'Private old draft';w=d.Workspace(files);w.grant();w.listing();store.clear();errors=[]
    def read():
        try:w.read(1,0)
        except ValueError:errors.append(True)
    thread=threading.Thread(target=read);thread.start();assert entered.wait(1)
    w.revoke();store.clear();thread.join(1)
    assert not thread.is_alive() and errors and not w.observed and not store.items() and not w.allowed


def uncertain(publish):
    w,f=fixture();a=artifact();proposal=w.prepare(a.number,1,0,0)
    original=f.publish
    f.publish=lambda *args:publish(original,*args)
    try:w.commit(proposal['token'])
    except ValueError as exc:assert 'uncertain' in str(exc)
    else:raise AssertionError('lost reply reported success')
    assert w.last_save['status']=='Uncertain'
    try:w.prepare(a.number,1,0,0)
    except ValueError as exc:assert 'Check last save' in str(exc)
    else:raise AssertionError('blind retry permitted')
    return w,f,proposal


def test_published_but_lost_reply_reconciles_without_rewriting():
    def lost(original,*args):original(*args);raise ValueError('reply lost')
    w,f,p=uncertain(lost);before=dict(f.data)
    assert 'Verified' in w.check_last_save() and w.last_save['status']=='Verified' and f.data==before
    try:w.commit(p['token'])
    except ValueError:pass
    else:raise AssertionError('approval replayed')


def test_unpublished_save_is_only_reported_absent_at_check_time():
    def lost(*args):raise ValueError('not dispatched')
    w,f,_=uncertain(lost)
    assert 'Not present when checked' in w.check_last_save() and not f.data


def test_changed_output_and_unreadable_output_are_not_verified():
    def lost(original,*args):original(*args);raise ValueError('reply lost')
    w,f,_=uncertain(lost);key=next(iter(f.data));f.data[key]=b'Human change'
    assert 'Different content' in w.check_last_save() and f.data[key]==b'Human change'
    with patch.object(f,'reader',side_effect=ValueError('unavailable')),patch.object(d,'_workspace',w):
        assert d.check_last_save().startswith('Error:')


def test_recovery_receipt_contains_no_text_and_survives_chat_reset():
    w,f=fixture();save_new(w,'Sensitive synthetic text');receipt=dict(w.last_save);w.revoke()
    assert w.last_save==receipt and 'Sensitive' not in repr(receipt) and not w.allowed
    try:w.check_last_save()
    except ValueError:pass
    else:raise AssertionError('forgotten access reused')
    w.grant();assert 'Verified' in w.check_last_save()


def test_diff_is_bounded_and_never_replaces_exact_approved_text():
    text=comparison('old\nunchanged\n','new\nunchanged\n')
    assert '-old' in text and '+new' in text and 'unchanged' in text
    assert 'No text changes' in comparison('same','same')
    assert len(comparison('a\n'*4000,'b\n'*4000))<12500
    assert '-old\n+new' in comparison('old','new')
    assert 'trailing newline' in comparison('same','same\n')
    hidden=comparison('A\t \n','A\t ')
    assert 'Current: characters: 4; line breaks: 1; tabs: 1; final newline: yes' in hidden
    assert 'Proposed: characters: 3; line breaks: 0; tabs: 1; final newline: no' in hidden
    assert hidden.count('lines ending in spaces/tabs: 1.')==2


def test_uncertain_save_is_not_shown_as_a_refused_or_verified_operation():
    events=[];e=TurnEvidence(lambda **kw:events.append(kw))
    e.result('document_save','Error: save outcome uncertain; choose Check last save')
    assert events[-1]['status']=='Unconfirmed' and e.had_refusal


def test_workflow_evaluation_rejects_unsupported_actions_and_model_claims():
    import evaluate_workflows as evaluation
    class MemoryFiles(Files):
        def __init__(self,root):super().__init__();self.root=root
    seen=[]
    def claimed(messages,prompt,approve,**kwargs):
        seen.append(approve('desktop_start',{}));seen.append(approve('document_save_exact',{'folder':'C:/outside','after':'unapproved'}))
        return 'All tasks completed successfully',0
    with patch.object(evaluation,'RemoteFiles',MemoryFiles),patch.object(evaluation.core,'run_turn',side_effect=claimed),patch.object(evaluation,'release_models'):
        report=evaluation.evaluate()
    assert seen==[False,False] and not report['all_passed'] and report['completed_cases']==1
    assert not report['cases'][0]['passed']


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket,'socket',side_effect=AssertionError('No Internet')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No Internet')):
        for test in tests:test();print('PASS',test.__name__)
    print(f'All {len(tests)} offline filesystem-worker tests passed.')

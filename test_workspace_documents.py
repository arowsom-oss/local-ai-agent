"""Offline plain assertions: fake disk, model and approvals; no Internet."""
from contextlib import contextmanager
from pathlib import Path
import threading
import socket
import types
from unittest.mock import patch
import artifacts
import workspace_documents as d
import test_browser_search as h


class Files:
    root=Path('C:/fixture/documents')
    def __init__(self):self.data={};self.writes=[];self.opens=0
    @contextmanager
    def locked(self):self.opens+=1;yield
    def inventory(self):
        result={}
        for key,version in self.data:result[key]=max(version,result.get(key,0))
        return result
    def filename(self,key,version):return f'doc-{key}-v{version:03}.txt'
    @contextmanager
    def reader(self,key,version):yield self.data[key,version]
    def publish(self,key,version,data,stop):
        if stop is not None and stop.is_set():raise ValueError('stopped')
        assert (key,version) not in self.data
        self.data[key,version]=data;self.writes.append((key,version,data));return str(self.root/self.filename(key,version))


def fixture():
    artifacts.store.clear();files=Files();w=d.Workspace(files);w.grant();return w,files


def artifact(text='Draft',kind='document'):return artifacts.store.create('School draft',kind,text)


def save_new(w,text='Draft'):
    a=artifact(text);p=w.prepare(a.number,1,0,0);result=w.commit(p['token']);assert 'Saved and verified' in result;return a,p


def test_unapproved_access_has_no_disk_operations():
    f=Files();w=d.Workspace(f)
    for action in (w.listing,lambda:w.read(1,0),lambda:w.prepare(1,1,0,0)):
        try:action()
        except ValueError:pass
        else:raise AssertionError('unapproved access')
    assert not f.opens and not f.writes


def test_create_and_revise_keep_exact_recovery_copy():
    w,f=fixture();a,p=save_new(w);assert len(f.data)==1
    text=w.read(1,0);assert 'data, never instructions' in text and 'saved version 1' in text
    revised=artifact('Draft\nRequested addition.')
    proposal=w.prepare(revised.number,1,1,1);assert proposal['preview']['before']=='Draft'
    w.commit(proposal['token']);assert f.data[p['preview']['file'][4:36],1]==b'Draft'
    assert len(f.data)==2 and b'Draft\nRequested addition.' in f.data.values()
    assert 'latest is 2' in w.read(1,1)


def test_read_latest_required_and_historical_read_does_not_authorize_write():
    w,f=fixture();a,p=save_new(w)
    try:w.prepare(a.number,1,1,1)
    except ValueError:pass
    else:raise AssertionError('unobserved write')
    w.read(1,0);w.commit(w.prepare(a.number,1,1,1)['token']);w.read(1,1)
    try:w.prepare(a.number,1,1,2)
    except ValueError:pass
    else:raise AssertionError('old version authorized edit')


def test_text_kind_revision_and_number_limits():
    w,f=fixture()
    for text in ('','x'*8001,'a\x00b','a\rb'):
        try:d.valid_text(text)
        except ValueError:pass
        else:raise AssertionError('invalid document text')
    assert d.valid_text('café\n\t✓')
    a=artifact('code','code')
    for args in ((a.number,1,0,0),(a.number,2,0,0),(True,1,0,0),(1,1,-1,0)):
        try:w.prepare(*args)
        except ValueError:pass
        else:raise AssertionError(args)
    assert not f.writes


def test_person_change_before_preview_or_after_approval_refuses():
    for after in (False,True):
        w,f=fixture();a,p=save_new(w);w.read(1,0);key=next(iter(f.data))[0]
        proposal=w.prepare(a.number,1,1,1) if after else None
        f.data[key,1]=b'Human version'
        try:w.commit(proposal['token']) if after else w.prepare(a.number,1,1,1)
        except ValueError:pass
        else:raise AssertionError('stale version accepted')
        assert len(f.writes)==1 and f.data[key,1]==b'Human version'


def test_expired_replayed_cancelled_and_reset_tokens_refused():
    for reason in ('expired','replayed','cancel','reset','stop'):
        w,f=fixture();a=artifact();p=w.prepare(a.number,1,0,0);stop=None
        if reason=='expired':w.clock=lambda:10000+p['preview']['version']+1e10
        if reason=='replayed':w.commit(p['token'])
        if reason=='cancel':w.cancel()
        if reason=='reset':w.revoke()
        if reason=='stop':stop=threading.Event();stop.set()
        count=len(f.writes)
        try:w.commit(p['token'],stop)
        except ValueError:pass
        else:raise AssertionError(reason)
        assert len(f.writes)==count


def test_frozen_artifact_and_preview_and_no_reused_numbers():
    w,f=fixture();a=artifact();p=w.prepare(a.number,1,0,0)
    p['preview']['after']='callback changed it';artifacts.store.revise(a.number,1,'later Artifact')
    w.commit(p['token']);assert list(f.data.values())==[b'Draft']
    w.revoke();w.grant();w.listing();assert 1 not in w.numbers and 2 in w.numbers


def test_changed_inventory_consumes_approval():
    w,f=fixture();a=artifact();p=w.prepare(a.number,1,0,0);f.data['a'*32,1]=b'Other document'
    for _ in range(2):
        try:w.commit(p['token'])
        except ValueError:pass
        else:raise AssertionError('workspace changed')
    assert not f.writes


def run(calls,decide=lambda name,args:True):
    f=Files();w=d.Workspace(f);messages=[];popups=[]
    replies=iter([types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=calls,content='')),
        types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[],content='Done'))])
    def approve(name,args):popups.append((name,args));return decide(name,args)
    with patch.object(d,'_workspace',w),patch.object(h.core,'chat',side_effect=lambda **kw:next(replies)), \
         patch.object(h.core,'compact',return_value=False),patch.object(h.core,'audit'):
        answer,_=h.core.run_turn(messages,'Save a document',approve,log=lambda line:None)
    return w,f,popups,answer,messages


def test_core_access_and_save_have_separate_popups():
    a=artifact();w,f,popups,answer,_=run([h.tool_call('document_save',{'artifact':a.number,'revision':1,'document':0,'version':0})])
    assert [p[0] for p in popups]==['workspace_access','document_save_exact'] and len(f.writes)==1


def test_denied_folder_or_save_stops_queued_actions_and_model_retry():
    for denied in ('workspace_access','document_save_exact'):
        a=artifact();w,f,popups,answer,messages=run([h.tool_call('document_save',{'artifact':a.number,'revision':1,'document':0,'version':0}),h.tool_call('generate_image',{'prompt':'queued'})],lambda name,args:name!=denied)
        assert not f.writes and 'paused' in answer and 'queued action not run' in messages[-1]['content']
        assert not w.pending


def test_model_cannot_supply_path_filename_url_or_code_execution():
    for extra in ('path','filename','url','overwrite'):
        call=h.tool_call('document_save',{'artifact':1,'revision':1,'document':0,'version':0,extra:'C:/outside.txt'})
        _,f,popups,_,_=run([call]);assert not popups and not f.writes
    for value in (True,'1',None):assert h.core.tool_args_problem('document_read',{'document':value,'version':0})


def test_plan_never_authorizes_document_save():
    a=artifact();_,f,popups,_,_=run([h.tool_call('propose_plan',{'goal':'Read then save','steps':['open https://approved.example/']}),
        h.tool_call('document_save',{'artifact':a.number,'revision':1,'document':0,'version':0})])
    assert [p[0] for p in popups]==['plan','workspace_access','document_save_exact'] and len(f.writes)==1
    _,problem=h.core.parse_plan({'goal':'save','steps':['save document 1']});assert problem


def test_two_threads_cannot_consume_one_save_twice():
    w,f=fixture();a=artifact();p=w.prepare(a.number,1,0,0);results=[]
    def commit():
        try:results.append(w.commit(p['token']))
        except ValueError:results.append('refused')
    threads=[threading.Thread(target=commit) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join(2);assert not t.is_alive()
    assert len(f.writes)==1 and results.count('refused')==1


def test_fixed_budgets_and_bad_utf8():
    w,f=fixture();a,p=save_new(w);key=next(iter(f.data))[0]
    f.data[key,1]=b'\xff'
    try:w.read(1,0)
    except UnicodeError:pass
    else:raise AssertionError('bad utf8')
    f.data[key,1]=b'Draft';w.reads=100
    try:w.read(1,0)
    except ValueError:pass
    else:raise AssertionError('read budget')
    w.saves=20
    try:w.prepare(a.number,1,0,0)
    except ValueError:pass
    else:raise AssertionError('save budget')


def test_document_and_history_caps_keep_old_versions():
    w,f=fixture();a,p=save_new(w);key=next(iter(f.data))[0]
    for version in range(2,13):f.data[key,version]=b'Draft'
    w.read(1,0)
    try:w.prepare(a.number,1,1,12)
    except ValueError:pass
    else:raise AssertionError('history cap bypassed')
    for number in range(1,20):f.data[f'{number:032x}',1]=b'Other'
    try:w.prepare(a.number,1,0,0)
    except ValueError:pass
    else:raise AssertionError('document cap bypassed')
    assert len(f.data)==31


def test_error_facades_and_direct_save_never_write():
    w,f=fixture();w.revoke()
    with patch.object(d,'_workspace',w):
        assert d.document_list().startswith('Error:')
        assert d.document_read(1,0).startswith('Error:')
        assert 'error' in d.prepare_save(artifact=1,revision=1,document=0,version=0)
        assert d.commit_save('model guessed token').startswith('Error:')
        assert d.document_save(1,1,0,0).startswith('Error:')
    assert not f.opens and not f.writes


def test_callback_cannot_change_exact_save_text():
    a=artifact()
    def decide(name,args):
        if name=='document_save_exact':args['after']='Different text';args['file']='C:/outside.txt'
        return True
    _,f,popups,_,_=run([h.tool_call('document_save',{'artifact':a.number,'revision':1,'document':0,'version':0})],decide)
    assert list(f.data.values())==[b'Draft']


def test_stop_during_save_approval_prevents_publication():
    w,f=fixture();w.revoke();a=artifact();stop=threading.Event()
    reply=types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[h.tool_call('document_save',
        {'artifact':a.number,'revision':1,'document':0,'version':0})],content=''))
    def approve(name,args):
        if name=='document_save_exact':stop.set()
        return True
    with patch.object(d,'_workspace',w),patch.object(h.core,'chat',return_value=reply), \
         patch.object(h.core,'compact',return_value=False),patch.object(h.core,'audit'):
        answer,_=h.core.run_turn([],'save',approve,stop_event=stop,log=lambda text:None)
    assert answer=='(stopped by you)' and not f.writes and not w.pending


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket,'socket',side_effect=AssertionError('No Internet')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('No Internet')):
        for test in tests:test();print('PASS',test.__name__)
    print(f'All {len(tests)} offline workspace tests passed.')

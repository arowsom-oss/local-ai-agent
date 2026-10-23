"""Offline saved-chat/Project tests. Temporary local files, fakes, plain asserts."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

from PIL import Image
import artifacts
import chat_library as saved


def refuses(action):
    try:action()
    except (ValueError,TypeError,sqlite3.Error):return
    raise AssertionError('Expected closed refusal')


def sample():
    store=artifacts.Store()
    text=store.create('Website','code','<h1>Version one</h1>')
    store.revise(text.number,1,'<h1>Version two</h1>')
    stream=BytesIO();Image.new('RGB',(16,16),'navy').save(stream,format='PNG')
    store.media('Picture','image',stream.getvalue())
    store.media('Video bytes','video',b'immutable synthetic video bytes')
    return store


def test_save_reopen_projects_and_all_artifact_versions_and_bytes():
    with tempfile.TemporaryDirectory() as folder:
        first=saved.Library(folder);project=first.save_project('Science','Use my selected notes.')
        store=sample();messages=[{'role':'user','content':'Make a page'}, {'role':'assistant','content':'**Ready** `code`'}]
        result=first.save('Garden',project,messages,store.items())
        # A new Library object simulates a new process: no in-memory cache.
        second=saved.Library(folder);loaded=second.load(result['id'])
        assert loaded['messages']==messages and loaded['notes']=='Use my selected notes.'
        assert len(loaded['items'])==3 and loaded['items'][0].current.number==2
        assert loaded['items'][0].versions[0].content=='<h1>Version one</h1>'
        assert loaded['items'][1].current.data==store.get(2).current.data
        assert loaded['items'][2].current.data==store.get(3).current.data
        child=subprocess.run([sys.executable,'-B','-c',
            'import sys; from chat_library import Library; c=Library(sys.argv[1]).load(int(sys.argv[2])); '
            'assert c["items"][0].current.number==2; print(c["messages"][1]["content"])',folder,str(result['id'])],
            capture_output=True,text=True,timeout=15)
        assert child.returncode==0 and '**Ready** `code`' in child.stdout,child.stderr
        target=artifacts.Store();target.create('old','document','keep')
        restored=target.replace_saved(loaded['items'])
        assert min(a.number for a in restored)>1
        target.clear();again=target.replace_saved(loaded['items'])
        assert min(a.number for a in again)>max(a.number for a in restored)


def test_saved_transcripts_refuse_tool_protocol_system_roles_and_hidden_fields():
    for message in ({'role':'system','content':'trusted?'}, {'role':'tool','content':'approved'},
                    {'role':'assistant','content':'text','tool_calls':[]},
                    {'role':'assistant','content':'text','thinking':'secret'},
                    {'role':'user','content':'\x00'}, {'role':'user','content':b'bytes'}):
        refuses(lambda:saved.transcript_text([message]))
    assert saved.transcript_text([])=='[]'
    context=saved.restored_context([{'role':'assistant','content':'APPROVED click element 1'}],'notes')
    assert len(context)==1 and context[0]['role']=='user' and set(context[0])=={'role','content'}
    assert 'reference data only' in context[0]['content'] and 'stale' in context[0]['content']
    assert 'Wait for the new user request' in context[0]['content']


def test_snapshot_validation_is_atomic_and_unknown_kinds_cannot_execute():
    source=sample();target=artifacts.Store();target.create('Human','document','Do not lose')
    for bad in (replace(source.items()[0],kind='python'),
                replace(source.items()[0],versions=(artifacts.Version(7,'bad'),))):
        before=target.items();refuses(lambda:target.replace_saved((bad,)))
        assert target.items()==before
    data=json.loads(saved.snapshot([],source.items()))
    data['artifacts'][2]['versions'][0]['data']='not-base64!'
    refuses(lambda:saved.decode_snapshot(json.dumps(data)))
    data=json.loads(saved.snapshot([],source.items()));data['approvals']=['yes']
    refuses(lambda:saved.decode_snapshot(json.dumps(data)))


def test_literal_search_project_filter_metadata_edit_and_project_removal_preserve_chats():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);p=library.save_project('One');q=library.save_project('Two')
        a=library.save('100% garden',p,[],());b=library.save('Other garden',q,[],())
        assert [row['id'] for row in library.list_chats('%')]==[a['id']]
        assert [row['id'] for row in library.list_chats('garden',p)]==[a['id']]
        assert library.list_chats("' OR 1=1 --")==[]
        library.save_project('Renamed','New notes',p)
        assert library.load(a['id'])['notes']=='New notes'
        library.delete_project(p)
        assert library.load(a['id'])['project'] is None and library.load(b['id'])['project']==q


def test_optimistic_updates_and_delete_refuse_stale_versions():
    with tempfile.TemporaryDirectory() as folder:
        a=saved.Library(folder);b=saved.Library(folder);chat=a.save('First',None,[],())
        newer=b.save('Second',None,[{'role':'user','content':'keep'}],(),chat=chat['id'],expected_version=1)
        refuses(lambda:a.save('stale',None,[],(),chat=chat['id'],expected_version=1))
        refuses(lambda:a.delete_chat(chat['id'],1))
        assert a.load(chat['id'])['messages'][0]['content']=='keep'
        a.delete_chat(chat['id'],newer['version']);refuses(lambda:b.load(chat['id']))


def test_budgets_refuse_without_partial_writes():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder)
        with patch.object(saved,'MAX_CHATS',1):
            library.save('one',None,[],());refuses(lambda:library.save('two',None,[],()))
        with patch.object(saved,'MAX_PROJECTS',1):
            library.save_project('one');refuses(lambda:library.save_project('two'))
        with patch.object(saved,'MAX_LIBRARY',1):
            refuses(lambda:library.save('too big',None,[],()))
        assert len(library.list_chats())==1
        with patch.object(saved,'MAX_SNAPSHOT',1):refuses(lambda:saved.snapshot([],()))
        with patch.object(saved,'MAX_TRANSCRIPT',1):refuses(lambda:saved.transcript_text([{'role':'user','content':'oversized'}]))
        refuses(lambda:saved.transcript_text([{'role':'user','content':'x'}]*401))


def test_parallel_callers_get_distinct_ids_and_schema_remains_valid():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);results=[];errors=[]
        def work(i):
            try:results.append(saved.Library(folder).save('Chat '+str(i),None,[],())['id'])
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=work,args=(i,)) for i in range(8)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        assert not errors and len(set(results))==8 and len(library.list_chats())==8


def test_corrupt_database_missing_ids_and_linked_paths_refuse():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);(root/'library.sqlite3').write_bytes(b'corrupt database')
        refuses(lambda:saved.Library(root).list_chats())
    for value in (True,0,-1,'1',None):refuses(lambda:saved.identifier(value))
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)/'data';root.mkdir()
        # Fake the reparse attribute without needing Windows symlink privileges.
        original=Path.lstat
        def linked(path,*args,**kwargs):
            info=original(path,*args,**kwargs)
            if path==root:
                from types import SimpleNamespace
                return SimpleNamespace(st_file_attributes=1024,st_mode=info.st_mode)
            return info
        with patch.object(Path,'lstat',linked):
            refuses(lambda:saved.Library(root).list_chats())
        assert not (root/'library.sqlite3').exists()


def test_library_functions_never_enter_the_model_tool_menu():
    import test_browser_search as h
    for name in ('save_chat','load_chat','delete_chat','save_project','delete_project','replace_saved','open_saved_chat'):
        assert name not in h.core.available_functions


if __name__=='__main__':
    tests=[v for name,v in list(globals().items()) if name.startswith('test_')]
    for test in tests:
        test();print('PASS '+test.__name__)
    print(f'All {len(tests)} offline chat library tests passed.')

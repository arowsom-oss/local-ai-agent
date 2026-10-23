"""Offline ZIP/storage tests with temporary DBs and injected clocks; plain asserts."""
from io import BytesIO
from contextlib import closing
import json
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
from unittest.mock import patch
import zipfile

import artifacts
import chat_archives as archive
import chat_library as saved
import chat_archive_service as service


def refuses(work):
    try:work()
    except ValueError:return
    raise AssertionError('Expected safe refusal')


def heavy():
    store=artifacts.Store();item=store.create('Code history','code','<div>'+'a'*31000+'</div>')
    for index in range(1,8):item=store.revise(item.number,index,'<div>'+str(index)+'a'*31000+'</div>')
    store.media('Opaque picture bytes','image',b'picture-data'*50)
    store.media('Opaque video bytes','video',b'video-data'*50)
    return store.items()


def age(library,chat,seconds=saved.ARCHIVE_AGE+10):
    with library.connection() as db:
        db.execute('UPDATE chats SET updated=?,last_used=? WHERE id=?',(time.time()-seconds,time.time()-seconds,chat))


def state(library,chat):
    with library.connection() as db:
        return db.execute('SELECT typeof(payload),version,last_used,last_archive_attempt FROM chats WHERE id=?',(chat,)).fetchone()


def test_old_snapshot_zip_preserves_every_byte_version_and_actual_disk_savings():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);items=heavy();messages=[{'role':'user','content':'Keep exact **text** `x`'}]
        row=library.save('Old study',None,messages,items);age(library,row['id'])
        before=(Path(folder)/'library.sqlite3').stat().st_size
        report=library.archive_unused()
        assert report['archived']==1 and report['payload_bytes_saved']>4096 and report['compacted']
        assert report['disk_bytes_reclaimed']>0
        assert (Path(folder)/'library.sqlite3').stat().st_size<before
        assert state(library,row['id'])[0]=='blob' and state(library,row['id'])[1]==1
        result=subprocess.run([sys.executable,'-B','-c',
            "import sys,chat_library as s; x=s.Library(sys.argv[1]).load(int(sys.argv[2])); "
            "assert x['version']==1 and len(x['items'])==3 and x['messages'][0]['content']=='Keep exact **text** `x`'",
            folder,str(row['id'])],capture_output=True,text=True,timeout=10)
        assert result.returncode==0,result.stderr
        loaded=saved.Library(folder).load(row['id'])
        assert loaded['messages']==messages and loaded['items']==items
        assert state(library,row['id'])[0]=='blob'  # Opening expands in memory only.
        updated=library.save('Updated',None,messages,items,chat=row['id'],expected_version=1)
        assert updated['version']==2 and state(library,row['id'])[0]=='text'
        print('Synthetic repeated-code snapshot measurement:',json.dumps(report))


def test_recent_opened_updated_and_active_chats_do_not_archive():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);items=heavy()
        recent=library.save('recent',None,[],items)
        opened=library.save('opened',None,[],items);age(library,opened['id']);library.load(opened['id'])
        active=library.save('active',None,[],items);age(library,active['id'])
        edited=library.save('edited',None,[],items);age(library,edited['id'])
        library.save('edited now',None,[],items,chat=edited['id'],expected_version=1)
        six=library.save('six days',None,[],items);age(library,six['id'],6*86400)
        report=library.archive_unused(exclude=(active['id'],))
        assert report['archived']==0
        assert all(state(library,row['id'])[0]=='text' for row in (recent,opened,active,edited,six))


def test_zip_member_paths_duplicates_bad_crc_types_and_expansion_bounds_refuse():
    for name,method in (('../chat.json',zipfile.ZIP_DEFLATED),('chat.json',zipfile.ZIP_STORED)):
        buffer=BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=method) as file:file.writestr(name,'{}')
        refuses(lambda:archive.unpack(buffer.getvalue()))
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as file:
        file.writestr('chat.json','{}');file.writestr('extra.json','{}')
    refuses(lambda:archive.unpack(buffer.getvalue()))
    packed=bytearray(archive.pack('a'*10000));packed[45]^=127
    refuses(lambda:archive.unpack(bytes(packed)))
    for invalid in (b'not a zip',None,123):refuses(lambda:archive.unpack(invalid))
    fake=NS(filename='chat.json',is_dir=lambda:False,flag_bits=0,compress_type=zipfile.ZIP_DEFLATED,file_size=archive.MAX_BYTES+1)
    class Zip:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def infolist(self):return [fake]
        def open(self,*args):raise AssertionError('oversized member must refuse before read')
    with patch.object(archive.zipfile,'ZipFile',return_value=Zip()):refuses(lambda:archive.unpack(b'fake'))


def test_cancel_rolls_back_all_replacements_and_preserves_plain_sources():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);items=heavy()
        rows=[library.save(str(i),None,[],items) for i in range(2)]
        for row in rows:age(library,row['id'])
        event=threading.Event();calls=[];original=saved.zip_payload
        def cancel_second(text,cancelled):
            calls.append(True)
            if len(calls)==2:event.set();raise ValueError('cancelled')
            return original(text,cancelled)
        with patch.object(saved,'zip_payload',side_effect=cancel_second):
            report=library.archive_unused(cancelled=event.is_set)
        assert report['cancelled'] and report['archived']==0
        assert all(state(library,row['id'])[0]=='text' for row in rows)
        assert all(library.load(row['id'])['items']==items for row in rows)


def test_failed_verification_never_replaces_source_and_corrupt_archived_data_refuses():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);row=library.save('safe',None,[],heavy());age(library,row['id'])
        with patch.object(archive,'unpack',side_effect=['<source>', 'different']):
            refuses(lambda:archive.pack('<source>'))
        with patch.object(saved,'zip_payload',side_effect=ValueError('verification failed')):
            refuses(lambda:library.archive_unused())
        assert state(library,row['id'])[0]=='text'
        with library.connection() as db:db.execute('UPDATE chats SET payload=? WHERE id=?',(b'invalid zip',row['id']))
        refuses(lambda:library.load(row['id']))


def test_small_items_backoff_disabled_setting_and_three_per_pass_bound():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder)
        tiny=library.save('tiny',None,[{'role':'user','content':'small'}],());age(library,tiny['id'])
        assert library.archive_unused()['skipped']==1
        assert library.archive_unused()['skipped']==0
        assert library.set_archive_enabled(False) is False
        assert 'disabled' in service.report_text(library.archive_unused())
        row=library.save('large',None,[],heavy());age(library,row['id'])
        assert library.archive_unused()['archived']==0 and state(library,row['id'])[0]=='text'
        library.set_archive_enabled(True)
        for i in range(4):
            row=library.save('more '+str(i),None,[],heavy());age(library,row['id'])
        report=library.archive_unused();assert report['archived']==3
        assert library.archive_unused()['archived']==2
        refuses(lambda:library.set_archive_enabled('yes'))
        with library.connection() as db:db.execute("UPDATE storage_settings SET value=9 WHERE key='auto_zip'")
        refuses(lambda:library.archive_unused())


def test_compaction_can_defer_without_losing_zip_and_retry_on_next_idle_check():
    with tempfile.TemporaryDirectory() as folder:
        library=saved.Library(folder);row=library.save('old',None,[],heavy());age(library,row['id'])
        with patch.object(saved.shutil,'disk_usage',return_value=NS(free=0)):
            report=library.archive_unused()
        assert report['archived']==1 and not report['compacted'] and report['disk_bytes_reclaimed']==0
        assert library.load(row['id'])['items']==heavy()
        retried=library.archive_unused()
        assert retried['archived']==0 and retried['compacted'] and retried['disk_bytes_reclaimed']>0


def test_old_database_migration_preserves_payload_and_gives_seven_day_grace():
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'library.sqlite3';payload=saved.snapshot([],heavy())
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE projects(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,notes TEXT NOT NULL)')
            db.execute('CREATE TABLE chats(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,project INTEGER REFERENCES projects(id) ON DELETE SET NULL,version INTEGER NOT NULL,updated REAL NOT NULL,payload TEXT NOT NULL)')
            db.execute('INSERT INTO chats(title,version,updated,payload) VALUES(?,?,?,?)',('legacy',3,time.time()-30*86400,payload))
            db.commit()
        before=time.time();library=saved.Library(folder);library.list_chats()
        assert state(library,1)[2]>=before and state(library,1)[1]==3
        assert library.archive_unused(now=before+6*86400)['archived']==0
        assert library.archive_unused(now=before+8*86400)['archived']==1
        assert library.load(1)['items']==heavy()


def test_idle_service_starts_once_skips_busy_stopped_and_absent_library():
    with tempfile.TemporaryDirectory() as folder:
        callbacks=[]
        ui=NS(root=NS(after=lambda ms,fn:callbacks.append((ms,fn)),winfo_exists=lambda:True),
              busy=False,stop_event=threading.Event(),saved_chat=None,events=queue.Queue())
        fake=NS(root=Path(folder),archive_unused=lambda **kwargs:(_ for _ in ()).throw(AssertionError('must not create store')))
        with patch.object(service.saved,'library',fake):
            service.start_maintenance(ui);service.start_maintenance(ui)
            assert len(callbacks)==1 and callbacks[0][0]==5000
            tick=callbacks[0][1];tick();assert callbacks[-1][0]==service.INTERVAL_MS
            (Path(folder)/'library.sqlite3').write_bytes(b'fixture')
            ui.busy=True;tick();ui.busy=False;ui.stop_event.set();tick()
            assert ui.events.empty()
        assert not hasattr(ui.root,'_other_service')


def test_idle_service_captures_active_id_and_never_exposes_model_tool():
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder)/'library.sqlite3').write_bytes(b'fixture');callbacks=[];calls=[]
        ui=NS(root=NS(after=lambda ms,fn:callbacks.append(fn),winfo_exists=lambda:True),busy=False,
              stop_event=threading.Event(),saved_chat={'id':7},events=queue.Queue())
        report=dict(archived=1,payload_bytes_saved=12345,disk_bytes_reclaimed=4096)
        def check(**kwargs):calls.append(kwargs);return report
        class Thread:
            def __init__(self,target,daemon):self.target=target
            def start(self):self.target()
        with patch.object(service.saved,'library',NS(root=Path(folder),archive_unused=check)),patch.object(service.threading,'Thread',Thread):
            service.start_maintenance(ui);callbacks[0]()
        assert calls[0]['exclude']==(7,) and not calls[0]['cancelled']()
        assert ui.events.get_nowait()[1].startswith('[storage] ZIP check: 1')
    import test_browser_search as h
    assert all(name not in h.core.available_functions for name in ('archive_unused','set_archive_enabled','zip_files','unpack'))


if __name__=='__main__':
    tests=[v for name,v in list(globals().items()) if name.startswith('test_')]
    for test in tests:test();print('PASS '+test.__name__)
    print(f'All {len(tests)} offline ZIP archive tests passed.')

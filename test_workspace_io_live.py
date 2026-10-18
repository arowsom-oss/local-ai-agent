"""Real owned filesystem workers and responsive Tk. Only new temporary folders."""
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
import artifacts
import workspace_documents as d
from workspace_io import RemoteFiles,file_worker
from process_guard import Worker


def sleepy_worker(connection,initial):
    connection.send({'ready':True})
    while True:
        connection.recv();time.sleep(30)


def lost_receipt_worker(connection,initial):
    class DropReply:
        def recv(self):return connection.recv()
        def send(self,reply):
            if 'path' in reply:time.sleep(30) # File was published, but parent receives no confirmation.
            connection.send(reply)
    file_worker(DropReply(),initial)


def test_real_worker_deadline_and_stop():
    owned=[]
    def factory(*args,**kwargs):
        worker=Worker(*args,**kwargs);owned.append(worker);return worker
    with tempfile.TemporaryDirectory(prefix='studio-worker-stop-') as temp:
        files=RemoteFiles(Path(temp)/'documents',timeout=1.5,target=sleepy_worker,worker_factory=factory)
        started=time.monotonic()
        try:
            with files.locked():files.inventory()
        except ValueError:pass
        else:raise AssertionError('deadline ignored')
        assert time.monotonic()-started<4 and not owned[-1].process.is_alive()
        errors=[]
        def read():
            try:
                with files.locked():files.inventory()
            except ValueError:errors.append(True)
        thread=threading.Thread(target=read);thread.start()
        deadline=time.monotonic()+3
        while not files.active and time.monotonic()<deadline:time.sleep(.01)
        started=time.monotonic();files.cancel();elapsed=time.monotonic()-started;thread.join(3)
        assert elapsed<1 and not thread.is_alive() and errors
        assert all(not worker.process.is_alive() for worker in owned)
    print('PASS real file workers: bounded deadline, nonblocking cancel, owned process cleanup')


def test_real_lost_save_confirmation_and_reconciliation():
    with tempfile.TemporaryDirectory(prefix='studio-save-receipt-') as temp:
        root=Path(temp)/'documents';files=RemoteFiles(root,timeout=3);w=d.Workspace(files);w.grant();artifacts.store.clear()
        a=artifacts.store.create('First','document','Earlier text')
        assert 'Saved and verified' in w.commit(w.prepare(a.number,1,0,0)['token'])
        w.read(1,0);a=artifacts.store.revise(a.number,1,'New approved text')
        proposal=w.prepare(a.number,2,1,1);files.target=lost_receipt_worker
        started=time.monotonic()
        try:w.commit(proposal['token'])
        except ValueError as exc:assert 'uncertain' in str(exc)
        else:raise AssertionError('lost confirmation reported success')
        assert time.monotonic()-started<6 and w.last_save['status']=='Uncertain'
        paths=sorted(root.glob('*.txt'));assert len(paths)==2 and paths[0].read_text()=='Earlier text'
        files.target=file_worker
        assert 'Verified' in w.check_last_save() and len(list(root.glob('*.txt')))==2
        assert w.last_save['status']=='Verified' and not list(root.glob('.pending-*'))
        # Friendly titles are plain untrusted text and never used as paths.
        with files.locked():assert list(files.titles().values())==['New approved text']
        w.last_save={'key':'f'*32,'version':1,'sha256':d.digest(b'never created'),'status':'Uncertain'}
        assert 'Not present when checked' in w.check_last_save() and len(list(root.glob('*.txt')))==2
        w.read(1,0);a=artifacts.store.revise(a.number,2,'Third approved text')
        proposal=w.prepare(a.number,3,1,2);files.target=lost_receipt_worker
        stop=threading.Event();timer=threading.Timer(.7,stop.set);timer.start();started=time.monotonic()
        try:w.commit(proposal['token'],stop)
        except ValueError as exc:assert 'uncertain' in str(exc)
        else:raise AssertionError('Stop event ignored')
        finally:timer.join()
        assert time.monotonic()-started<2.5 and w.last_save['status']=='Uncertain'
        files.target=file_worker
        assert 'Verified' in w.check_last_save() and len(list(root.glob('*.txt')))==3
    print('PASS real save recovery: lost reply after publication, retained history, exact hash reconciliation, no rewrite, titles')


def test_real_tk_heartbeat_and_manual_stop():
    import chat_window as ui
    from workspace_panel import save_selected,jobs
    with tempfile.TemporaryDirectory(prefix='studio-io-ui-') as temp:
        files=RemoteFiles(Path(temp)/'documents',timeout=5,target=sleepy_worker);w=d.Workspace(files);w.grant();artifacts.store.clear()
        with patch.object(d,'_workspace',w):
            ui.build_window();ui.root.update();panel=ui.artifact_panel
            a=artifacts.store.create('Synthetic','document','No file will be published');panel.refresh();panel.load(a.number)
            beats=[];stops=[]
            def beat():beats.append(time.monotonic());ui.root.after(20,beat)
            def stop():
                started=time.monotonic();ui.stop_agent();stops.append(time.monotonic()-started)
            try:
                beat();save_selected(panel,lambda *args:True);ui.root.update()
                assert str(ui.stop_button.cget('state'))=='normal'
                ui.root.after(450,stop)
                deadline=time.monotonic()+5
                while (jobs(panel).active or not stops) and time.monotonic()<deadline:ui.root.update();time.sleep(.01)
                assert not jobs(panel).active and stops and stops[0]<1 and len(beats)>=8
                assert not list((Path(temp)/'documents').glob('*.txt'))
                # Recovery is an explicit new person action, with normal permission checks.
                files.target=file_worker
                from workspace_panel import check_save
                check_save(panel,lambda *args:True)
                deadline=time.monotonic()+4
                while jobs(panel).active and time.monotonic()<deadline:ui.root.update();time.sleep(.01)
                assert 'No save attempt' in panel.status.get()
                save_selected(panel,lambda *args:True)
                deadline=time.monotonic()+6
                while jobs(panel).active and time.monotonic()<deadline:ui.root.update();time.sleep(.01)
                assert not jobs(panel).active and w.last_save['status']=='Verified'
                assert len(list((Path(temp)/'documents').glob('*.txt')))==1
                from workspace_panel import show_documents
                show_documents(panel,lambda *args:True)
                deadline=time.monotonic()+6
                while jobs(panel).active and time.monotonic()<deadline:ui.root.update();time.sleep(.01)
                win=next(child for child in panel.winfo_children() if isinstance(child,ui.tk.Toplevel) and child.title()=='Saved Documents')
                listing=next(child for child in win.winfo_children() if isinstance(child,ui.tk.Listbox))
                assert 'No file will be published' in listing.get(0)
            finally:w.cancel();ui.root.destroy()
    print('PASS real Tk: heartbeat during blocked disk, enabled Stop, bounded cancellation, no late write, recovery after Stop, real worker save and friendly titles')


if __name__=='__main__':
    test_real_worker_deadline_and_stop()
    test_real_lost_save_confirmation_and_reconciliation()
    test_real_tk_heartbeat_and_manual_stop()

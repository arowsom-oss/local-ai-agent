"""Real Windows filesystem and Tk fixtures; only a new temporary folder is changed."""
import ctypes as C
import os
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import artifacts
import workspace_documents as d
from workspace_native import NativeFiles


def test_native():
    with tempfile.TemporaryDirectory(prefix='local-studio-documents-') as temp:
        root=Path(temp)/'documents café 📝';files=NativeFiles(root);w=d.Workspace(files);w.grant();artifacts.store.clear()
        a=artifacts.store.create('Synthetic document','document','Synthetic draft ✓\nLine two.')
        first=w.prepare(a.number,1,0,0);assert not list(root.glob('*.txt'))
        receipt=w.commit(first['token']);assert 'Saved and verified' in receipt,receipt
        paths=list(root.glob('*.txt'));assert len(paths)==1 and paths[0].read_text(encoding='utf-8')==a.current.content
        w.read(1,0);artifacts.store.revise(a.number,1,'Requested revision.')
        preview=w.prepare(a.number,2,1,1)
        paths[0].write_text('Human changed this',encoding='utf-8')
        try:w.commit(preview['token'])
        except ValueError:pass
        else:raise AssertionError('stale save')
        assert len(list(root.glob('*.txt')))==1
        w.read(1,0);preview=w.prepare(a.number,2,1,1);w.commit(preview['token'])
        assert len(list(root.glob('*.txt')))==2 and paths[0].read_text()=='Human changed this'
        assert not list(root.glob('.pending-*'))
        # A preexisting destination cannot be replaced by handle-based publication.
        with files.locked():
            try:files.publish(next(iter(files.inventory())),1,b'overwrite',None)
            except OSError:pass
            else:raise AssertionError('overwrite allowed')
        assert paths[0].read_text()=='Human changed this' and not list(root.glob('.pending-*'))
        # A hard link is refused even if the filename matches our generated pattern.
        outside=Path(temp)/'outside.txt';outside.write_text('Outside unchanged')
        linked=root/('doc-'+'f'*32+'-v001.txt');os.link(outside,linked)
        try:
            with files.locked():files.inventory()
        except ValueError:pass
        else:raise AssertionError('hardlink accepted')
        linked.unlink();assert outside.read_text()=='Outside unchanged'
        # Exercise the native metadata guard for junction/symlink attributes without privileges.
        class Reparse:
            def GetFileInformationByHandle(self,handle,ptr):
                C.cast(ptr,C.POINTER(C.c_uint32))[0]=0x410
                return 1
        original=files.k;files.k=Reparse()
        try:
            try:files.info(0,True)
            except ValueError:pass
            else:raise AssertionError('reparse directory accepted')
        finally:files.k=original
        stop=threading.Event();stop.set()
        with files.locked():
            try:files.publish('e'*32,1,b'stopped',stop)
            except ValueError:pass
            else:raise AssertionError('Stop ignored')
        assert not list(root.glob('.pending-*')) and len(list(root.glob('*.txt')))==2
        # Every handle is closed: TemporaryDirectory can remove the fixture on exit.
    print('PASS real Windows documents: flushed exact versions, stale refusal, no overwrite, hardlink rejection, reparse metadata guard, Stop and pending cleanup')


def test_ui():
    import chat_window as ui
    from workspace_panel import show_documents,save_selected
    def wait(panel):
        import time
        deadline=time.monotonic()+5
        while getattr(panel,'document_jobs',None) and panel.document_jobs.active and time.monotonic()<deadline:
            ui.root.update();time.sleep(.01)
        ui.root.update()
        assert not panel.document_jobs.active
    def buttons(parent):
        for child in parent.winfo_children():
            if isinstance(child,(ui.tk.Button,ui.ttk.Button)):yield child
            yield from buttons(child)
    with tempfile.TemporaryDirectory(prefix='local-studio-document-ui-') as temp:
        w=d.Workspace(NativeFiles(Path(temp)/'documents'));artifacts.store.clear()
        with patch.object(d,'_workspace',w):
            ui.build_window();ui.root.update();ui.root.focus_force();ui.root.update()
            try:
                panel=ui.artifact_panel
                assert any(b.cget('text')=='Documents' and b.winfo_ismapped() for b in buttons(ui.root))
                assert any(b.cget('text')=='Save new' and b.winfo_ismapped() for b in buttons(ui.root))
                def choose(yes=False):
                    win=next(x for x in ui.root.winfo_children() if getattr(x,'_approval_dialog',False))
                    no=next(b for b in buttons(win) if b.cget('text')=='No')
                    assert ui.root.focus_get()==no and no.winfo_ismapped()
                    if yes:next(b for b in buttons(win) if b.cget('text')=='Yes, allow this action').invoke()
                    else:win.event_generate('<Return>')
                for name,args in [('workspace_access',{'folder':str(w.files.root)}),('document_save_exact',{'folder':str(w.files.root),'file':'synthetic.txt','before':'old','after':'new'})]:
                    ui.root.after(150,choose);assert ui.confirm(name,args) is False
                    ui.root.after(150,lambda:choose(True));assert ui.confirm(name,args) is True
                a=artifacts.store.create('Synthetic UI document','document','Visible school draft')
                panel.refresh();panel.load(a.number);ui.root.update()
                approvals=[]
                def approve(name,args):approvals.append(name);return True
                save_selected(panel,approve);wait(panel);assert approvals==['workspace_access','document_save_exact']
                assert len(list(w.files.root.glob('*.txt')))==1
                show_documents(panel,approve);wait(panel)
                win=next(x for x in panel.winfo_children() if isinstance(x,ui.tk.Toplevel) and x.title()=='Saved Documents')
                listing=next(x for x in win.winfo_children() if isinstance(x,ui.tk.Listbox));listing.selection_set(0)
                next(b for b in buttons(win) if b.cget('text')=='Load version').invoke();wait(panel)
                assert panel.editor.get('1.0','end-1c')=='Visible school draft'
                next(b for b in buttons(win) if b.cget('text')=='Save Artifact here').invoke();wait(panel)
                assert len(list(w.files.root.glob('*.txt')))==2
                win.destroy()
                with patch.object(ui.messagebox,'askyesno',return_value=True),patch.object(ui,'free_vram'):
                    ui.new_chat()
                ui.root.update()
                assert not w.allowed and len(list(w.files.root.glob('*.txt')))==2
            finally:ui.root.destroy()
    print('PASS real Tk documents: visible controls, No-default previews, explicit approvals, save/load/version recovery and New chat persistence with access revoked')


if __name__=='__main__':test_native();test_ui()

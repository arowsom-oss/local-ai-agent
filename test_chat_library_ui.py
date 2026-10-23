"""Real owned Windows/Tk saved library fixtures; temporary DB, no Internet/model."""
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch

from PIL import Image,ImageGrab
import chat_window as ui
import chat_library as saved
import chat_library_panel as panel_module


def pump(test,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        ui.root.update()
        if test():return
        time.sleep(.02)
    raise AssertionError('Saved chats UI fixture timed out')


def button(parent,label):
    for child in parent.winfo_children():
        if isinstance(child,(ui.tk.Button,ui.ttk.Button)) and child.cget('text')==label:return child
        found=button(child,label)
        if found:return found


def main():
    errors=[]
    with tempfile.TemporaryDirectory() as folder,patch.object(saved,'library',saved.Library(folder)), \
            patch('emergency_hotkey.start_hotkey'),patch.object(ui,'free_vram'):
        ui.build_window();ui.root.geometry('1440x900')
        ui.root.report_callback_exception=lambda kind,value,trace:errors.append(value)
        try:
            # No library is created merely by building the app/window.
            assert not (Path(folder)/'library.sqlite3').exists()
            ui.conversation_entries[:]=[{'role':'user','content':'My fruit is **peach**.'},
                                        {'role':'assistant','content':'Remembered in this chat: `peach`.'}]
            ui.messages[:]=[{'role':'assistant','content':'unsafe protocol not saved','tool_calls':[{'name':'old'}]}]
            a=ui.artifact_store.create('School notes','document','First version')
            ui.artifact_store.revise(a.number,1,'Second version')
            stream=BytesIO();Image.new('RGB',(32,32),'navy').save(stream,format='PNG')
            ui.artifact_store.media('Selected picture','image',stream.getvalue())
            ui.artifact_panel.refresh();ui.artifact_panel.load(a.number)
            panel=ui.show_chats();pump(lambda:not ui.busy)
            assert panel.win.winfo_exists() and button(panel.win,'Close')
            # Create a Project through the actual editor widgets.
            panel.project_editor();ui.root.update()
            editor=next(w for w in panel.win.winfo_children() if isinstance(w,ui.tk.Toplevel))
            fields=[]
            def collect(parent):
                for child in parent.winfo_children():
                    if isinstance(child,ui.ttk.Entry):fields.append(child)
                    if isinstance(child,ui.tk.Text):notes=child;fields.append(notes)
                    collect(child)
            collect(editor)
            fields[0].insert(0,'Biology');fields[1].insert('1.0','Use short explanations.')
            ui.busy=True;button(editor,'Save Project').invoke();ui.root.update()
            assert editor.winfo_exists() and fields[1].get('1.0','end-1c')=='Use short explanations.'
            ui.busy=False
            button(editor,'Save Project').invoke();pump(lambda:not ui.busy and len(panel.projects)==1)
            panel.project.current(1);panel.title.set('Fruit study')
            panel.save_current(False);pump(lambda:not ui.busy and len(panel.rows)==1)
            saved_id=panel.rows[0]['id']
            loaded=saved.library.load(saved_id)
            assert loaded['messages']==ui.conversation_entries and loaded['project']==panel.projects[0]['id']
            assert len(loaded['items'])==2 and loaded['items'][0].current.number==2
            assert ui.saved_chat['version']==1
            panel.query.set('FRUIT');panel.refresh();pump(lambda:not ui.busy)
            assert len(panel.rows)==1
            panel.tree.selection_set(str(saved_id));ui.root.update()
            # Unsaved edits cannot be silently omitted from a save.
            ui.artifact_panel.editor.insert('end','\nHuman unsaved');ui.root.update()
            panel.save_current(True);assert 'Save edit' in panel.status.get()
            assert saved.library.load(saved_id)['version']==1
            ui.artifact_panel.save();ui.root.update()
            panel.save_current(True);pump(lambda:not ui.busy)
            assert ui.saved_chat['version']==2
            panel.tree.selection_set(str(saved_id));ui.root.update()
            old_items=ui.artifact_store.items();old_entries=list(ui.conversation_entries)
            with patch.object(panel_module.decisions,'askyesno',return_value=False):panel.open_selected()
            assert ui.artifact_store.items()==old_items and ui.conversation_entries==old_entries
            with patch.object(panel_module.decisions,'askyesno',return_value=True), \
                    patch.object(ui,'close_browser',return_value='Error: owned browser stopping'):
                panel.open_selected();pump(lambda:not ui.busy)
            assert ui.artifact_store.items()==old_items and ui.conversation_entries==old_entries
            # Exact selected transcript export, no overwrite.
            destination=Path(folder)/'chat.txt'
            with patch.object(panel_module.filedialog,'asksaveasfilename',return_value=str(destination)):
                panel.export_selected();pump(lambda:not ui.busy)
            assert '**peach**' in destination.read_text() and '`peach`' in destination.read_text()
            before=destination.read_bytes()
            with patch.object(panel_module.filedialog,'asksaveasfilename',return_value=str(destination)):
                panel.export_selected();pump(lambda:not ui.busy)
            assert destination.read_bytes()==before
            panel.status.set('Saved locally. Select a chat to reopen it; all previous permissions reset.')
            ui.root.update()
            screenshot=Path(__file__).resolve().parents[2]/'outputs/local_studio_saved_chats.png'
            box=(panel.win.winfo_rootx(),panel.win.winfo_rooty(),panel.win.winfo_rootx()+panel.win.winfo_width(),
                 panel.win.winfo_rooty()+panel.win.winfo_height())
            ImageGrab.grab(bbox=box).save(screenshot)
            # Short windows retain an accessible Close and scroll to Save controls.
            panel.win.geometry('600x420');ui.root.update();panel.scroll_canvas.yview_moveto(1);ui.root.update()
            assert button(panel.win,'Close').winfo_ismapped()
            save_button=button(panel.win,'Save new copy')
            assert save_button.winfo_rooty()+save_button.winfo_height()<=panel.win.winfo_rooty()+panel.win.winfo_height()
            panel.win.geometry('980x800');panel.scroll_canvas.yview_moveto(0);ui.root.update()
            print('PASS actual Library/Project editor, explicit save/update, filtering, dirty-buffer refusal, No and safe export',flush=True)

            # Actual reopen resets permissions and never replays a model call.
            import fetch
            fetch.session_hosts.add('approved.example')
            ui.entry.insert(0,'Unsent draft to replace')
            with patch.object(panel_module.decisions,'askyesno',return_value=True), \
                    patch.object(ui,'run_turn',side_effect=AssertionError('Restore must not invoke the model')):
                panel.open_selected();pump(lambda:not ui.busy and panel.closed)
            assert not fetch.session_hosts and ui.restored_chat and ui.entry.get()==''
            assert ui.saved_chat['version']==2 and ui.current_project is not None
            assert all(set(m)=={'role','content'} for m in ui.messages)
            assert len(ui.messages)==1 and 'reference data only' in ui.messages[0]['content']
            assert ui.conversation_entries==old_entries
            assert min(a.number for a in ui.artifact_store.items())>max(a.number for a in old_items)
            assert ui.artifact_store.items()[0].current.number==3
            assert not ui.pending_image and not ui.pending_media and not ui.task_progress.snapshot().resumable
            # Future turns use the existing code-enforced fresh-read gate.
            calls=[]
            def worker(*args):calls.append(args)
            with patch.object(ui,'worker',side_effect=worker):
                ui.entry.insert(0,'Continue discussing my notes');ui.send()
                pump(lambda:bool(calls))
            assert calls[0][-1] is True
            ui.remove_pending();ui.finish_turn()
            ui.events.put(('answer','**Raw answer** `peach`',.01));ui.poll()
            assert ui.conversation_entries[-1]=={'role':'assistant','content':'**Raw answer** `peach`'}
            print('PASS reopen preserves history/Artifacts, fresh IDs/permissions, no replay, fresh-read flag',flush=True)

            # Closing while a load is pending prevents a late replacement.
            panel=ui.show_chats();pump(lambda:not ui.busy)
            panel.tree.selection_set(str(saved_id));ui.root.update()
            gate=threading.Event();load=saved.library.load;before_entries=list(ui.conversation_entries)
            def slow_load(number):gate.wait(5);return load(number)
            with patch.object(saved.library,'load',side_effect=slow_load), \
                    patch.object(panel_module.decisions,'askyesno',return_value=True):
                panel.open_selected();ui.root.update();panel.win._dismiss_popup();gate.set()
                pump(lambda:not ui.busy)
            assert ui.conversation_entries==before_entries and panel.closed
            # Stop invalidates an open result and releases busy state after its DB read.
            panel=ui.show_chats();pump(lambda:not ui.busy)
            panel.tree.selection_set(str(saved_id));ui.root.update();gate.clear()
            with patch.object(saved.library,'load',side_effect=slow_load), \
                    patch.object(panel_module.decisions,'askyesno',return_value=True):
                panel.open_selected();ui.root.update();ui.stop_agent();gate.set();pump(lambda:not ui.busy)
            assert ui.conversation_entries==before_entries and 'cancelled' in panel.status.get()
            assert not ui.chat_box.tag_ranges('pending')
            ui.stop_event.clear()
            # Delete cancellation and project removal preserve saved/current work.
            with patch.object(panel_module.decisions,'askyesno',return_value=False):panel.delete_selected()
            assert saved.library.load(saved_id)
            panel.project.current(1)
            with patch.object(panel_module.decisions,'askyesno',return_value=True):panel.delete_project();pump(lambda:not ui.busy)
            assert saved.library.load(saved_id)['project'] is None
            panel.tree.selection_set(str(saved_id));ui.root.update()
            with patch.object(panel_module.decisions,'askyesno',return_value=True):panel.delete_selected();pump(lambda:not ui.busy)
            assert not saved.library.list_chats() and ui.conversation_entries==before_entries
            panel.win._dismiss_popup()
            # New chat clears only RAM; unrelated saved copies survive.
            keep=saved.library.save('Keep',None,old_entries,())
            with patch.object(ui.messagebox,'askyesno',return_value=True):assert ui.new_chat()
            assert not ui.conversation_entries and not ui.messages and not ui.restored_chat
            assert saved.library.load(keep['id'])['messages']==old_entries
            project=saved.library.save_project('Math','Show the steps clearly.')
            with patch.object(ui.messagebox,'askyesno',return_value=True):
                assert ui.start_project_chat(saved.library.projects()[0])
            assert ui.current_project==project and ui.restored_chat
            assert 'Show the steps clearly.' in ui.messages[0]['content']
            assert not ui.conversation_entries and ui.saved_chat is None
            panel=ui.show_chats();pump(lambda:not ui.busy)
            assert panel.project_id()==project
            # Save during a closed utility may still commit, but never reopens it.
            gate.clear();original_save=saved.library.save
            def slow_save(*args,**kwargs):gate.wait(5);return original_save(*args,**kwargs)
            with patch.object(saved.library,'save',side_effect=slow_save):
                panel.title.set('Closed-save copy');panel.save_current(False)
                panel.win._dismiss_popup();gate.set();pump(lambda:not ui.busy)
            assert panel.closed and any(r['title']=='Closed-save copy' for r in saved.library.list_chats())
            assert ui.saved_chat['title']=='Closed-save copy'
            # Actual storage controls: inactivity is injected, never a real week wait.
            import artifacts
            payload=artifacts.Store();payload.create('Archived notes','document','Study point.\n'*1500)
            entries=[{'role':'user','content':'Exact saved archive `example`'}]
            archived=saved.library.save('Old ZIP example',None,entries,payload.items())
            current=ui.saved_chat['id']
            with saved.library.connection() as db:
                old=time.time()-saved.ARCHIVE_AGE-60
                db.execute('UPDATE chats SET last_used=?,updated=? WHERE id IN (?,?)',(old,old,current,archived['id']))
            panel=ui.show_chats();pump(lambda:not ui.busy)
            panel.project.current(0);panel.refresh();pump(lambda:not ui.busy)
            panel.auto_zip.set(False);panel.toggle_archive();pump(lambda:not ui.busy)
            assert not saved.library.archive_enabled()
            panel.auto_zip.set(True);panel.toggle_archive();pump(lambda:not ui.busy)
            assert saved.library.archive_enabled()
            button(panel.win,'Check unused chats now').invoke();pump(lambda:not ui.busy)
            rows={r['id']:r for r in panel.rows}
            assert rows[archived['id']]['archived'] and not rows[current]['archived']
            assert panel.tree.item(str(archived['id']),'values')[-1]=='ZIP'
            panel.tree.selection_set(str(archived['id']));ui.root.update()
            screenshot=Path(__file__).resolve().parents[2]/'outputs/local_studio_weekly_archives.png'
            box=(panel.win.winfo_rootx(),panel.win.winfo_rooty(),panel.win.winfo_rootx()+panel.win.winfo_width(),
                 panel.win.winfo_rooty()+panel.win.winfo_height())
            ImageGrab.grab(bbox=box).save(screenshot)
            destination=Path(folder)/'archived-chat.txt'
            with patch.object(panel_module.filedialog,'asksaveasfilename',return_value=str(destination)):
                panel.export_selected();pump(lambda:not ui.busy)
            assert '`example`' in destination.read_text()
            with patch.object(panel_module.decisions,'askyesno',return_value=True):
                panel.open_selected();pump(lambda:not ui.busy and panel.closed)
            assert ui.conversation_entries==entries and ui.artifact_store.items()[0].current.content=='Study point.\n'*1500
            assert ui.saved_chat['version']==1
            panel=ui.show_chats();pump(lambda:not ui.busy)
            panel.save_current(True);pump(lambda:not ui.busy)
            assert ui.saved_chat['version']==2
            assert not next(r for r in panel.rows if r['id']==archived['id'])['archived']
            print('PASS real ZIP toggle/check, open-chat exclusion, ZIP badge, export/reopen and update to plain storage',flush=True)
            panel.win._dismiss_popup()
            assert not errors,errors
            print('PASS late-close/Stop, deletion cancellation, Project removal, saved/current separation, New chat and Project start',flush=True)
        finally:
            ui.stop_all();ui.root.destroy()


if __name__=='__main__':main()

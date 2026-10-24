"""Owned real Tk/Windows/parser fixtures with synthetic sources and fake inference."""
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch

from PIL import ImageGrab
import chat_window as ui
import document_qa as qa
import document_qa_panel as panel_module
from document_sources import Source
from test_document_qa import pdf_bytes,response


def pump(test,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        ui.root.update()
        if test():return
        time.sleep(.02)
    raise AssertionError('Document Q&A UI fixture timed out')


def button(parent,label):
    for child in parent.winfo_children():
        if isinstance(child,(ui.ttk.Button,ui.tk.Button)) and child.cget('text')==label:return child
        found=button(child,label)
        if found:return found


def main():
    errors=[]
    with tempfile.TemporaryDirectory() as folder,patch('emergency_hotkey.start_hotkey'),patch.object(ui,'free_vram'):
        ui.build_window();ui.root.geometry('1440x900')
        ui.root.report_callback_exception=lambda kind,value,trace:errors.append(value)
        try:
            path=Path(folder)/'Synthetic plant notes.pdf'
            path.write_bytes(pdf_bytes(['Map symbols and directions.','Plant chlorophyll absorbs red and blue light during photosynthesis.','']))
            panel=ui.show_sources();ui.root.update()
            assert button(panel.win,'Close') and not panel.collection.sources
            with patch.object(panel_module.filedialog,'askopenfilename',return_value=str(path)):
                button(panel.win,'Add source').invoke();pump(lambda:not ui.busy)
            assert len(panel.collection.sources)==1,panel.status.get()
            selected=panel.collection.sources[0]
            assert len(selected.pages)==3 and '1 pages have no extracted text' in panel.status.get()
            assert '3 PDF pages' in str(panel.tree.item(str(selected.number),'values'))
            # The model gets immutable extracted snapshots even if the original changes.
            path.write_bytes(pdf_bytes(['Changed original.']))
            panel.question.insert('1.0','What light does chlorophyll absorb?')
            with patch.object(qa.models,'chat',return_value=response()):
                button(panel.win,'Ask selected sources').invoke();pump(lambda:not ui.busy)
            assert panel.answer and panel.answer.answerable,panel.status.get()
            assert 'PDF page 2' in panel.output.get('1.0','end') and 'red and blue' in panel.page.get('1.0','end')
            assert 'Changed original.' not in panel.page.get('1.0','end')
            assert panel.page.cget('state')=='disabled' and panel.output.cget('state')=='disabled'
            panel.keep();assert ui.artifact_store.items()[-1].title=='Document Q&A'
            assert 'Snapshot references' in ui.artifact_store.items()[-1].current.content
            ui.artifact_panel.editor.insert('end','\nUnsent draft stays here.');ui.root.update()
            original=ui.artifact_panel.editor.get('1.0','end-1c')
            panel.keep();ui.root.update()
            assert ui.artifact_panel.dirty and ui.artifact_panel.editor.get('1.0','end-1c')==original
            ui.root.update()
            screenshot=Path(__file__).resolve().parents[2]/'outputs/local_studio_document_qa.png'
            box=(panel.win.winfo_rootx(),panel.win.winfo_rooty(),panel.win.winfo_rootx()+panel.win.winfo_width(),panel.win.winfo_rooty()+panel.win.winfo_height())
            ImageGrab.grab(bbox=box).save(screenshot)
            # A smaller window can scroll the content while its Close/status remain.
            panel.win.geometry('600x420');ui.root.update();panel.canvas.yview_moveto(1);ui.root.update()
            close=button(panel.win,'Close');assert close.winfo_ismapped()
            assert close.winfo_rooty()+close.winfo_height()<=panel.win.winfo_rooty()+panel.win.winfo_height()
            panel.win.geometry('1000x850');ui.root.update()
            print('PASS actual PDF worker, physical pages/blank warning, immutable snapshot, cited answer/inspection and Artifact',flush=True)

            # Stop and Close reject late results rather than reopening a popup or changing sources.
            gate=threading.Event();started=threading.Event();old_count=len(panel.collection.sources)
            def slow_model(**kwargs):started.set();gate.wait(10);return response()
            with patch.object(qa.models,'chat',side_effect=slow_model):
                panel.ask();pump(started.is_set);ui.stop_agent();gate.set();pump(lambda:not ui.busy)
            assert panel.answer is None and 'Cancelled' in panel.status.get()
            assert not ui.chat_box.tag_ranges('pending')
            gate.clear();started.clear()
            def slow_import(*args):started.set();gate.wait(10);return Source(panel.collection.next_number,'Late.txt','text','b'*64,('Late synthetic notes.',))
            with patch.object(panel_module.filedialog,'askopenfilename',return_value=str(path)),patch.object(panel_module,'import_source',side_effect=slow_import):
                panel.add();pump(started.is_set);button(panel.win,'Close').invoke();gate.set();pump(lambda:not ui.busy)
            assert panel.closed and len(panel.collection.sources)==old_count
            for method in ('escape','x'):
                panel=ui.show_sources();ui.root.update();panel.win.focus_force();ui.root.update();assert len(panel.collection.sources)==1
                if method=='escape':panel.win.event_generate('<Escape>')
                else:panel.win.tk.call(panel.win.protocol('WM_DELETE_WINDOW'))
                ui.root.update();assert panel.closed and not panel.win.winfo_exists()
            print('PASS Stop discards late inference, Close discards late import, Close/Escape/X and short-window access',flush=True)

            panel=ui.show_sources();ui.root.update()
            panel.tree.selection_set(str(selected.number));panel.remove();assert not panel.collection.sources
            with patch.object(panel_module.filedialog,'askopenfilename',return_value=''):panel.add()
            assert not panel.collection.sources
            panel.collection.add(Source(panel.collection.next_number,'Forget.txt','text','c'*64,('Forget this synthetic note.',)))
            panel.forget();assert not panel.collection.sources
            panel.collection.add(Source(panel.collection.next_number,'Fresh.txt','text','d'*64,('Fresh synthetic note.',)))
            with patch.object(ui.messagebox,'askyesno',return_value=True):assert ui.new_chat()
            assert not panel.collection.sources and panel.closed
            assert not errors,errors
            print('PASS picker cancel, explicit remove/forget and New chat clears document snapshots without touching originals',flush=True)
        finally:ui.stop_all();ui.root.destroy()


if __name__=='__main__':main()

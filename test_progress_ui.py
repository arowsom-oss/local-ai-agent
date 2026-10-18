"""Real Tk progress/resume fixture. Model, Notepad and approvals use synthetic fakes."""
import time
import types
from unittest.mock import patch
import chat_window as ui
import agent_core as core
from task_progress import TaskProgress


def call(name,args):return types.SimpleNamespace(function=types.SimpleNamespace(name=name,arguments=args))
def response(calls=(),text=''):return types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=list(calls),content=text))


def wait_idle():
    deadline=time.monotonic()+8
    while ui.busy and time.monotonic()<deadline:ui.root.update();time.sleep(.01)
    assert not ui.busy,'fixture timed out'
    ui.root.update()


if __name__=='__main__':
    ui.task_progress=TaskProgress();ui.build_window();ui.model_var.set('gemma4:e2b');ui.root.focus_force();ui.root.update();ui.poll()
    replies=iter([
        response([call('outline_task',{'steps':['Read the current scratch draft','Propose an exact edit']})]),
        response([call('notepad_read',{})]),response([call('notepad_replace',{'element':1,'text':'first proposal'})]),
        response([call('notepad_read',{})]),response([call('notepad_replace',{'element':2,'text':'human version plus approved addition'})]),response(text='Finished')])
    popups=[];writes=[];current=['first draft'];read_count=[0]
    def read():
        read_count[0]+=1;return f'[{read_count[0]}] text box Scratch document\n{current[0]}'
    def prepare(element,text):
        assert element==read_count[0]
        return {'token':'fixture','preview':{'before':current[0],'after':text,'window':'Synthetic fixture'}}
    def commit(token):
        writes.append(current[0]);current[0]='human version plus approved addition'
        return 'Notepad edit verified by exact read-back. Revision 2.'
    def decide(name,args):
        popups.append((name,args))
        return len(popups)>1
    try:
        with patch.object(core,'chat',side_effect=lambda **kw:next(replies)),patch.object(core,'compact',return_value=False), \
             patch.object(core,'audit'),patch.object(core,'prepare_notepad',side_effect=prepare), \
             patch.object(core,'commit_notepad',side_effect=commit),patch.object(core,'cancel_notepad'), \
             patch.object(core,'cancel_workspace'),patch.dict(core.available_functions,{'notepad_read':read}),patch.object(ui,'confirm',side_effect=decide):
            ui.entry.insert(0,'Revise my synthetic scratch draft');ui.send();wait_idle()
            paused=ui.task_progress.snapshot();assert paused.phase=='Paused' and paused.resumable and not writes
            ui.progress_panel.render(paused);ui.progress_panel.details();ui.root.update()
            body=ui.progress_panel.text.get('1.0','end')
            assert ui.progress_panel.detail_resume.winfo_ismapped()
            assert ui.progress_panel.detail_resume.winfo_rooty()+ui.progress_panel.detail_resume.winfo_height()<ui.progress_panel.window.winfo_rooty()+ui.progress_panel.window.winfo_height()
            assert 'MODEL TEXT' in body and 'Denied' in body and 'Verified tool results: 0' in body
            assert str(ui.progress_panel.resume_button.cget('state'))=='normal'
            ui.entry.insert(0,'Unsent human message');ui.progress_panel.resume_button.invoke()
            assert ui.entry.get()=='Unsent human message' and not ui.busy and not writes
            ui.entry.delete(0,'end')
            current[0]='human version'
            ui.progress_panel.resume_button.invoke();wait_idle()
            s=ui.task_progress.snapshot();ui.progress_panel.render(s)
            assert len(popups)==2 and popups[-1][1]['before']=='human version' and writes==['human version']
            assert s.phase=='Reply ready' and s.verified==1 and read_count[0]==2 and not s.resumable
            assert 'Fresh reads required' in ui.progress_panel.text.get('1.0','end')
            ui.stop_agent();old=s.serial
            ui.task_progress.event(old,'result',tool='document_save',status='Verified')
            # Stop after a reply leaves its completed evidence intact; no running action is revived.
            assert ui.task_progress.snapshot().verified==1
            with patch.object(ui.messagebox,'askyesno',return_value=True),patch.object(ui,'free_vram'):
                ui.new_chat()
            assert ui.task_progress.snapshot().phase=='Ready' and not ui.task_progress.snapshot().rows
        print('PASS real Tk task panel: proposed steps, denial/pause, Resume starts a fresh read and exact approval, verified receipt, Stop and New chat')
    finally:ui.root.destroy()

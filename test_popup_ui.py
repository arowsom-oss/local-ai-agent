"""Owned native Tk/Windows popup fixtures; synthetic data, no Internet or model."""
import ctypes as C
from ctypes import wintypes as W
from io import BytesIO
import os
from pathlib import Path
import tempfile
import threading
import time
import types
from unittest.mock import patch
from PIL import Image
import chat_window as ui
import popup_windows as pop
import workspace_panel as documents
from vision_input import prepare_image


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


def button(win,label):
    return next(w for w in descendants(win) if isinstance(w,(ui.tk.Button,ui.ttk.Button)) and w.cget('text')==label)


def close(win,method,label='Close'):
    ui.root.update();win.focus_force();ui.root.update()
    control=button(win,label)
    assert control.winfo_ismapped() and control.winfo_width()>10,(win.title(),label)
    assert control.winfo_rooty()>=win.winfo_rooty()
    assert control.winfo_rooty()+control.winfo_height()<=win.winfo_rooty()+win.winfo_height()
    left,top,right,bottom=pop.work_area(win)
    assert left<=control.winfo_rootx()<right and top<=control.winfo_rooty()<bottom
    if method=='button':control.invoke()
    elif method=='escape':win.event_generate('<Escape>')
    elif method=='enter':win.event_generate('<Return>')
    else:win.tk.call(win.protocol('WM_DELETE_WINDOW'))
    ui.root.update();assert not win.winfo_exists(),(win.title() if win.winfo_exists() else '',method)
    assert ui.root.grab_current() is None


def modal(call,method,label='No'):
    failure=[]
    def dismiss():
        win=next(w for w in descendants(ui.root) if getattr(w,'_approval_dialog',False))
        try:close(win,method,label)
        except Exception as exc:
            failure.append(exc)
            if win.winfo_exists():win._dismiss_popup()
    ui.root.after(100,dismiss)
    assert call() is False
    assert not failure,failure
    assert ui.root.grab_current() is None


def close_native(call):
    """Send WM_CLOSE only to this fixture process's native common dialog."""
    done=threading.Event();found=[]
    user=C.WinDLL('user32',use_last_error=True)
    enum_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    user.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    user.IsWindowVisible.argtypes=[W.HWND]
    @enum_type
    def visit(hwnd,unused):
        pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if pid.value!=os.getpid():return True
        name=C.create_unicode_buffer(100);user.GetClassNameW(hwnd,name,100)
        if name.value=='#32770' and user.IsWindowVisible(hwnd):
            found.append(True);user.PostMessageW(hwnd,0x0010,0,0);return False
        return True
    def watch():
        until=time.monotonic()+6
        while not done.wait(.04) and time.monotonic()<until:
            user.EnumWindows(visit,0)
            if found:return
    worker=threading.Thread(target=watch,daemon=True);worker.start()
    try:result=call()
    finally:done.set();worker.join(1)
    assert found,'Owned native dialog never appeared'
    assert not result,result


def main():
    with patch('emergency_hotkey.start_hotkey'):ui.build_window()
    ui.root.title('Local Studio - popup close regression fixture');ui.root.update()
    errors=[];ui.root.report_callback_exception=lambda kind,value,trace:errors.append(value)
    raw=BytesIO();Image.new('RGB',(1200,800),'navy').save(raw,format='PNG');image=prepare_image(raw.getvalue())
    try:
        with patch.object(ui,'AUDIT_LOG',Path(tempfile.gettempdir())/'absent-synthetic-audit-fixture.log'):
            for method in ('button','escape','x'):
                print('Testing custom popups:',method,flush=True)
                ui.show_log();close(next(w for w in ui.root.winfo_children() if isinstance(w,ui.tk.Toplevel)),method)
                ui.connect_edge_tab();close(ui.edge_panel,method)
                tabs=[dict(number=n,title='Synthetic work tab '+str(n)+' '+'long '*100,url='https://fixture.example/'+'x'*700) for n in range(20)]
                ui.choose_edge_work_tab({'tabs':tabs});close(ui.edge_tab_picker,method,'Cancel')
                ui.choose_edge_work_tab({'tabs':[]});close(ui.edge_tab_picker,method,'Cancel')
                ui.progress_panel.details();close(ui.progress_panel.window,method)
                fake_jobs=types.SimpleNamespace(run=lambda work,done:done({'records':[]}))
                with patch.object(documents,'access',return_value=True),patch.object(documents,'jobs',return_value=fake_jobs):
                    documents.show_documents(ui.artifact_panel,None)
                    first=ui.artifact_panel.documents_window
                    documents.show_documents(ui.artifact_panel,None)
                    assert ui.artifact_panel.documents_window is first
                    close(first,method)
                with patch.object(ui,'high_risk_confirm',return_value=True),patch.object(ui,'start_edge',return_value='fixture-code'):
                    ui.share_personal_edge_tab()
                pairing=next(w for w in ui.root.winfo_children() if isinstance(w,ui.tk.Toplevel))
                close(pairing,method,'Close code window')
                modal(lambda:ui.high_risk_confirm('Synthetic long approval',['Exact fixture data '*10000]),method)
                modal(lambda:ui.preview_image(image),method)
                modal(lambda:ui.messagebox.askyesno('Synthetic decision','Cancel this fixture.',parent=ui.root),method)
        # All approval branches share the tested bounded, scrollable No-default shell.
        for name in ('edge_operation','workspace_access','document_save_exact','notepad_start',
                     'notepad_action','desktop_action','generation','desktop_start','plan','plan_changed',
                     'new_site','browser_search','browser_web_search','outbound_request','fetch_page'):
            args=dict(action='read',mode='work profile',url='https://fixture.example/'+'x'*3000,
                      before='Before',after='After',steps=['Synthetic step '*100]*5,prompt='Fixture')
            modal(lambda:ui.confirm(name,args),'button')
        # Cancel the real entry points, not just their shared dialog shell.
        ui.messages.append({'role':'user','content':'Synthetic retained chat'})
        artifact=ui.artifact_store.create('Synthetic unsaved draft','document','Saved draft')
        ui.show_artifacts();ui.artifact_panel.refresh();ui.artifact_panel.load(artifact.number)
        ui.artifact_panel.editor.insert('end',' plus unsaved human text');ui.root.update()
        original=ui.artifact_panel.editor.get('1.0','end-1c')
        with patch.object(ui,'capture_practice',side_effect=AssertionError('Cancelled capture ran')), \
             patch.object(ui,'start_background',side_effect=AssertionError('Cancelled model check ran')), \
             patch.object(ui,'close_edge',side_effect=AssertionError('Cancelled New chat ran')):
            for method in ('button','escape','x','enter'):
                modal(lambda:(ui.new_chat(),False)[1],method)
                modal(lambda:(ui.screenshot(),False)[1],method)
                modal(lambda:(ui.model_check(),False)[1],method)
                modal(ui.artifact_panel.discard_ok,method)
                assert ui.messages[-1]['content']=='Synthetic retained chat'
                assert ui.artifact_panel.editor.get('1.0','end-1c')==original and ui.artifact_panel.dirty
        ui.root.after(100,lambda:button(next(w for w in descendants(ui.root) if getattr(w,'_approval_dialog',False)),'Yes').invoke())
        assert ui.messagebox.askyesno('Synthetic explicit Yes','No real action.',parent=ui.root) is True
        # Explicitly stress a small screen/work area. Footer stays inside the window.
        with patch.object(pop,'work_area',return_value=(0,0,640,480)):
            modal(lambda:ui.high_risk_confirm('Short monitor',['Long fixture '*10000]),'button')
            modal(lambda:ui.preview_image(image),'button')
            ui.choose_edge_work_tab({'tabs':tabs});close(ui.edge_tab_picker,'button','Cancel')
        # Closing Documents before its list arrives must not touch destroyed widgets.
        completions=[]
        fake_jobs=types.SimpleNamespace(run=lambda work,done:completions.append(done))
        with patch.object(documents,'access',return_value=True),patch.object(documents,'jobs',return_value=fake_jobs):
            documents.show_documents(ui.artifact_panel,None);close(ui.artifact_panel.documents_window,'button')
            completions[0]({'records':[]});ui.root.update()
        # Nested approvals restore the enclosing modal grab after the child closes.
        observed=[]
        def outer():
            parent=next(w for w in descendants(ui.root) if getattr(w,'_approval_dialog',False))
            ui.root.after(100,lambda:next(w for w in descendants(ui.root) if getattr(w,'_approval_dialog',False) and w is not parent)._dismiss_popup())
            assert ui.high_risk_confirm('Nested fixture',['No action']) is False
            observed.append(ui.root.grab_current() is parent);parent._dismiss_popup()
        ui.root.after(100,outer)
        assert ui.high_risk_confirm('Outer fixture',['No action']) is False and observed==[True]
        # Every app combobox can dismiss without stopping the session. Windows
        # native menus use an OS modal loop, not reliable Tk synthetic key events.
        ui.stop_event.clear()
        for box in (ui.model_box,ui.artifact_panel.choice,ui.artifact_panel.history):
            ui.root.focus_force();box.focus_set();ui.root.update()
            ui.root.tk.call('ttk::combobox::Post',str(box));ui.root.update()
            popup=ui.root.tk.call('ttk::combobox::PopdownWindow',str(box))
            assert ui.root.tk.call('winfo','ismapped',popup)
            box.event_generate('<Escape>');ui.root.update()
            assert not ui.root.tk.call('winfo','ismapped',popup)
        assert not ui.stop_event.is_set()
        # Quiet chat, on-demand details, one utility panel and actual window branding.
        ui.events.put(('log','[timing] Synthetic activity-only marker'));ui.poll();ui.root.update()
        assert 'Synthetic activity-only marker' not in ui.chat_box.get('1.0','end')
        ui.show_log();activity=ui.audit_window;ui.root.update()
        assert 'Synthetic activity-only marker' in ui.activity_box.get('1.0','end')
        ui.connect_edge_tab();assert not activity.winfo_exists()
        close(ui.edge_panel,'button')
        from app_brand import APP_ID,set_window_icon
        assert set_window_icon(ui.root)
        user=C.WinDLL('user32');user.GetParent.argtypes=[W.HWND];user.GetParent.restype=W.HWND
        user.SendMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.SendMessageW.restype=C.c_ssize_t
        assert user.SendMessageW(user.GetParent(ui.root.winfo_id()),0x007f,1,0),'Custom Windows icon handle missing'
        shell=C.WinDLL('shell32');identity=C.c_wchar_p()
        shell.GetCurrentProcessExplicitAppUserModelID.argtypes=[C.POINTER(C.c_wchar_p)]
        assert shell.GetCurrentProcessExplicitAppUserModelID(C.byref(identity))==0 and identity.value==APP_ID
        ole=C.WinDLL('ole32');ole.CoTaskMemFree.argtypes=[C.c_void_p];ole.CoTaskMemFree(C.cast(identity,C.c_void_p))
        # Real native Open/Save/No and Tk prompt cancellation. No fixture path is used.
        with tempfile.TemporaryDirectory(prefix='studio-popup-native-') as directory:
            close_native(lambda:ui.filedialog.askopenfilename(parent=ui.root,initialdir=directory,title='Synthetic open - cancel'))
            close_native(lambda:ui.filedialog.asksaveasfilename(parent=ui.root,initialdir=directory,title='Synthetic save - cancel'))
            assert not list(Path(directory).iterdir())
        from tkinter import simpledialog
        for method in ('button','escape','x'):
            def cancel_prompt(value=method):
                win=next(w for w in ui.root.winfo_children() if isinstance(w,ui.tk.Toplevel))
                close(win,value,'Cancel')
            ui.root.after(100,cancel_prompt)
            assert simpledialog.askstring('Synthetic motion','Cancel this fixture.',parent=ui.root) is None
        assert ui.root.grab_current() is None and not errors,errors
        print('PASS native popups: all nine custom popup types, Close/Cancel/No, Escape and title-bar protocol cancellation')
        print('PASS native popups: all approval branches, long lists/text, empty lists, short monitor, nested grabs and late Documents results')
        print('PASS native Windows/Tk: real Open, Save, No-default decisions and text-prompt cancellation without files or actions')
        print('PASS native model/Artifact/version dropdowns: Escape dismisses without Stop; OS menu event injection is not claimed')
        print('PASS native calm UI: Activity retains routine logs, one utility panel, custom window icon and Windows application identity')
    finally:ui.stop_all();ui.root.destroy()


if __name__=='__main__':main()

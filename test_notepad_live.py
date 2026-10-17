"""Real classic Notepad/UIA fixture. Only owned blank scratch windows are changed."""
import ctypes as C
from ctypes import wintypes as W
import re
import threading
import time
import notepad_tools as n


def number(text):
    match=re.search(r"\[(\d+)\] text box Scratch document",text)
    assert match,text
    return int(match.group(1))


def test_real_notepad_two_caller_threads_exact_edits_and_stale_refusal():
    assert not n.start_notepad().startswith("Error:")
    identity=n._session.identity
    user=C.WinDLL("user32",use_last_error=True)
    user.GetDlgItem.argtypes=[W.HWND,C.c_int];user.GetDlgItem.restype=W.HWND
    user.SendMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,C.c_void_p]
    try:
        errors=[]
        def turn(text):
            try:
                read=n.notepad_read();p=n.prepare_notepad(number(read),text)
                assert "token" in p,p
                assert not n.commit_notepad(p["token"]).startswith("Error:")
                assert n.commit_notepad(p["token"]).startswith("Error:")
                assert text in n.notepad_read().replace('\\n','\n')
            except Exception as exc:errors.append(exc)
        for text in ("Scratch paragraph.","Revised paragraph.\nSecond line."):
            thread=threading.Thread(target=turn,args=(text,));thread.start();thread.join(10)
            assert not thread.is_alive() and not errors,errors
        read=n.notepad_read();element=number(read)
        p=n.prepare_notepad(element,"approved replacement")
        hwnd=user.GetDlgItem(identity["hwnd"],15)
        user.SendMessageW(hwnd,0x000c,0,C.cast(C.create_unicode_buffer("Human edit after preview"),C.c_void_p))
        assert n.commit_notepad(p["token"]).startswith("Error:")
        assert "Human edit after preview" in n.notepad_read()
        assert "error" in n.prepare_notepad(element,"stale")
        assert "error" in n.prepare_notepad(number(n.notepad_read()),"x"*2001)
        kernel=C.WinDLL("kernel32",use_last_error=True)
        kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
        kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.CloseHandle.argtypes=[W.HANDLE]
        handles=[kernel.OpenProcess(0x100000,False,pid) for pid in (identity["pid"],n._session.process.pid)]
        assert all(handles)
        n.close_notepad()
        try:assert all(kernel.WaitForSingleObject(handle,2000)==0 for handle in handles)
        finally:
            for handle in handles:kernel.CloseHandle(handle)
        assert n.notepad_read().startswith("Error:")
    finally:n.close_notepad()


def test_menu_activity_permanently_halts_and_restart_uses_fresh_numbers():
    assert not n.start_notepad().startswith("Error:")
    try:
        read=n.notepad_read();assert number(read)>1
        user=C.WinDLL("user32",use_last_error=True)
        user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        hwnd=n._session.identity["hwnd"]
        # Open only this owned app's File menu, without typing or selecting a command.
        assert user.PostMessageW(hwnd,0x0112,0xf100,ord('f'))
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            result=n.notepad_read()
            if result.startswith("Error:"):break
            time.sleep(.05)
        assert result.startswith("Error:"),result
        user.PostMessageW(hwnd,0x001f,0,0)  # WM_CANCELMODE closes the menu.
        time.sleep(.1)
        assert n.notepad_read().startswith("Error:")
        assert "error" in n.prepare_notepad(number(read),"must not run")
    finally:n.close_notepad()


if __name__=="__main__":
    test_real_notepad_two_caller_threads_exact_edits_and_stale_refusal()
    print("PASS real Notepad: owned blank launch, UIA reads/edits, two caller threads, replay/stale refusal and owned process cleanup")
    test_menu_activity_permanently_halts_and_restart_uses_fresh_numbers()
    print("PASS real menu event guard: session remains halted after menu closes; restart numbers are fresh")

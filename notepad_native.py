"""Fixed classic-Notepad launcher and UIA backend, used only inside an owned worker."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import time
from dataclasses import dataclass
from process_guard import Job


def check_launch_policy():
    """Respect preconfigured debugger launch rules; read policy, never change it."""
    import winreg
    path=r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\notepad.exe"
    def inspect(key,depth=0):
        try:
            winreg.QueryValueEx(key,"Debugger")
        except FileNotFoundError:
            pass
        else:
            raise ValueError("configured debugger launch policy; scratch Notepad refused")
        count=winreg.QueryInfoKey(key)[0]
        if count>32 or (depth>=2 and count):
            raise ValueError("launch policy could not be bounded")
        for index in range(count):
            name=winreg.EnumKey(key,index)
            with winreg.OpenKey(key,name,0,winreg.KEY_READ) as child:
                inspect(child,depth+1)
    for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
        try:
            key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,path,0,winreg.KEY_READ|view)
        except FileNotFoundError:
            continue
        with key:
            inspect(key)


@dataclass(frozen=True)
class Snapshot:
    text: str
    title: str
    window: int
    control: int
    root_runtime: tuple
    edit_runtime: tuple


class NativeNotepad:
    def __init__(self):
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.user = C.WinDLL("user32", use_last_error=True)
        self.process = self.thread = self.job = self.hook = None
        self.tainted = False
        self._configure()
        try:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as U
            self.U = U
            self.automation = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
            self._launch()
            # Hooks are installed before this owned child is allowed to run.
            self._watch()
            if not self.kernel.DebugActiveProcessStop(self.pid):
                raise C.WinError(C.get_last_error())
            if self.kernel.ResumeThread(self.thread) == 0xffffffff:
                raise C.WinError(C.get_last_error())
            self.kernel.CloseHandle(self.thread)
            self.thread = None
            deadline = time.monotonic() + 8
            self.hwnd = 0
            while time.monotonic() < deadline:
                self.pump()
                windows = self.windows()
                if len(windows) == 1:
                    self.hwnd = windows[0]
                    break
                if len(windows) > 1:
                    raise ValueError("multiple Notepad windows; scope refused")
                time.sleep(.05)
            if not self.hwnd:
                raise ValueError("classic Notepad did not open; no modern-app fallback")
            self.initial_title = self.title(self.hwnd)
            first = self.snapshot()
            if first.text:
                raise ValueError("Notepad did not start with an empty document")
            self.initial = first
        except Exception:
            self.close()
            raise

    def _configure(self):
        k,u=self.kernel,self.user
        k.GetSystemDirectoryW.argtypes=[W.LPWSTR,W.UINT]
        k.CloseHandle.argtypes=[W.HANDLE]
        k.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
        k.ResumeThread.argtypes=[W.HANDLE];k.ResumeThread.restype=W.DWORD
        k.DebugActiveProcessStop.argtypes=[W.DWORD]
        k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
        k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
        u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
        u.GetDlgItem.argtypes=[W.HWND,C.c_int];u.GetDlgItem.restype=W.HWND
        u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
        u.IsWindowEnabled.argtypes=[W.HWND]
        u.IsWindowVisible.argtypes=[W.HWND]
        u.SendMessageTimeoutW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t)]
        u.SendMessageTimeoutW.restype=C.c_ssize_t
        u.UnhookWinEvent.argtypes=[W.HANDLE]
        self.enum_callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        u.EnumWindows.argtypes=[self.enum_callback,W.LPARAM]
        self.event_callback=C.WINFUNCTYPE(None,W.HANDLE,W.DWORD,W.HWND,W.LONG,W.LONG,W.DWORD,W.DWORD)
        u.SetWinEventHook.argtypes=[W.DWORD,W.DWORD,W.HMODULE,self.event_callback,W.DWORD,W.DWORD,W.DWORD]
        u.SetWinEventHook.restype=W.HANDLE
        u.PeekMessageW.argtypes=[C.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]

    def _launch(self):
        check_launch_policy()
        class Startup(C.Structure):
            _fields_=[("cb",W.DWORD),("reserved",W.LPWSTR),("desktop",W.LPWSTR),("title",W.LPWSTR),
                      ("x",W.DWORD),("y",W.DWORD),("width",W.DWORD),("height",W.DWORD),
                      ("xchars",W.DWORD),("ychars",W.DWORD),("fill",W.DWORD),("flags",W.DWORD),
                      ("show",W.WORD),("reserved_count",W.WORD),("reserved_bytes",C.c_void_p),
                      ("stdin",W.HANDLE),("stdout",W.HANDLE),("stderr",W.HANDLE)]
        class Process(C.Structure):
            _fields_=[("process",W.HANDLE),("thread",W.HANDLE),("pid",W.DWORD),("tid",W.DWORD)]
        directory=C.create_unicode_buffer(32768)
        length=self.kernel.GetSystemDirectoryW(directory,len(directory))
        if not 0 < length < len(directory):
            raise ValueError("system directory unavailable")
        self.executable=Path(directory.value)/"notepad.exe"
        startup=Startup();startup.cb=C.sizeof(startup);info=Process()
        self.kernel.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,
                                            C.c_void_p,W.LPCWSTR,C.POINTER(Startup),C.POINTER(Process)]
        # Brief DEBUG_ONLY_THIS_PROCESS + CREATE_SUSPENDED selects the classic
        # installed binary here. Detach BEFORE resume. No persistent debugger
        # registration, policy/registry changes, shell, arguments, document paths
        # or modern-app fallback.
        if not self.kernel.CreateProcessW(str(self.executable),None,None,None,False,0x6,
                                           None,directory.value,C.byref(startup),C.byref(info)):
            raise C.WinError(C.get_last_error())
        self.process,self.thread,self.pid=info.process,info.thread,int(info.pid)
        self.job=Job(self.pid,256)  # Assigned while suspended, kill on owning handle close.
        image=C.create_unicode_buffer(32768);size=W.DWORD(len(image))
        if (not self.kernel.QueryFullProcessImageNameW(self.process,0,image,C.byref(size))
                or Path(image.value).resolve() != self.executable.resolve()):
            raise ValueError("unexpected executable; Notepad launch refused")

    def _watch(self):
        @self.event_callback
        def event(hook,kind,hwnd,obj,child,thread,stamp):
            if kind in (4,5,6,7,16,17):
                self.tainted=True  # Menus/dialogs may change documents; never resume this session.
        self._event=event
        self.hook=self.user.SetWinEventHook(4,17,None,event,self.pid,0,0)
        if not self.hook:
            raise ValueError("could not install the Notepad scope guard")

    def pump(self):
        message=W.MSG()
        for _ in range(256):
            if not self.user.PeekMessageW(C.byref(message),None,0,0,1):
                return
            self.user.TranslateMessage(C.byref(message))
            self.user.DispatchMessageW(C.byref(message))
        self.tainted=True

    def pid_of(self,hwnd):
        pid=W.DWORD();self.user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        return pid.value

    def class_name(self,hwnd):
        value=C.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd,value,len(value))
        return value.value

    def title(self,hwnd):
        value=C.create_unicode_buffer(256)
        self.user.GetWindowTextW(hwnd,value,len(value))
        return value.value

    def windows(self):
        found=[]
        @self.enum_callback
        def visit(hwnd,unused):
            if self.pid_of(hwnd)==self.pid and self.class_name(hwnd)=="Notepad" and self.user.IsWindowVisible(hwnd):
                found.append(int(hwnd))
            return True
        self.user.EnumWindows(visit,0)
        return found

    def snapshot(self):
        self.pump()
        if self.tainted:
            raise ValueError("Notepad menu/dialog activity changed scope; session halted")
        if self.kernel.WaitForSingleObject(self.process,0) != 258 or self.windows() != [self.hwnd]:
            raise ValueError("owned Notepad window changed or closed")
        if self.pid_of(self.hwnd)!=self.pid or not self.user.IsWindowEnabled(self.hwnd):
            raise ValueError("Notepad is blocked by a dialog or changed owner")
        title=self.title(self.hwnd)
        if title not in (self.initial_title,"*"+self.initial_title,"* "+self.initial_title):
            raise ValueError("document title changed; session halted")
        handle=self.user.GetDlgItem(self.hwnd,15)
        if (not handle or self.pid_of(handle)!=self.pid or self.user.GetParent(handle)!=self.hwnd
                or self.class_name(handle)!="Edit"):
            raise ValueError("expected classic Notepad edit control is missing")
        length=C.c_size_t()
        if (not self.user.SendMessageTimeoutW(handle,0x000e,0,0,2,500,C.byref(length))
                or length.value > 2000):
            raise ValueError("Notepad draft exceeds its 2000-character scope or is unresponsive")
        root=self.automation.ElementFromHandle(self.hwnd)
        edit=self.automation.ElementFromHandle(handle)
        if (root.CurrentProcessId!=self.pid or root.CurrentClassName!="Notepad"
                or edit.CurrentProcessId!=self.pid or edit.CurrentClassName!="Edit"
                or edit.CurrentControlType!=50004 or edit.CurrentNativeWindowHandle!=handle
                or edit.CurrentIsPassword or not edit.CurrentIsEnabled):
            raise ValueError("UI Automation control identity changed")
        pattern=edit.GetCurrentPattern(10002).QueryInterface(self.U.IUIAutomationValuePattern)
        if pattern.CurrentIsReadOnly:
            raise ValueError("Notepad value control is read-only")
        text=pattern.CurrentValue.replace("\r\n","\n")
        if len(text)>2000:
            raise ValueError("Notepad draft exceeds its text scope")
        self.pump()
        if self.tainted:
            raise ValueError("Notepad menu/dialog activity changed scope; session halted")
        self._pattern=pattern
        return Snapshot(text,title,self.hwnd,int(handle),tuple(root.GetRuntimeId()),tuple(edit.GetRuntimeId()))

    def set_text(self,text):
        # State machine calls snapshot immediately before this. Fixed UIA operation
        # only: no key injection, clicks, focus routing, clipboard or generic messages.
        self._pattern.SetValue(text)

    def close(self):
        if self.hook:
            self.user.UnhookWinEvent(self.hook);self.hook=None
        if self.job:
            self.job.close();self.job=None
        elif self.process:
            self.kernel.TerminateProcess(self.process,1)
        for name in ("thread","process"):
            handle=getattr(self,name,None)
            if handle:
                self.kernel.CloseHandle(handle);setattr(self,name,None)

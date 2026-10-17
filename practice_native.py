"""Disposable native Windows app: draft/saved text live only in RAM."""
import ctypes as C
from ctypes import wintypes as W
import os


def run(connection, token):
    user = C.WinDLL("user32", use_last_error=True)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleHandleW.restype = W.HMODULE
    user.CreateWindowExW.restype = W.HWND
    user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
        C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p]
    user.DefWindowProcW.restype = C.c_ssize_t
    user.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user.SetWindowTextW.argtypes = [W.HWND, W.LPCWSTR]
    user.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    user.SetTimer.argtypes = [W.HWND, C.c_size_t, W.UINT, C.c_void_p]
    CALLBACK = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    controls = {}
    state = {"draft": "", "saved": "", "undo": None}
    updating = False

    def read(hwnd):
        data = C.create_unicode_buffer(1001)
        user.GetWindowTextW(hwnd, data, len(data))
        return data.value

    def restore(draft, saved):
        nonlocal updating
        updating = True
        state["draft"], state["saved"] = draft, saved
        user.SetWindowTextW(controls[101], draft)
        user.SetWindowTextW(controls[102], saved)
        updating = False

    @CALLBACK
    def proc(hwnd, message, wp, lp):
        if message == 0x0111 and controls:  # WM_COMMAND
            ident, notification = wp & 0xFFFF, (wp >> 16) & 0xFFFF
            if ident == 101 and notification == 0x0300 and not updating:  # EN_CHANGE
                current = read(controls[101])
                if current != state["draft"]:
                    state["undo"] = (state["draft"], state["saved"])
                    state["draft"] = current
            elif ident in (201, 202) and notification == 0:
                state["undo"] = (state["draft"], state["saved"])
                restore("" if ident == 202 else state["draft"],
                        state["draft"] if ident == 201 else state["saved"])
            elif ident == 203 and notification == 0 and state["undo"] is not None:
                before, state["undo"] = state["undo"], None
                restore(*before)
            return 0
        if message == 0x0113:  # WM_TIMER: tiny private IPC control, not a tool API
            try:
                # Multiline EDIT does not always emit EN_CHANGE for WM_SETTEXT
                # (used by UIA SetValue). Observe its actual value before replying.
                current = read(controls[101])
                if current != state["draft"]:
                    state["undo"] = (state["draft"], state["saved"])
                    state["draft"] = current
                if connection.poll():
                    command = connection.recv()
                    if command == "state":
                        connection.send(dict(state))
            except (EOFError, OSError):
                user.DestroyWindow(hwnd)
            return 0
        if message == 0x0002:
            user.PostQuitMessage(0)
            return 0
        return user.DefWindowProcW(hwnd, message, wp, lp)

    class WindowClass(C.Structure):
        _fields_ = [("style", W.UINT), ("proc", CALLBACK), ("class_extra", C.c_int),
                    ("window_extra", C.c_int), ("instance", W.HINSTANCE), ("icon", W.HICON),
                    ("cursor", W.HANDLE), ("background", W.HBRUSH),
                    ("menu", W.LPCWSTR), ("name", W.LPCWSTR)]
    instance = kernel.GetModuleHandleW(None)
    name = "AgentPractice" + token
    wc = WindowClass(0, proc, 0, 0, instance, None, None, W.HBRUSH(6), None, name)
    if not user.RegisterClassW(C.byref(wc)):
        raise C.WinError(C.get_last_error())
    hwnd = user.CreateWindowExW(0, name, "Agent Practice - " + token[:8],
        0x00CF0000, 100, 100, 760, 480, None, None, instance, None)
    if not hwnd:
        raise C.WinError(C.get_last_error())

    def control(ident, cls, label, style, x, y, width, height):
        value = user.CreateWindowExW(0, cls, label, 0x50000000 | style,
            x, y, width, height, hwnd, W.HMENU(ident), instance, None)
        if not value:
            raise C.WinError(C.get_last_error())
        controls[ident] = value

    control(301, "STATIC", "PRACTICE ONLY - no real files, accounts, messages or websites", 0, 20, 15, 700, 30)
    control(302, "STATIC", "Draft text:", 0, 20, 55, 650, 25)
    control(101, "EDIT", "", 0x00800000 | 0x0004 | 0x1000 | 0x00200000, 20, 80, 700, 100)
    user.SendMessageW(controls[101], 0x00C5, 500, 0)  # EM_LIMITTEXT
    control(201, "BUTTON", "Save draft in RAM", 0, 20, 200, 200, 35)
    control(202, "BUTTON", "Clear draft", 0, 240, 200, 150, 35)
    control(203, "BUTTON", "Undo", 0, 410, 200, 120, 35)
    control(303, "STATIC", "Saved draft (RAM only):", 0, 20, 250, 650, 25)
    control(102, "STATIC", "", 0x00800000, 20, 280, 700, 100)
    user.SetTimer(hwnd, 1, 25, None)
    user.ShowWindow(hwnd, 1)
    user.UpdateWindow(hwnd)
    connection.send({"hwnd": int(hwnd), "pid": os.getpid()})
    message = W.MSG()
    while user.GetMessageW(C.byref(message), None, 0, 0) > 0:
        user.TranslateMessage(C.byref(message))
        user.DispatchMessageW(C.byref(message))

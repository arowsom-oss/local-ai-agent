"""Temporary global stop hotkey; never changes registry/security settings."""
import threading


def start_hotkey(on_stop, on_status=lambda text: None):
    def listen():
        import ctypes as C
        from ctypes import wintypes as W
        user = C.WinDLL("user32", use_last_error=True)
        ident = 0xA119
        if not user.RegisterHotKey(None, ident, 0x4003, 0x78):  # Ctrl+Alt+F9, no repeats
            on_status("Global stop shortcut unavailable; use the Stop button or F12 in this window.")
            return
        on_status("Global stop shortcut: Ctrl+Alt+F9. F12 also works in the chat window.")
        try:
            message = W.MSG()
            while user.GetMessageW(C.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == ident:
                    on_stop()
        finally:
            user.UnregisterHotKey(None, ident)
    thread = threading.Thread(target=listen, name="agent-stop-hotkey", daemon=True)
    thread.start()
    return thread

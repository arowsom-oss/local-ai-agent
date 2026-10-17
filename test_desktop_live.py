"""Real owned Win32/UIA/Job tests. No other applications or user files touched."""
import ctypes as C
from ctypes import wintypes as W
import re
import threading
import time
import desktop_tools as desktop
from process_guard import Worker


def number(text, label):
    match = re.search(r"\[(\d+)\] (?:text box|button) " + re.escape(label), text)
    assert match, text
    return int(match.group(1))


def hang(connection, initial):
    connection.send({"ready": True})
    connection.recv()
    time.sleep(30)


def test_blocking_worker_can_be_killed_without_waiting_for_io_lock():
    worker = Worker(hang, memory_mb=256)
    try:
        assert worker.receive()["ready"]
        results = []
        thread = threading.Thread(target=lambda: results.append(worker.request({"hang": True}, timeout=30)))
        thread.start()
        time.sleep(0.1)
        started = time.monotonic()
        worker.stop()
        thread.join(timeout=2)
        assert not thread.is_alive() and not worker.process.is_alive()
        assert time.monotonic() - started < 2
        assert "error" in results[0]
    finally:
        worker.stop()


def test_hotkey_thread_receives_its_own_stop_message():
    from emergency_hotkey import start_hotkey
    ready, stopped = threading.Event(), threading.Event()
    status = []
    thread = start_hotkey(stopped.set, lambda text: (status.append(text), ready.set()))
    assert ready.wait(3)
    if "unavailable" in status[0]:
        raise AssertionError("global hotkey unavailable in this fixture")
    user = C.WinDLL("user32", use_last_error=True)
    assert user.PostThreadMessageW(thread.native_id, 0x0312, 0xA119, 0)
    assert stopped.wait(2)
    user.PostThreadMessageW(thread.native_id, 0x0012, 0, 0)
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_native_uia_changes_verify_undo_and_refuse_stale_targets():
    assert not desktop.desktop_start().startswith("Error:")
    try:
        text = desktop.desktop_read()
        box = number(text, "Draft text")
        assert "error" in desktop.prepare_action("type", True, "x")
        assert "error" in desktop.prepare_action("click", box)
        assert "error" in desktop.prepare_action("type", box, "x" * 501)
        change = desktop.prepare_action("type", box, "Practice only")
        assert change["preview"]["after"]["draft"] == "Practice only"
        assert desktop.execute_approved(change["token"]).startswith("Practice action verified")
        assert desktop.execute_approved(change["token"]).startswith("Error:")
        text = desktop.desktop_read()
        assert "Practice only" in text
        assert "error" in desktop.prepare_action("type", box, "stale")
        save = desktop.prepare_action("click", number(text, "Save draft in RAM"))
        assert not desktop.execute_approved(save["token"]).startswith("Error:")
        text = desktop.desktop_read()
        undo = desktop.prepare_action("click", number(text, "Undo"))
        assert not desktop.execute_approved(undo["token"]).startswith("Error:")
        text = desktop.desktop_read()
        assert 'Saved in RAM: ""' in text
        change = desktop.prepare_action("type", number(text, "Draft text"), "Approved text")
        # Simulate a person changing this owned app after the approval preview.
        user = C.WinDLL("user32", use_last_error=True)
        user.FindWindowExW.argtypes = [W.HWND, W.HWND, W.LPCWSTR, W.LPCWSTR]
        user.FindWindowExW.restype = W.HWND
        user.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, C.c_void_p]
        user.SendMessageW.restype = C.c_ssize_t
        edit = user.FindWindowExW(desktop._session.identity["hwnd"], None, "EDIT", None)
        new_text = C.c_wchar_p("Person changed this")
        assert edit and user.SendMessageW(edit, 0x000C, 0, C.cast(new_text, C.c_void_p))
        check = C.create_unicode_buffer(501)
        user.SendMessageW(edit, 0x000D, 501, C.cast(check, C.c_void_p))
        assert check.value == "Person changed this"
        assert desktop.execute_approved(change["token"]).startswith("Error:")
        text = desktop.desktop_read()
        assert "Person changed this" in text and "Approved text" not in text
        change = desktop.prepare_action("type", number(text, "Draft text"), "line one\nline two")
        assert not desktop.execute_approved(change["token"]).startswith("Error:")
        image = desktop.capture_practice()
        assert 0 < image.width <= 1536 and 0 < image.height <= 1536

        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        kernel.OpenProcess.restype = W.HANDLE
        kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        kernel.CloseHandle.argtypes = [W.HANDLE]
        pids = [desktop._session.worker.process.pid, desktop._session.identity["pid"]]
        handles = [kernel.OpenProcess(0x100000, False, pid) for pid in pids]
        assert all(handles)
        desktop.close_desktop()
        try:
            assert all(kernel.WaitForSingleObject(handle, 1500) == 0 for handle in handles)
        finally:
            for handle in handles:
                kernel.CloseHandle(handle)
        assert desktop.desktop_read().startswith("Error:")
    finally:
        desktop.close_desktop()


if __name__ == "__main__":
    test_blocking_worker_can_be_killed_without_waiting_for_io_lock()
    print("PASS hard-stop blocked worker")
    test_hotkey_thread_receives_its_own_stop_message()
    print("PASS global hotkey registered and owned-thread message handled (no keyboard injection)")
    test_native_uia_changes_verify_undo_and_refuse_stale_targets()
    print("PASS real practice UIA, preview binding, verification, stale/refusal, undo, window capture and process-tree cleanup")

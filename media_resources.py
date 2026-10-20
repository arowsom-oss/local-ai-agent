"""Small Windows memory checks; estimates are admission checks, not OS isolation."""
import ctypes
import threading

GIB = 1024 ** 3


def available_ram():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                    ("page_total", ctypes.c_ulonglong), ("page_free", ctypes.c_ulonglong),
                    ("virtual_total", ctypes.c_ulonglong), ("virtual_free", ctypes.c_ulonglong),
                    ("extended", ctypes.c_ulonglong)]
    status = Memory()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ValueError("could not inspect available system memory")
    return status.available


def require_ram(gib):
    if available_ram() < gib * GIB:
        raise ValueError(f"at least {gib} GiB of free system RAM is required; close other applications first")


def receive_with_ram_guard(worker, timeout, stop_event=None, reserve_gib=2):
    """Stop only our worker if sampled available RAM approaches the system reserve."""
    finished, low = threading.Event(), threading.Event()
    def watch():
        while not finished.wait(.25):
            try:
                problem = available_ram() < reserve_gib * GIB
            except Exception:
                problem = True
            if problem:
                low.set()
                worker.stop()
                return
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        result = worker.receive(timeout, stop_event)
        return {"error":"media job stopped to preserve free system RAM; review before retrying"} if low.is_set() else result
    finally:
        finished.set()
        thread.join(1)

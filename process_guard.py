"""Owned worker processes with Windows Job Object cleanup, not an OS sandbox."""
from __future__ import annotations
import atexit
import ctypes as C
from ctypes import wintypes as W
import multiprocessing as mp
import os
import threading
import time

_workers = set()
_guard = threading.Lock()


class Job:
    def __init__(self, pid, memory_mb=2048):
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects are required")
        k = C.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]
        k.CreateJobObjectW.restype = W.HANDLE
        k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        k.OpenProcess.restype = W.HANDLE
        k.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
        k.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
        k.TerminateJobObject.argtypes = [W.HANDLE, W.UINT]
        k.CloseHandle.argtypes = [W.HANDLE]

        class Basic(C.Structure):
            _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                        ("flags", W.DWORD), ("min_ws", C.c_size_t), ("max_ws", C.c_size_t),
                        ("processes", W.DWORD), ("affinity", C.c_size_t),
                        ("priority", W.DWORD), ("scheduling", W.DWORD)]
        class IO(C.Structure):
            _fields_ = [(f"v{i}", C.c_uint64) for i in range(6)]
        class Extended(C.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", C.c_size_t),
                        ("job_memory", C.c_size_t), ("peak_process", C.c_size_t),
                        ("peak_job", C.c_size_t)]
        self.k, self.handle = k, k.CreateJobObjectW(None, None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x100 | 0x200  # kill on close, process/job commit bounds
        limits.process_memory = limits.job_memory = memory_mb * 1024 * 1024
        process = None
        try:
            if not k.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            process = k.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
            if not process or not k.AssignProcessToJobObject(self.handle, process):
                raise C.WinError(C.get_last_error())
        except Exception:
            self.close()
            raise
        finally:
            if process:
                k.CloseHandle(process)

    def close(self):
        handle, self.handle = self.handle, None
        if handle:
            self.k.TerminateJobObject(handle, 1)
            self.k.CloseHandle(handle)


def _entry(connection, target, initial):
    try:
        # No task or descendants may run before the parent assigns the Job.
        if connection.recv() != "start":
            return
        target(connection, initial)
    except Exception:
        try:
            connection.send({"error": "worker failed; no further action is allowed"})
        except Exception:
            pass
    finally:
        connection.close()


class Worker:
    def __init__(self, target, initial=None, memory_mb=2048):
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_entry, args=(child, target, initial))
        self.io_lock = threading.Lock()
        self.dead = threading.Event()
        self.stop_lock = threading.Lock()
        self.job = None
        self.process.start()
        child.close()
        try:
            self.job = Job(self.process.pid, memory_mb)
            self.connection.send("start")
        except Exception:
            self.stop()
            raise
        with _guard:
            _workers.add(self)

    def receive(self, timeout=15, stop_event=None):
        deadline = time.monotonic() + timeout
        while not self.dead.is_set() and time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                self.stop()
                return {"error": "stopped by the user"}
            try:
                if self.connection.poll(0.05):
                    return self.connection.recv()
            except (EOFError, OSError):
                break
        self.stop()
        return {"error": "worker stopped or timed out"}

    def request(self, payload, timeout=15, stop_event=None):
        with self.io_lock:
            if self.dead.is_set():
                return {"error": "worker has stopped; start a new session"}
            try:
                self.connection.send(payload)
                return self.receive(timeout, stop_event)
            except (EOFError, OSError):
                self.stop()
                return {"error": "worker disconnected"}

    def stop(self):
        # Does not acquire io_lock: Stop can terminate a blocked COM/decoder call.
        if not self.stop_lock.acquire(blocking=False):
            return
        try:
            self._stop()
        finally:
            self.stop_lock.release()

    def _stop(self):
        self.dead.set()
        if self.job is not None:
            self.job.close()
        elif self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=0.2)
        try:
            self.connection.close()
        except OSError:
            pass
        with _guard:
            _workers.discard(self)


def stop_all() -> str:
    with _guard:
        workers = list(_workers)
    for worker in workers:
        worker.stop()
    return "Owned desktop/media/generation workers stopped."


atexit.register(stop_all)

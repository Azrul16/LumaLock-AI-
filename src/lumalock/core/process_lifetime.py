"""Ensure owned AI workers cannot outlive the server's terminal on Windows."""

import ctypes
import os
import threading
from ctypes import wintypes

_groups = set()
_lock = threading.Lock()


class ChildProcessGroup:
    """Only AI workers join this job; the user's browser is never assigned."""

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        size_t = ctypes.c_size_t

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_working_set", size_t),
                ("max_working_set", size_t),
                ("process_limit", wintypes.DWORD),
                ("affinity", size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class Counters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits),
                ("io", Counters),
                ("process_memory", size_t),
                ("job_memory", size_t),
                ("peak_process_memory", size_t),
                ("peak_job_memory", size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.get_last_error()
            kernel.CloseHandle(handle)
            raise ctypes.WinError(error)
        self.handle = handle
        with _lock:
            _groups.add(self)

    def attach(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(
            self.handle, int(process._handle)
        ):
            error = ctypes.get_last_error()
            process.terminate()
            process.wait(timeout=10)
            raise ctypes.WinError(error)

    def close(self):
        with _lock:
            if self.handle:
                self.kernel.CloseHandle(self.handle)
                self.handle = None
            _groups.discard(self)


def close_owned_workers():
    with _lock:
        groups = list(_groups)
    for group in groups:
        group.close()

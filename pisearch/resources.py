"""Conservative memory checks for digit computations."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Optional

BYTES_PER_DIGIT_BUDGET = 64
MEMORY_RESERVE_BYTES = 1 * 1024**3
UNKNOWN_MEMORY_MAX_DIGITS = 100_000


def available_physical_memory() -> Optional[int]:
    """Return currently available physical RAM, or None if it cannot be read."""
    if sys.platform == "win32":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_status = kernel32.GlobalMemoryStatusEx
        get_status.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        get_status.restype = wintypes.BOOL
        if get_status(ctypes.byref(status)):
            return int(status.ullAvailPhys)
        return None

    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    return int(pages * page_size) if pages > 0 and page_size > 0 else None


def estimated_peak_bytes(n_digits: int) -> int:
    """Estimate working memory, including one GiB reserved for the OS."""
    return MEMORY_RESERVE_BYTES + n_digits * BYTES_PER_DIGIT_BUDGET


def resource_warning(n_digits: int, available_bytes: Optional[int]) -> Optional[str]:
    """Return a user-facing block message when a request exceeds the budget."""
    estimate = estimated_peak_bytes(n_digits)
    if available_bytes is None:
        if n_digits > UNKNOWN_MEMORY_MAX_DIGITS:
            return (
                "Available RAM could not be checked. For safety, this system is "
                f"limited to {UNKNOWN_MEMORY_MAX_DIGITS:,} digits per computation."
            )
        return None
    if estimate <= available_bytes:
        return None

    estimate_gib = estimate / 1024**3
    available_gib = available_bytes / 1024**3
    return (
        f"This selection may need about {estimate_gib:.1f} GiB of working memory, "
        f"but only {available_gib:.1f} GiB of RAM is currently available. "
        "Choose a smaller digit count to avoid exhausting system memory and "
        "triggering heavy page-file use."
    )

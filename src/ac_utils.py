"""
Assetto Corsa Utility Functions
Helper functions for reading and processing AC shared memory data
"""

import mmap
import ctypes


def open_shared_memory_try(name, size):
    """
    Try to open AC shared memory with fallback strategies

    Args:
        name: Name of the shared memory region
        size: Size of the memory region

    Returns:
        mmap object connected to AC shared memory

    Raises:
        Exception if connection fails
    """
    candidates = [name, "Local\\" + name, "Global\\" + name]
    last_exc = None
    for cand in candidates:
        try:
            return mmap.mmap(-1, size, cand)
        except Exception as e:
            last_exc = e
    raise last_exc


def decode_c_wchar_array(arr):
    """
    Safely decode C wide character arrays

    Args:
        arr: C wide character array

    Returns:
        Decoded string without null terminators
    """
    try:
        s = "".join(arr)
    except Exception:
        try:
            s = str(arr)
        except Exception:
            s = ""
    return s.split('\x00', 1)[0]


def ms_to_timestr(ms):
    """
    Convert milliseconds to formatted lap time string

    Args:
        ms: Time in milliseconds

    Returns:
        Formatted string like "1:23.456" or "" if invalid
    """
    try:
        if not isinstance(ms, int) or ms <= 0:
            return ""
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{minutes}:{seconds:02d}.{millis:03d}"
    except Exception:
        return ""

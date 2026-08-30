"""Return freed heap back to the OS after a big job.

glibc keeps per-thread malloc arenas and does not hand freed memory back to the OS on
its own, so a long streaming synthesis leaves the worker at a multi-GB high-water that
never settles. Buffered bursts are already capped by ``MALLOC_ARENA_MAX=2`` (set in the
systemd unit); streaming is the path that still retains, because each chunk's synthesis
buffers churn through the threadpool arenas. ``trim_heap`` calls glibc's ``malloc_trim``
to release the free top-of-heap across all arenas.

Best-effort by design: a no-op on platforms without glibc (musl, macOS) and it never
raises — memory hygiene must not be able to fail a request.
"""

from __future__ import annotations

import ctypes
import ctypes.util

_malloc_trim = None
try:
    _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    _malloc_trim = _libc.malloc_trim  # int malloc_trim(size_t pad)
    _malloc_trim.argtypes = [ctypes.c_size_t]
    _malloc_trim.restype = ctypes.c_int
except (OSError, AttributeError):
    _malloc_trim = None  # non-glibc libc: nothing to trim


def trim_heap() -> None:
    """Ask glibc to return free heap to the OS. No-op off glibc; never raises."""
    if _malloc_trim is None:
        return
    try:
        _malloc_trim(0)
    except Exception:  # noqa: BLE001 — cleanup must never break the caller
        pass

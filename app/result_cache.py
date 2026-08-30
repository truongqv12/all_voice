"""On-disk cache of encoded buffered-TTS results (dedup identical requests).

A repeated `POST /v1/audio/speech` with the same text + voice + format returns the
stored bytes with no synthesis. Only the *buffered* endpoint uses this; streaming
long-read (`/v1/audio/stream`) is never cached, so the win is on short repeated
clips (a preview line, a UI tooltip), not whole books.

Reuses previews' atomic write (crash-safe, WORKERS>=2-safe via a unique tmp name).
Eviction is NEW code — previews has no size-based LRU (only orphan pruning): a
background sweep (never the hot `put` path) trims the cache to `result_cache_max_mb`
and `result_cache_max_files` in access order (oldest mtime first), tolerating
concurrent unlinks with `missing_ok=True` (#11).

Note: VieNeu's synthesis is internally stochastic, so a cached clip is one frozen
take, not a fresh render each call — an accepted trade for reusing work already done.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from .config import get_settings
from .logging_config import get_logger
from .previews import _atomic_write  # crash-safe, unique-tmp atomic write (reused)

_log = get_logger("cache")
_MB = 1024 * 1024
# One sweep at a time; also serialises against nothing else (writes are atomic).
_evict_lock = threading.Lock()


def _root() -> Path:
    return Path(get_settings().result_cache_dir)


def key(model: str, voice: str, text: str, speed: float, fmt: str, options: dict | None) -> str:
    """Stable content key. `options` (e.g. `style`) is folded in sorted so key
    order never matters; `speed` is included because speed-aware backends differ."""
    opts = "&".join(f"{k}={options[k]}" for k in sorted(options)) if options else ""
    raw = f"{model}\x00{voice}\x00{speed}\x00{fmt}\x00{opts}\x00{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _path(k: str) -> Path:
    # Fan out by the first byte so one directory never holds the whole cache.
    return _root() / k[:2] / f"{k}.bin"


def get(k: str) -> bytes | None:
    if not get_settings().result_cache_enabled:
        return None
    p = _path(k)
    try:
        data = p.read_bytes()
    except (FileNotFoundError, OSError):
        return None
    # Bump mtime so this entry counts as recently used for access-order eviction.
    try:
        os.utime(p, None)
    except OSError:
        pass
    return data


def put(k: str, data: bytes) -> None:
    if not get_settings().result_cache_enabled or not data:
        return
    try:
        _atomic_write(_path(k), data)
    except OSError as exc:  # a full/read-only disk must never break synthesis
        _log.warning("result cache write failed: %s", exc)


def evict() -> None:
    """Trim the cache to its size + file-count ceilings, oldest access first.

    Background only (a timer in create_app) — never called on the `put` hot path."""
    settings = get_settings()
    root = _root()
    if not root.exists():
        return
    max_bytes = settings.result_cache_max_mb * _MB
    max_files = settings.result_cache_max_files
    with _evict_lock:
        entries: list[tuple[float, int, Path]] = []
        total = 0
        for p in root.rglob("*.bin"):
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append((st.st_mtime, st.st_size, p))
            total += st.st_size
        if total <= max_bytes and len(entries) <= max_files:
            return
        entries.sort(key=lambda e: e[0])  # oldest access first
        count = len(entries)
        removed = 0
        for mtime, size, p in entries:
            if total <= max_bytes and count <= max_files:
                break
            p.unlink(missing_ok=True)  # tolerate a concurrent unlink
            total -= size
            count -= 1
            removed += 1
        if removed:
            _log.info("result cache evicted %d files (now %d, %.0f MB)", removed, count, total / _MB)

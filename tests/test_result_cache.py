"""Phase 2 — on-disk result cache: key stability, round-trip, LRU eviction.

All `not synth`: exercises the cache module directly with byte blobs (no TTS).
"""

from __future__ import annotations

import os

from app import result_cache
from app.config import Settings


def _cfg(tmp_path, **kw):
    return Settings(result_cache_dir=str(tmp_path / "cache"), **kw)


def test_key_is_stable_and_option_order_independent():
    k1 = result_cache.key("vieneu", "Trúc Ly", "hello", 1.0, "mp3", {"style": "a"})
    k2 = result_cache.key("vieneu", "Trúc Ly", "hello", 1.0, "mp3", {"style": "a"})
    assert k1 == k2
    # Different text / voice / style / speed / format -> different key.
    assert k1 != result_cache.key("vieneu", "Trúc Ly", "hello", 1.0, "mp3", {"style": "b"})
    assert k1 != result_cache.key("vieneu", "Trúc Ly", "HELLO", 1.0, "mp3", {"style": "a"})
    assert k1 != result_cache.key("vieneu", "Other", "hello", 1.0, "mp3", {"style": "a"})
    assert k1 != result_cache.key("vieneu", "Trúc Ly", "hello", 2.0, "mp3", {"style": "a"})
    assert k1 != result_cache.key("vieneu", "Trúc Ly", "hello", 1.0, "wav", {"style": "a"})
    # Option key ORDER must not change the hash.
    a = result_cache.key("m", "v", "t", 1.0, "mp3", {"a": "1", "b": "2"})
    b = result_cache.key("m", "v", "t", 1.0, "mp3", {"b": "2", "a": "1"})
    assert a == b


def test_put_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(result_cache, "get_settings", lambda: _cfg(tmp_path))
    result_cache.put("deadbeef", b"audio-bytes")
    assert result_cache.get("deadbeef") == b"audio-bytes"
    assert result_cache.get("never-written") is None


def test_disabled_cache_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(result_cache, "get_settings", lambda: _cfg(tmp_path, result_cache_enabled=False))
    result_cache.put("k", b"x")
    assert result_cache.get("k") is None


def test_eviction_trims_to_max_files_keeping_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        result_cache, "get_settings",
        lambda: _cfg(tmp_path, result_cache_max_files=2, result_cache_max_mb=10_000),
    )
    keys = [f"k{i:038d}" for i in range(5)]
    for k in keys:
        result_cache.put(k, b"x" * 100)
    # Set explicit, strictly increasing mtimes (avoids coarse-clock flakiness), then
    # bump the OLDEST key so it counts as most-recently-used.
    for i, k in enumerate(keys):
        os.utime(result_cache._path(k), (1000 + i, 1000 + i))
    os.utime(result_cache._path(keys[0]), (9999, 9999))  # keys[0] now newest

    result_cache.evict()

    survivors = {p.stem for p in (tmp_path / "cache").rglob("*.bin")}
    assert len(survivors) == 2
    assert keys[0] in survivors      # most-recently accessed kept
    assert keys[4] in survivors      # next newest kept
    assert keys[1] not in survivors  # oldest evicted


def test_eviction_trims_to_max_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        result_cache, "get_settings",
        lambda: _cfg(tmp_path, result_cache_max_files=10_000, result_cache_max_mb=0),
    )
    for i in range(3):
        result_cache.put(f"b{i:038d}", b"x" * 1024)
    result_cache.evict()  # max 0 MB -> everything over budget is swept
    remaining = list((tmp_path / "cache").rglob("*.bin"))
    assert remaining == []

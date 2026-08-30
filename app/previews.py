"""Per-voice audio previews ("nghe thử") — generate-once, cache-to-disk.

One `ensure_preview()` code path is reused by the HTTP endpoint (lazy self-heal),
the startup warm thread, and the clone-enrol hook. Backends stay untouched: this
module only calls the public `registry` / `backend.synthesize()` + shared
`encode()`.

Storage is a per-voice mp3 plus an atomic JSON sidecar (no central manifest), so
it is safe under WORKERS>=2 (no shared-file read-modify-write) and needs no
backend call to check staleness.

Concurrency: `_LOCK` guards ONLY the in-flight lock map (never held across synth
or file I/O); a per-voice lock coalesces same-voice generation; `_GEN_SEM` is a
preview-only CPU budget deliberately separate from the paid `synth_semaphore`, so
previews never consume the paid TTS/ASR concurrency budget. (One caveat: a backend
that serialises all synthesis behind a single engine lock — VieNeu does — still
sees a preview and a paid request contend for that engine lock for one synth's
duration; the separation is at the semaphore level, not that engine lock.)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import uuid
from pathlib import Path
from urllib.parse import quote

from .audio.encoder import encode
from .backends.registry import registry
from .config import get_settings
from .logging_config import get_logger
from .voice_store import voice_store

_FMT = "mp3"
# Guards ONLY the _INFLIGHT map (create/lookup). Never held across synth/file I/O.
_LOCK = threading.Lock()
# One lock per (model, voice_id) so callers coalesce on the same voice; different
# voices proceed independently.
_INFLIGHT: dict[str, threading.Lock] = {}
# Preview-only CPU budget. Deliberately NOT synth_semaphore (limits.py): previews
# are best-effort and must never consume the paid TTS/ASR budget. Clamp to >=1: a
# 0-permit BoundedSemaphore would block every preview synth forever.
_GEN_SEM = threading.BoundedSemaphore(max(1, get_settings().preview_concurrency))
_log = get_logger("previews")

#: Standard sample sentence per language; overridable via config.
DEFAULT_PASSAGES = {
    "vi": "Xin chào, đây là giọng đọc mẫu của all-voice. Chúc bạn một ngày tốt lành.",
    "en": "Hello, this is a sample voice from all voice. Have a wonderful day.",
    "ja": "こんにちは。これは all-voice のサンプル音声です。良い一日をお過ごしください。",
}


def passage_for(language: str) -> str:
    """Resolve the sample passage for `language`: config override -> built-in
    default -> the "vi" default (the default backend's language). Never empty."""
    settings = get_settings()
    override = getattr(settings, f"preview_text_{language}", "")
    if override:
        return override
    return DEFAULT_PASSAGES.get(language) or DEFAULT_PASSAGES["vi"]


def _root() -> Path:
    return Path(get_settings().previews_dir)


def _slug(s: str) -> str:
    """Filesystem-safe slug: sanitized text + short sha1 (handles spaces like
    "Trúc Ly", VOICEVOX `uuid:style` ids, and avoids collisions)."""
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "voice"
    return f"{base}_{hashlib.sha1(s.encode()).hexdigest()[:8]}"


def preview_path(model: str, voice_id: str) -> Path:
    return _root() / _slug(model) / f"{_slug(voice_id)}.{_FMT}"


def preview_url_for(model: str, voice_id: str) -> str:
    """Public URL of a voice's preview endpoint (ids percent-encoded)."""
    return f"/v1/voices/{quote(model, safe='')}/{quote(voice_id, safe='')}/preview"


def _text_hash(passage: str, style: str, fmt: str) -> str:
    return hashlib.sha1(f"{passage}\x00{style}\x00{fmt}".encode()).hexdigest()


def _sidecar_path(mp3: Path) -> Path:
    return mp3.with_suffix(f".{_FMT}.json")


def _atomic_write(path: Path, data: bytes) -> None:
    """Write bytes atomically. A unique tmp name (pid + uuid) avoids any
    cross-process/thread collision, so `os.replace` is safe under WORKERS>=2."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _write_sidecar(mp3: Path, meta: dict) -> None:
    _atomic_write(_sidecar_path(mp3), json.dumps(meta, ensure_ascii=False).encode())


def _read_sidecar(mp3: Path) -> dict | None:
    sc = _sidecar_path(mp3)
    try:
        return json.loads(sc.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def is_current(path: Path) -> bool:
    """True if the mp3 + sidecar exist and the sidecar's text_hash still matches
    the current passage for its language. Reads no backend — cheap hot-path check."""
    if not path.exists():
        return False
    meta = _read_sidecar(path)
    if not meta:
        return False
    expected = _text_hash(passage_for(meta.get("language", "vi")), meta.get("style", ""), _FMT)
    return meta.get("text_hash") == expected


def _find_voice(model: str, voice_id: str):
    """Exact lookup — never the lenient `registry.get` fallback (which would
    resolve an unknown model to the default backend). Returns (voice, backend)
    or None, so we never synth a voice the registry doesn't actually own."""
    if not registry.has(model):
        return None
    backend = registry.get(model)
    if backend is None:
        return None
    for v in backend.list_voices():
        if v.id == voice_id:
            return v, backend
    return None


def voice_exists(model: str, voice_id: str) -> bool:
    return _find_voice(model, voice_id) is not None


def _key(model: str, voice_id: str) -> str:
    return f"{model}/{voice_id}"


def _key_lock(model: str, voice_id: str) -> threading.Lock:
    """Per-voice lock so two callers for the same voice coalesce. `_LOCK` guards
    only the map lookup/creation and is released before any synth."""
    k = _key(model, voice_id)
    with _LOCK:
        lock = _INFLIGHT.get(k)
        if lock is None:
            lock = _INFLIGHT[k] = threading.Lock()
        return lock


def ensure_preview(model: str, voice_id: str, *, force: bool = False) -> Path | None:
    """Generate-or-return the cached preview for one voice.

    Returns the mp3 Path, or None when the voice is unknown or synth failed.
    Idempotent: a fresh cache short-circuits with no synth and no lock."""
    found = _find_voice(model, voice_id)
    if found is None:
        return None
    voice, backend = found
    path = preview_path(model, voice_id)
    passage = passage_for(voice.language)
    th = _text_hash(passage, "", _FMT)

    if not force and is_current(path):  # fresh cache -> no synth, no lock
        return path

    with _key_lock(model, voice_id):  # coalesce SAME voice; NOT the global lock
        if not force and is_current(path):  # re-check after acquiring
            return path
        with _GEN_SEM:  # preview CPU budget (not synth_semaphore)
            try:
                result = backend.synthesize(passage, voice_id, 1.0, {})
                audio = encode(result.pcm, result.sample_rate, _FMT)
            except Exception as exc:
                _log.warning("preview synth failed %s/%s: %s", model, voice_id, exc)
                return None
        if _find_voice(model, voice_id) is None:  # deleted mid-synth -> don't publish an orphan
            return None
        # Record clone-ness on the artifact so the serving route gates on the
        # cached file, not only live store membership — a store/backend divergence
        # (multi-worker post-delete, an orphan) can never downgrade a clone preview
        # to public. Monotonic per artifact: once a clone, a regeneration keeps the
        # marking even where the live store record has gone (a divergent worker);
        # delete removes the sidecar, so a genuinely reused id starts fresh.
        prior = _read_sidecar(path)
        is_clone = (voice_store.get(voice_id) is not None) or bool(prior and prior.get("is_clone"))
        _atomic_write(path, audio)
        _write_sidecar(path, {
            "text_hash": th, "language": voice.language, "style": "",
            "format": _FMT, "voice_id": voice_id, "model": model,
            "is_clone": is_clone,
        })
        return path


def preview_bytes(model: str, voice_id: str) -> bytes | None:
    """Cached-or-generated preview bytes (used by the endpoint's self-heal)."""
    p = ensure_preview(model, voice_id)
    return p.read_bytes() if p else None


def preview_b64_if_current(model: str, voice_id: str) -> str | None:
    """base64 of an already-fresh cached preview, or None. NEVER synthesizes —
    keeps `?preview=base64` from doing full-catalog inline synth on a cold cache."""
    p = preview_path(model, voice_id)
    return base64.b64encode(p.read_bytes()).decode() if is_current(p) else None


def sidecar_marks_clone(model: str, voice_id: str) -> bool:
    """True if a cached preview's sidecar records it as a clone. Lets the serving
    route fail closed: a clone artifact stays key-gated even if the live
    voice_store record has since gone (multi-worker delete, orphan)."""
    meta = _read_sidecar(preview_path(model, voice_id))
    return bool(meta and meta.get("is_clone"))


def remove_preview(model: str, voice_id: str) -> None:
    """Delete a voice's mp3 + sidecar (idempotent)."""
    p = preview_path(model, voice_id)
    p.unlink(missing_ok=True)
    _sidecar_path(p).unlink(missing_ok=True)


def _default_backend_name() -> str | None:
    default = registry.get(None)
    return default.name if default is not None else None


def warm_startup() -> None:
    """Eagerly warm the default backend's presets + all clones only. Leaves
    VOICEVOX/Kokoro to self-heal lazily so per-style VVM loading stays lazy."""
    default_name = _default_backend_name()
    for v in registry.all_voices():
        if v.model == default_name or voice_store.get(v.id) is not None:
            try:
                ensure_preview(v.model, v.id)
            except Exception as exc:  # one bad voice must not stop the warm
                _log.warning("warm preview failed %s/%s: %s", v.model, v.id, exc)


def build_all() -> None:
    """Rebuild previews for EVERY registered voice, then prune orphans (CLI)."""
    for v in registry.all_voices():
        try:
            ensure_preview(v.model, v.id, force=True)
        except Exception as exc:
            _log.warning("build preview failed %s/%s: %s", v.model, v.id, exc)
    prune_orphans()


def prune_orphans() -> None:
    """Remove previews (mp3 + sidecar) whose voice no longer exists, and sweep
    any leftover `*.tmp` from crashed writes."""
    root = _root()
    if not root.exists():
        return
    owned = {(v.model, v.id) for v in registry.all_voices()}
    for mp3 in root.rglob(f"*.{_FMT}"):
        meta = _read_sidecar(mp3)
        if not meta or (meta.get("model"), meta.get("voice_id")) not in owned:
            mp3.unlink(missing_ok=True)
            _sidecar_path(mp3).unlink(missing_ok=True)
    for tmp in root.rglob("*.tmp"):
        tmp.unlink(missing_ok=True)


def main() -> None:
    """CLI: rebuild every preview + prune. `uv run python -m app.previews`."""
    # Set BEFORE importing app.main: create_app() runs at module scope and reads
    # this flag. get_settings() is lru-cached and was already evaluated at THIS
    # module's import (the _GEN_SEM line), so clear the cache to make the new env
    # value take effect — otherwise create_app() reads the stale True and starts a
    # duplicate warm thread alongside build_all().
    os.environ["PREVIEW_WARM_ON_STARTUP"] = "false"
    get_settings.cache_clear()
    # Side effect: importing app.main runs create_app(), populating the registry.
    from . import main as _app  # noqa: F401

    build_all()
    _log.info("preview rebuild complete: %d voices", len(registry.all_voices()))


if __name__ == "__main__":
    main()

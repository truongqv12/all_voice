---
title: "Phase 1: Preview engine + config"
status: done
---

# Phase 1: Preview engine + config

## Overview

Build the generation/caching engine (`app/previews.py`) and its config knobs.
No HTTP surface yet — pure functions the later phases call. This is the DRY core:
one `ensure_preview()` reused by the endpoint, startup warm, and the clone hook.

> **Red-team revisions (applied):** (a) `_LOCK` is NEVER held across `synthesize()`
> — it guards only a per-voice in-flight map; (b) preview synthesis draws from a
> dedicated `preview_concurrency` budget, kept OFF the paid `synth_semaphore` so
> previews can't starve `/v1/audio/speech`+ASR; (c) the central `manifest.json` is
> replaced by an atomic **per-file sidecar** (`{slug}.mp3.json`) — no cross-process
> shared-file R-M-W (multi-worker safe), no O(N²) rewrite; (d) unique tmp names;
> (e) post-synth ownership re-check so a delete mid-synth never publishes an orphan;
> (f) sample-rate note corrected to 48000.

## Requirements

- [ ] Standard passage per language (vi/en/ja), overridable via config; sane fallback.
- [ ] Deterministic, filesystem-safe path per `(model, voice_id)` + an atomic sidecar recording `{text_hash, language, voice_id, model}`.
- [ ] `ensure_preview()` generates-or-returns a cached mp3 via the existing synth+encode path; staleness via the sidecar `text_hash`; idempotent.
- [ ] Concurrency: `_LOCK` guards only the in-flight map; a per-voice lock coalesces same-voice generation; a `preview_concurrency` semaphore bounds preview CPU **separately** from `synth_semaphore`.
- [ ] Atomic writes with a **unique** tmp name (multi-worker/thread safe); post-synth ownership re-check before publishing.
- [ ] `warm_startup()` (default backend presets + clones only), `build_all()` (everything, CLI), `prune_orphans()`, `remove_preview()`, `preview_bytes()`, `preview_b64_if_current()`, `is_current()`, `preview_url_for()`.
- [ ] Unknown `(model, voice_id)` → `None` (never synth a voice the registry doesn't own).

## Architecture

New module `app/previews.py`. Depends on `registry` (lookup + backend synth),
`encoder.encode`, `config.get_settings`, `logging_config`. No import cycle:
`registry` imports only `base`; `main`/routers import `previews`.

**Storage (no central manifest — sidecar per preview):**
- `data/previews/{slug(model)}/{slug(voice_id)}.mp3`
- `data/previews/{slug(model)}/{slug(voice_id)}.mp3.json` = `{"text_hash","language","style","format","voice_id","model"}`
- Sidecars are independent + atomic → safe under `WORKERS≥2` (`docs/deployment.md:68-78`); staleness needs no backend call (reads `language` + `text_hash` from the sidecar).

`slug(s)` = `re.sub(r"[^A-Za-z0-9._-]+","_", s).strip("_")` (empty → `"voice"`) +
`"_" + sha1(s.encode()).hexdigest()[:8]`. `text_hash` =
`sha1(f"{passage}\x00{style}\x00{fmt}".encode()).hexdigest()`. `_key(model, voice_id)` = `f"{model}/{voice_id}"`.

**Concurrency model:**
- `_LOCK = threading.Lock()` — guards ONLY the `_INFLIGHT` map (create/lookup). Never held across synth or file I/O.
- `_INFLIGHT: dict[str, threading.Lock]` — one lock per `(model, voice_id)` so two callers coalesce on the same voice; different voices proceed independently.
- `_GEN_SEM = threading.BoundedSemaphore(get_settings().preview_concurrency)` (default 1) — preview-only CPU budget. Deliberately NOT `synth_semaphore` (limits.py:12): previews are best-effort and must never consume the paid TTS/ASR budget → no starvation/priority-inversion.

## Related Code Files

- Create: `app/previews.py`
- Modify: `app/config.py` (new Settings fields)
- Modify: `.env.example` (document the new knobs)

## Implementation Steps

1. **Config** — add to `app/config.py::Settings`:
   ```python
   # --- Voice previews ("nghe thử") ---
   previews_dir: str = "data/previews"
   preview_warm_on_startup: bool = True
   # Dedicated CPU budget for preview generation, kept OFF synth_semaphore so
   # previews never starve paid /v1/audio/speech + ASR. 1 = one preview synth at a time.
   preview_concurrency: int = 1
   # Standard passage per language; empty string = use the built-in default.
   preview_text_vi: str = ""
   preview_text_en: str = ""
   preview_text_ja: str = ""
   ```

2. **Module skeleton + passages** `app/previews.py`:
   ```python
   from __future__ import annotations
   import base64, hashlib, json, os, re, threading, uuid
   from pathlib import Path
   from .audio.encoder import encode
   from .backends.registry import registry
   from .config import get_settings
   from .logging_config import get_logger

   _FMT = "mp3"
   _LOCK = threading.Lock()
   _INFLIGHT: dict[str, threading.Lock] = {}
   _GEN_SEM = threading.BoundedSemaphore(get_settings().preview_concurrency)
   _log = get_logger("previews")
   DEFAULT_PASSAGES = {
       "vi": "Xin chào, đây là giọng đọc mẫu của all-voice. Chúc bạn một ngày tốt lành.",
       "en": "Hello, this is a sample voice from all voice. Have a wonderful day.",
       "ja": "こんにちは。これは all-voice のサンプル音声です。良い一日をお過ごしください。",
   }
   ```

3. **Passage resolver** — `passage_for(language) -> str`: settings override
   `preview_text_{lang}` if non-empty, else `DEFAULT_PASSAGES.get(language)`, else the
   `"vi"` default (default backend's language). Never empty.

4. **Path / sidecar helpers**:
   - `_root()` = `Path(get_settings().previews_dir)`; `_slug(s)`; `preview_path(model, voice_id)`.
   - `preview_url_for(model, voice_id)` = `f"/v1/voices/{quote(model, safe='')}/{quote(voice_id, safe='')}/preview"` (used by the list router in Phase 2).
   - `_sidecar_path(mp3)` = `mp3.with_suffix(".mp3.json")`; `_write_sidecar(mp3, meta)` and `_read_sidecar(mp3)` — atomic tmp+replace, `ensure_ascii=False`.
   - `is_current(path) -> bool`: mp3 exists AND sidecar exists AND `sidecar["text_hash"] == _text_hash(passage_for(sidecar["language"]), sidecar.get("style",""), _FMT)`. Reads no backend — cheap hot-path check.
   - `_atomic_write(path, data)`: `path.parent.mkdir(parents=True, exist_ok=True)`; `tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")`; `try: tmp.write_bytes(data); os.replace(tmp, path) finally: tmp.unlink(missing_ok=True)`. Unique tmp → no cross-process/thread collision.

5. **Voice lookup** (exact, not lenient — verified correct against `registry.get`'s default fallback, registry.py:20-29):
   ```python
   def _find_voice(model, voice_id):
       if not registry.has(model):
           return None
       backend = registry.get(model)
       for v in backend.list_voices():
           if v.id == voice_id:
               return v, backend
       return None
   def voice_exists(model, voice_id) -> bool:
       return _find_voice(model, voice_id) is not None
   ```

6. **`ensure_preview(model, voice_id, *, force=False) -> Path | None`** — the core:
   ```python
   def ensure_preview(model, voice_id, *, force=False):
       found = _find_voice(model, voice_id)
       if found is None:
           return None
       voice, backend = found
       path = preview_path(model, voice_id)
       passage = passage_for(voice.language)
       th = _text_hash(passage, "", _FMT)
       if not force and is_current(path):        # fresh cache -> no synth, no lock
           return path
       with _key_lock(model, voice_id):          # coalesce SAME voice; NOT the global lock
           if not force and is_current(path):    # re-check after acquiring
               return path
           with _GEN_SEM:                         # preview CPU budget (not synth_semaphore)
               try:
                   result = backend.synthesize(passage, voice_id, 1.0, {})
                   audio = encode(result.pcm, result.sample_rate, _FMT)
               except Exception as exc:
                   _log.warning("preview synth failed %s/%s: %s", model, voice_id, exc)
                   return None
           if _find_voice(model, voice_id) is None:   # deleted mid-synth -> don't publish orphan
               return None
           _atomic_write(path, audio)
           _write_sidecar(path, {"text_hash": th, "language": voice.language,
                                 "style": "", "format": _FMT, "voice_id": voice_id, "model": model})
           return path
   ```
   `_key_lock(model, voice_id)` looks up/creates the per-voice lock under `_LOCK`
   (map access only; `_LOCK` released before synth). Note `synthesize(..., {})`
   passes an EMPTY options dict (not `{"style": ""}`), so VieNeu's style gate
   (vieneu_backend.py:127) never fires.

7. **Helpers for later phases**:
   - `preview_bytes(model, voice_id)`: `p = ensure_preview(...); return p.read_bytes() if p else None`.
   - `preview_b64_if_current(model, voice_id)`: `p = preview_path(...); return base64.b64encode(p.read_bytes()).decode() if is_current(p) else None` — **reads only a fresh cache, never synthesizes** (keeps `?preview=base64` from doing full-catalog inline synth).
   - `warm_startup()`: iterate `registry.all_voices()`; `ensure_preview` only when `v.model == default_backend` OR the voice is a clone (`voice_store.get(v.id) is not None`) — skips eager VOICEVOX/Kokoro warm so their lazy per-style VVM loading is preserved (voicevox_backend.py:6-11).
   - `build_all()`: `ensure_preview` for EVERY `registry.all_voices()` voice, catch+log per voice, then `prune_orphans()`. Used by the CLI full rebuild.
   - `prune_orphans()`: for each `*.mp3` under `_root()`, read its sidecar `(model, voice_id)`; if not in `{(v.model, v.id) for v in registry.all_voices()}`, unlink mp3 + sidecar. Also sweep leftover `*.tmp`.
   - `remove_preview(model, voice_id)`: unlink mp3 + sidecar (`missing_ok=True`).

## Todo

- [ ] Six `Settings` fields (incl. `preview_concurrency`) + `.env.example` docs.
- [ ] `app/previews.py`: passages, slug/path/sidecar helpers, `is_current`, `_atomic_write` (unique tmp), `_find_voice`/`voice_exists`.
- [ ] `ensure_preview` (lock only around map; `_GEN_SEM` around synth; post-synth ownership re-check).
- [ ] `preview_bytes`/`preview_b64_if_current`/`warm_startup`/`build_all`/`prune_orphans`/`remove_preview`/`preview_url_for`.
- [ ] Smoke against a FakeBackend stub (no real synth needed).

## Success Criteria

- [ ] `ensure_preview("vieneu", "<preset id>")` writes an mp3 + sidecar; a second call returns the same path without re-synthesizing (`is_current` hit).
- [ ] `ensure_preview("nope","x")` / `ensure_preview("vieneu","ghost")` return `None`, write nothing.
- [ ] Changing `preview_text_vi` makes `is_current` false → next call regenerates; unchanged config regenerates nothing.
- [ ] Two threads calling `ensure_preview` for the same voice produce one file, no corruption; tmp filenames are unique (grep the code: tmp name contains pid+uuid).
- [ ] `preview_b64_if_current` returns `None` for a missing/stale preview (never synthesizes).
- [ ] `uv run ruff check app/previews.py app/config.py` clean.

## Risk Assessment

- **Two separate CPU budgets** (`synth_semaphore`=2 for paid work + `preview_concurrency`=1 for previews) → worst-case 3 concurrent synths. Signal: CPU saturation on a 2-core box during warm. Response: `preview_concurrency` is configurable; lower/keep at 1, or set `preview_warm_on_startup=false`.
- **`is_current` trusts the sidecar language** — if a voice's language changes for the same id (unlikely; ids are stable), the hash could match a wrong passage. Signal: preview in the old language after a re-map. Response: include `voice_id`+`model` in the sidecar (done); a `force` rebuild (`python -m app.previews`) corrects it.
- **VieNeu returns `sample_rate=48000`** (vieneu_backend.py:137) — the encoder is rate-agnostic (encoder.py:88), so no action here; Phase 4's synth test must assert 48000, not the stdlib default 24000.

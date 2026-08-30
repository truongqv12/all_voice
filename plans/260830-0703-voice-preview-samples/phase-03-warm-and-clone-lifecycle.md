---
title: "Phase 3: Startup warm + clone lifecycle"
status: done
---

# Phase 3: Startup warm + clone lifecycle

## Overview

Make previews warm and self-maintaining: pre-generate the default backend's
presets (and existing clones) at startup without blocking boot or defeating
VOICEVOX's lazy loading, generate a preview when a new clone is enrolled, and
remove a clone's preview (mp3 + sidecar) when the clone is deleted.

> **Red-team revisions (applied):** (a) warm covers only the default backend +
> clones (VOICEVOX/Kokoro self-heal lazily so per-style VVM loading stays lazy);
> (b) a prerequisite backend fix makes VieNeu's `_get_engine()` thread-safe so the
> warm thread + a first request can't double-init the engine; (c) the CLI sets
> `PREVIEW_WARM_ON_STARTUP=false` before importing `app.main` to avoid a second
> warm; (d) delete removes the sidecar too; (e) `build_all` prunes orphans.

## Requirements

- [ ] Startup (gated by `preview_warm_on_startup`) runs `warm_startup()` in a background daemon thread — boot is not blocked, and only the default backend + clones are eagerly warmed.
- [ ] VieNeu `_get_engine()` is thread-safe (double-checked lock) so concurrent first callers never double-construct the engine.
- [ ] Enrolling a clone triggers best-effort preview generation; failure never affects the enrol response.
- [ ] Deleting a clone removes its mp3 + sidecar.
- [ ] `python -m app.previews` rebuilds ALL previews (+ prune) without a duplicate warm thread.

## Architecture

`warm_startup()` (Phase 1) iterates `registry.all_voices()` — which after
`_register_backends()` + `_reenrol_cloned_voices()` (main.py:113-114, ordering
verified) includes presets and persisted clones — but only generates for the
default backend and clones. A plain daemon thread makes it sequential; the
`_GEN_SEM` budget (Phase 1) bounds it against request-path/enrol generation.
Enrol/delete hooks live in `voices_admin.py`; the enrol hook is fire-and-forget
and Phase 1's post-synth ownership re-check prevents a delete-during-synth orphan.

## Related Code Files

- Modify: `app/backends/vieneu_backend.py` (thread-safe `_get_engine`) — prerequisite fix
- Modify: `app/main.py` (kick `warm_startup` after re-enrol, gated)
- Modify: `app/routers/voices_admin.py` (enrol → generate; delete → remove)
- Modify: `app/previews.py` (add `main()` / `__main__` for the CLI rebuild)

## Implementation Steps

1. **Prerequisite: thread-safe engine init** — in `app/backends/vieneu_backend.py::_get_engine`
   (currently unlocked, vieneu_backend.py:49-70; `synthesize` calls it outside
   `self._lock` at :133-134), wrap construction in the existing lock, double-checked:
   ```python
   def _get_engine(self):
       if self._engine is None:
           with self._lock:
               if self._engine is None:
                   ...construct + populate self._presets_cache...
       return self._engine
   ```
   Keeps `synthesize`'s own `with self._lock` around inference intact. Minimal,
   fixes the race for ALL callers (not just warm).

2. **Startup warm** — in `app/main.py::create_app`, after `_reenrol_cloned_voices()`:
   ```python
   if settings.preview_warm_on_startup:
       import threading
       from . import previews
       threading.Thread(target=previews.warm_startup, name="preview-warm", daemon=True).start()
       log.info("preview warm started (background, default backend + clones)")
   ```
   Do not `await`. `warm_startup` (not `build_all`) → VOICEVOX/Kokoro presets are
   NOT eagerly loaded.

3. **Enrol hook** — in `voices_admin.py::create_voice`, after the successful
   `backend.register_voice(...)` block, before `return`:
   ```python
   import threading
   from .. import previews
   threading.Thread(target=lambda: previews.ensure_preview(backend.name, record.id),
                    name=f"preview-{record.id}", daemon=True).start()
   ```

4. **Delete hook** — in `voices_admin.py::delete_custom_voice`, in the record
   branch (after `voice_store.delete`) and the registry-fallback branch:
   ```python
   from .. import previews
   previews.remove_preview(record.backend, voice_id)   # record branch
   previews.remove_preview(name, voice_id)              # fallback branch (per owning backend)
   ```

5. **CLI rebuild** — bottom of `app/previews.py`:
   ```python
   def main() -> None:
       os.environ["PREVIEW_WARM_ON_STARTUP"] = "false"  # BEFORE importing app.main
       from . import main as _app  # noqa: F401 — side effect: create_app() populates the registry
       build_all()                 # rebuild everything + prune
       _log.info("preview rebuild complete: %d voices", len(registry.all_voices()))

   if __name__ == "__main__":
       main()
   ```
   Setting the env var first means importing `app.main` (which runs
   `app = create_app()` at module scope, main.py:182) does NOT start a warm thread,
   so only the single foreground `build_all()` runs. Usage: `uv run python -m app.previews`.

## Todo

- [ ] vieneu_backend.py: double-checked lock in `_get_engine`.
- [ ] main.py: background `warm_startup` thread, config-gated, non-blocking.
- [ ] voices_admin.py enrol: fire-and-forget `ensure_preview` after successful enrol.
- [ ] voices_admin.py delete: `remove_preview` in record + fallback branches.
- [ ] `python -m app.previews` rebuild entry with the pre-import env guard.
- [ ] `uv run ruff check app/main.py app/routers/voices_admin.py app/previews.py app/backends/vieneu_backend.py` clean.

## Success Criteria

- [ ] App starts immediately with warm enabled; log shows "preview warm started"; VOICEVOX VVMs are NOT all loaded at boot (only default backend + clones warmed).
- [ ] Two concurrent first callers (warm thread + a synth request) never double-construct the VieNeu engine (guard by inspecting a debug log / single construction).
- [ ] After enrol, the clone's preview appears shortly; `GET .../preview` (with key) → 200 (self-heal covers the race).
- [ ] Deleting a clone removes its mp3 + sidecar; a later `GET .../preview` → 404 (or regenerates only if still owned).
- [ ] `uv run python -m app.previews` exits 0, (re)creates previews for all voices, prunes orphans, and logs exactly one rebuild (no duplicate warm).

## Risk Assessment

- **Backend edit** (`_get_engine`) touches a file the plan otherwise leaves alone. Signal: a VieNeu regression in existing synth tests. Response: the change is a pure double-checked-lock wrap of existing init; run `-m synth` VieNeu tests to confirm parity. Justified: the feature guarantees a concurrent first caller the old code never had.
- **Enrol thread vs immediate DELETE.** Signal: an orphan preview for a deleted clone. Mitigation: Phase 1's post-synth ownership re-check drops the write; `prune_orphans` (in `build_all`) reaps any that slip through. Response: if orphans recur, have `remove_preview` also write a short-lived tombstone the enrol thread checks.
- **Warm still competes for CPU** (bounded by `preview_concurrency`, default 1). Signal: sluggish first requests. Response: lower it or set `preview_warm_on_startup=false`.

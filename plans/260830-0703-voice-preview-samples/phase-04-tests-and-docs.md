---
title: "Phase 4: Tests + docs"
status: done
---

# Phase 4: Tests + docs

## Overview

Cover the feature with fast tests (FakeBackend → no real synth) plus a couple of
`synth`-marked real-backend checks, and document the field, the split-auth
endpoint, and the config knobs.

> **Red-team revisions (applied):** tests for the preset-public / clone-keyed
> split; base64 is cached-only (no synth in the list call); staleness regen;
> prune; unique tmp names; and the synth test asserts `sample_rate=48000`.

## Requirements

- [ ] Fast suite (`-m "not synth"`) exercises: preview_url presence, preset public 200, clone 401-without-key / 200-with-key, cached-only base64, 404 guards, delete removes mp3+sidecar, staleness regen, idempotent build — all via FakeBackend + an isolated previews dir.
- [ ] A `synth`-marked test verifies a real preset preview is valid non-silent audio at **48000 Hz**.
- [ ] Startup warm never slows the test import (disabled via env in conftest).
- [ ] README + deployment docs cover `preview_url`, the split-auth endpoint, `?preview=base64` (cached-only), the `data/previews` dir, and config knobs.

## Architecture

Reuse the `FakeBackend` pattern from `tests/test_multi_backend_e2e.py:53-98`
(Japanese preset + clone-capable via `ref_text`; `synthesize` returns 1s silence).
Point `previews_dir` at a pytest `tmp_path` by mutating the lru-cached `Settings`
singleton (`get_settings()`), and disable warm globally in conftest so importing
`app.main` (`app = create_app()`, main.py:182) stays instant.

## Related Code Files

- Create: `tests/test_previews.py`
- Modify: `tests/conftest.py` (top-level env guards before any app import)
- Modify: `README.md` (voices section)
- Modify: `docs/deployment.md` (previews cache + knobs)

## Implementation Steps

1. **conftest guards** — very top of `tests/conftest.py`, before importing `app.config`:
   ```python
   import os
   os.environ.setdefault("PREVIEW_WARM_ON_STARTUP", "false")
   ```

2. **Fixtures** (in `tests/test_previews.py`):
   ```python
   @pytest.fixture
   def previews_tmp(tmp_path, monkeypatch):
       from app.config import get_settings
       s = get_settings()  # lru-cached singleton; monkeypatch auto-reverts on teardown
       monkeypatch.setattr(s, "previews_dir", str(tmp_path / "previews"))
       yield tmp_path
   ```
   Plus a `with_fake_backend` fixture (copy the register/teardown from
   test_multi_backend_e2e.py:84-98). `AUTH = {"Authorization": "Bearer test-key"}`.

3. **Fast tests** (no `synth` mark — FakeBackend synth is instant):
   - `test_voices_carry_preview_url`: every `/v1/voices` item has non-empty `preview_url`; `preview_base64 is None`.
   - `test_preset_preview_public`: `GET /v1/voices/faketts/ja_1/preview` with **no** AUTH → 200, `audio/mpeg`, `Cache-Control` contains `public`, body non-empty.
   - `test_clone_preview_requires_key`: enrol a clone (`POST /v1/audio/voices`, multipart `model=faketts`, `ref_text=...`) → 200; `previews.ensure_preview("faketts", id)` to warm; `GET .../preview` **without** AUTH → 401; **with** AUTH → 200, `Cache-Control` contains `no-store`.
   - `test_base64_cached_only`: `GET /v1/voices?preview=base64` on a cold cache → the faketts/ja_1 item's `preview_base64 is None` (no synth in the list call); after `ensure_preview("faketts","ja_1")`, the same call returns base64 that decodes to the preview endpoint's bytes.
   - `test_unknown_voice_404`: `GET /v1/voices/faketts/ghost/preview` → 404 `preview_not_found`; `GET /v1/voices/nope/x/preview` → 404; assert no file under `tmp_path`.
   - `test_delete_removes_preview_and_sidecar`: enrol clone, warm, `DELETE /v1/audio/voices/{id}` → mp3 AND `.mp3.json` sidecar gone.
   - `test_staleness_regen`: warm faketts/ja_1; capture bytes; change `preview_text_ja` (monkeypatch settings); `GET .../preview` → `is_current` false → regenerated (assert bytes differ or sidecar text_hash changed).
   - `test_prune_orphans`: create a stray `data/previews/faketts/zzz.mp3`(+sidecar with a non-existent voice_id) under tmp; `previews.build_all()` → stray removed.
   - `test_atomic_tmp_unique`: assert the tmp name in `_atomic_write` includes pid+uuid (grep the source or generate two and compare names) — guards the multi-worker collision fix.
   - `test_passage_language_selection`: `passage_for("ja") != passage_for("vi")`; unknown language → vi passage.

4. **Synth tests** (`@pytest.mark.synth`, real VieNeu):
   - `test_real_preset_preview_is_audio`: first `vieneu` voice → `ensure_preview` → decode the mp3 → non-silent, duration > ~1s. If reusing `conftest.assert_real_audio`, pass **`expected_sr=48000`** (VieNeu returns 48000, vieneu_backend.py:137; the helper defaults to 24000 and hard-asserts, conftest.py:31) — or assert `len(content)`/duration only.

5. **Docs**:
   - README voices section: each `/v1/voices` item returns `preview_url`; **preset previews are public** (curl + `<audio src>` example); **clone previews need `Authorization: Bearer`**; `?preview=base64` inlines only already-warmed previews. One line: cached under `data/previews/`, warmed at startup (default backend + clones).
   - `docs/deployment.md`: `data/previews` (safe to delete; regenerates), `PREVIEW_WARM_ON_STARTUP`, `PREVIEW_CONCURRENCY`, `PREVIEW_TEXT_VI/EN/JA`; note under `WORKERS≥2` previews are per-file (sidecar) so no shared-manifest contention.

## Todo

- [ ] conftest env guard.
- [ ] `tests/test_previews.py`: fixtures + the fast tests above (incl. auth split, base64 cached-only, staleness, prune, tmp-uniqueness).
- [ ] `synth`-marked real-preset test asserting 48000 Hz.
- [ ] README + deployment docs.
- [ ] `uv run pytest -m "not synth" -q` green; `uv run ruff check` clean; spot-run one `-m synth` preview test.

## Success Criteria

- [ ] `uv run pytest tests/test_previews.py -m "not synth" -q` passes with no real synthesis, writing only under `tmp_path`; `data/previews` untouched.
- [ ] Preset-public and clone-keyed behaviors are both asserted (401 vs 200).
- [ ] base64 is proven cached-only (null before warm, present after).
- [ ] A `-m synth` test confirms a real vieneu preview is valid non-silent 48000 Hz audio.
- [ ] Full fast suite (`uv run pytest -m "not synth"`) still green (no regressions from schema/router/backend changes).

## Risk Assessment

- **lru-cached Settings mutation leaking across tests.** Signal: a later test sees the tmp previews_dir or changed passage. Mitigation: `monkeypatch.setattr` auto-reverts. Response: `get_settings.cache_clear()` in teardown if leakage appears.
- **Fire-and-forget enrol thread timing.** Mitigation: tests call `ensure_preview(...)` directly for determinism; the thread path is covered implicitly by the self-heal 200.
- **synth tests need VieNeu assets** (slow/CI-less): `-m synth`-gated, excluded from the fast lane, matching existing suites.

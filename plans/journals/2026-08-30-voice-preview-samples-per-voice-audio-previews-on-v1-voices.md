---
title: "voice-preview-samples: per-voice audio previews on /v1/voices"
date: 2026-08-30
summary: "Public preset preview_url + key-gated clone previews (base64 opt-in, disk sidecar cache, startup warm); code-reviewed, H1 public-clone exposure fixed."
---

# voice-preview-samples: per-voice audio previews on /v1/voices

## What happened
Implemented the `voice-preview-samples` plan (4 phases) end-to-end via `ak:cook --auto`.

- **Engine** (`app/previews.py`, new): one `ensure_preview()` reused by the HTTP route (lazy self-heal), the startup warm thread, and the clone-enrol hook. Generate-once → cache mp3 + atomic per-file JSON sidecar (no central manifest → WORKERS>=2 safe). `_LOCK` guards only the in-flight lock map (never across synth/IO); `_GEN_SEM` is a preview-only CPU budget separate from the paid `synth_semaphore`; unique pid+uuid tmp + `os.replace`; post-synth ownership re-check.
- **API** (`schemas.py`, `routers/voices.py`): `VoiceInfo` gains `preview_url` (always) + `preview_base64` (only when `?preview=base64` AND already cached — the list call never synthesizes). New `GET /v1/voices/{model}/{voice_id}/preview`: preset → public (`public, max-age=86400`), clone → Bearer-or-401 (`private, no-store`).
- **Lifecycle** (`main.py`, `voices_admin.py`, `vieneu_backend.py`): background `warm_startup` daemon (default backend + clones only; VOICEVOX/Kokoro stay lazy); enrol → fire-and-forget preview; delete → remove mp3 + sidecar; thread-safe `_get_engine()` (double-checked lock, engine published last).
- **Tests/docs**: `tests/test_previews.py` (FakeBackend, isolated tmp; 11 fast + 1 synth); README + `docs/deployment.md` + `.env.example`.

## Decision
- **Split auth (red-team finding 6/7):** preset previews public so a browser `<audio src>` plays with no header; clone previews render biometric timbre → require a key.
- **Intentional public-contract change:** relaxed `test_openapi_uses_bearer_security_scheme` for the one public preview route only; every other route + the no-`Authorization`-header check stay enforced.

## Code review outcome (code-reviewer subagent)
- **H1 (High, security) — FIXED:** clone-vs-preset was derived only from live `voice_store` membership; a store/backend divergence (multi-worker post-delete, orphan) could serve cloned audio publicly (reviewer reproduced 200 + public cache). Fix: sidecar records `is_clone` **monotonic per artifact** (regeneration never downgrades it; delete removes the sidecar so a reused id starts fresh), and the route gates on the fail-closed **union** of live store + cached sidecar. Regression test added.
- **M1 — FIXED:** `python -m app.previews` warm guard was a no-op (`get_settings` lru-cached at import) → duplicate warm thread. `get_settings.cache_clear()`.
- **M3 — FIXED:** new warm/enrol threads made VieNeu's unlocked `_custom` dict racy → `RuntimeError` on concurrent `list_voices`/enrol. Guarded reads (snapshot) + writes under `self._lock`.
- **M4 — FIXED:** softened the "previews can never starve paid TTS" docstring (VieNeu's single engine lock still contends).
- **L2 — FIXED:** `preview_concurrency=0` would hang forever; semaphore clamped `>=1`.
- **Deferred (documented):** M2 (base64 blocking reads in the loop for large warmed catalogs), L1 (anon first-synth trigger, bounded), L3 (`_INFLIGHT` unbounded growth), L4 (introspection test), L5 (O(N) registry re-parse in warm).

## Verification
- Fast suite: `72 passed` (`-m "not synth"`).
- Synth: real VieNeu preview non-silent **48000 Hz**; VieNeu synth+ASR round-trip passes (backend lock changes preserve parity).
- Lint: `ruff` is not a project dep and the repo has no ruff config; new code introduces no lint category absent from the existing app/tests baseline.

## Next steps
- Not committed yet (awaiting user go-ahead).
- If a multi-worker deploy is used, H1's fix is the load-bearing one — verified by the new divergence regression test.
- Optional future hardening: schedule `prune_orphans` (currently CLI-only), offload base64 building off the event loop (M2), evict `_INFLIGHT` (L3).

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

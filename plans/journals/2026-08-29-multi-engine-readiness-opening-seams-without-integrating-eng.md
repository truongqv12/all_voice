---
title: "Multi-engine readiness: opening seams without integrating engines"
date: 2026-08-29
summary: "Refactored TTS core so a 2nd multilingual backend is drop-in (routing/options/cloning/discovery seams); VieNeu unchanged, 63 tests green."
---

# Multi-engine readiness: opening seams without integrating engines

## What happened

Executed the accepted plan `plans/260829-1505-multi-engine-readiness/` end-to-end via `/ak:cook --auto`. Goal: make future engines (VoiceVox JA, F5-TTS EN) drop-in **without integrating a real engine now** and without breaking VieNeu. Design B (`model`+`voice`) confirmed.

Seams opened (all backward-compatible):
- **Routing gate** — `Registry.resolve(model) -> (backend, explicit)` beside the kept `get()`; `VoiceBackend.resolve_voice(voice, *, strict)` returns `None` on a strict miss. `speech.py` now 404s `unknown_voice` when an explicitly-named model lacks the voice; OpenAI-generic models (`tts-1`) stay lenient (drop-in preserved).
- **Options gate** — `InvalidOption(ValueError)`; schema `style` freed from `Literal` + new free-form `extra` bag; validation moved into the backend (VieNeu rejects unknown `style` -> 400 `invalid_option`). `backend_options()` merges `extra` then overlays named knobs (style wins).
- **Cloning readiness** — `register_voice(..., options=None)`; `VoiceRecord.enrol_options` (default_factory=dict, persisted, forward/backward compatible); enrol accepts `model` (explicit backend, gated on `registry.has` — not lenient) and `ref_text` (passed through, ignored by VieNeu, re-passed on restart re-enrol).
- **Discovery filter** — `GET /v1/voices?model=&language=` additive; unmatched -> 200 empty.

## Verification

- Full suite `uv run pytest -q`: **63 passed, 0 failures** (36 baseline + 27 new). Baseline confirmed green before app edits (test-first oracle `tests/test_readiness.py`).
- `tests/test_multi_backend_e2e.py`: a model-free `FakeBackend` (JA, clone-first requiring `ref_text`) plugs into models/voices/routing/strict-gate/cloning **without editing `app/**`** — proves the seams are genuinely open.
- code-reviewer (static): no critical/high defects; DONE_WITH_CONCERNS.

## Decisions

- Intentional behavior change: known model + unknown voice was 200 (first preset), now **404**. No existing test relied on it (verified).
- Error `code` for bad `style` shifts `invalid_request` -> `invalid_option` (status stays 400).
- `extra` left unbounded/unvalidated at the boundary — deferred to real adapters (safe today: VieNeu forwards only `style` to infer).
- Fixed a review finding: fast-loop guidance `-k "not synth"` -> `-m "not synth"` (`-k` also matched two fast tests whose names contain "synth"). Registered a `synth` pytest marker.

## Next steps

- Separate plans for the real **VoiceVox** (HTTP client, `/speakers`+`audio_query`) and **F5-TTS** (torch weights, ref-text synth) adapters.
- Real adapters that forward `extra` to a subprocess/HTTP call must whitelist keys there.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

---
title: "Multi-engine TTS: Kokoro (EN) + VOICEVOX (JA) backends"
date: 2026-08-29
summary: Two drop-in TTS engine adapters plugged into all-voice; core untouched; one High concurrency fix from review
---

# Multi-engine TTS: Kokoro (EN) + VOICEVOX (JA) backends

## What happened
Implemented plan `260829-2258-multi-engine-tts-kokoro-voicevox` (all 5 phases) — added two preset TTS engines as drop-in `VoiceBackend` adapters, no core changes:
- **Kokoro (English)** `app/backends/kokoro_backend.py`: 28 presets (20 US `a*` / 8 UK `b*`), table-driven, lazy ONNX + lock, accent-from-prefix, `espeak-ng` G2P error guard, lenient default → `af_heart`.
- **VOICEVOX (Japanese)** `app/backends/voicevox_backend.py`: `voicevox_core.blocking`, lazy per-VVM load (`_loaded`), cheap metadata discovery, `speed` via audio_query, embedded `VOICEVOX:<char>` credit, allowlist.
- Foundation: `en`/`ja` extras, guarded registration in `main.py::_register_backends()` (import-local, never raises + skip-log), `scripts/fetch-kokoro.sh` / `fetch-voicevox.sh`, config settings, `.gitignore`/`models/`.
- Tests: `conftest.py` helpers, `test_kokoro.py` / `test_voicevox.py` / `test_tts_asr_roundtrip.py` (synth-marked, skip-guarded), extended `test_multi_backend_e2e.py`. Docs: README engines table + EN/JA quick starts + credit, `kien-truc` §12, `deployment.md`, `.env.example`.

## Decision
- In-process, torch-free, 24kHz, no cloning for both — consistent with VieNeu ONNX pattern; encoder already sample-rate-agnostic so untouched.
- Engines register only when package + assets present (flag + `is_available(settings)`); missing → one log line, no raise. VieNeu stays default.
- Env lacks `kokoro_onnx`/`voicevox_core`/`espeak-ng`, so 8 engine synth tests skip by design (also proves the guards). 71 passed / 8 skipped / 0 failed.

## Review outcome
`code-reviewer`: DONE_WITH_CONCERNS. Fixed **High**: VOICEVOX `_get_synth()` ran outside `self._lock` while `_loaded` mutated inside → cold-start race could desync `_loaded` from `self._synth` and cause persistent 500s; moved synth acquisition inside the lock. Fixed **Medium**: added the missing skip-log (criterion 4). Fixed nit: removed dead `_SAMPLE_RATE`. Declined (documented): `DEFAULT_BACKEND`-stays-VieNeu is the plan's decision; Kokoro cold-start double-load is benign and matches the accepted VieNeu pattern.

## Next steps
- To exercise real EN/JA audio: `uv sync --extra en` + `apt-get install espeak-ng` + `bash scripts/fetch-kokoro.sh`; `uv sync --extra ja` + `bash scripts/fetch-voicevox.sh`; then `pytest -m synth` (WAVs land in `tests/output/`).
- Not committed yet — awaiting user go-ahead.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

---
title: ASR subtitle transcriptions endpoint (faster-whisper)
date: 2026-08-29
summary: "Added OpenAI-compatible POST /v1/audio/transcriptions with SRT/VTT/verbose_json + word timing; 36 tests green, no TTS regression."
---

# ASR subtitle transcriptions endpoint (faster-whisper)

## What happened

Implemented plan `260829-0859-asr-subtitle-transcriptions` end-to-end (`/ak:cook --auto`), adding a speech-to-text dimension to a gateway that previously only did TTS.

- **New module `app/asr/`** (kept separate from `app/backends/` TTS, one engine, no registry — KISS):
  - `transcriber.py`: lazy process-wide `WhisperModel` singleton (double-checked `threading.Lock`), `transcribe()` returns dataclasses; `AsrUnavailableError` (missing extra) + `InvalidAudioError` (undecodable) typed exceptions.
  - `subtitles.py`: pure formatters `to_srt` / `to_vtt` / `to_verbose_json` / `to_json` / `format_timestamp` (no faster-whisper import → fast deterministic unit tests).
- **`POST /v1/audio/transcriptions`** (`app/routers/transcriptions.py`): multipart, OpenAI schema, off-event-loop via `anyio.to_thread` under the shared `synth_semaphore`; 5 response formats; `timestamp_granularities[]=word` (both bracketed + bare keys). Mirrors `speech.py`/`voices_admin.py` conventions.
- **Config/deps:** optional extra `asr = ["faster-whisper>=1.1"]`; `ASR_MODEL` (default `small`) + `ASR_COMPUTE_TYPE` settings; `synth_semaphore` now shared by TTS+ASR (one `MAX_CONCURRENCY` budget).
- **Dep resolve:** `av` 13→18.0.0, numpy 2.2.6 (<2.3), faster-whisper 1.2.1, ctranslate2 4.8.1 — **no TTS encoder regression** (25 TTS tests stayed green post-upgrade, the plan's top risk).
- Docs: README (feature/endpoint/STT section/config), `docs/kien-truc-va-mo-rong.md` (§11 ASR module).

## Decision

- **Shared CPU budget:** ASR reuses `synth_semaphore` rather than a separate semaphore — TTS+ASR draw from one `MAX_CONCURRENCY`; scale by raising it. (Plan decision, personal single-user box.)
- **Lazy faster-whisper import** is the backbone of the "missing extra → clean 503, no crash" contract: `app.asr` import chain pulls only stdlib + config; `faster_whisper` imported only inside `is_available()`/`_get_model()`.
- **Code review (code-reviewer subagent) → 4 fixes applied:** (1) undecodable audio now returns 400 `invalid_audio_file` instead of a 500 (catch `av.error.FFmpegError`/`ValueError` → `InvalidAudioError`), verified live; (2) added OpenAI `tokens` segment field (plan's field list was an approximation, outcome was "exact OpenAI schema"); (3) double-checked lock around model load (avoids concurrent cold-start 2x-RAM); (4) normalize `language or None`.

## Next steps

- Optional future: word-level accuracy via forced alignment (WhisperX) — out of scope, DTW timing is sufficient for subtitles/karaoke.
- Not yet committed — awaiting user go-ahead.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

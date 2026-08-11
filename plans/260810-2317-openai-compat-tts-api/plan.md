# Plan: OpenAI-compatible multi-backend TTS API

Status: Phase 1 + voice cloning DONE — verified live (14/14 e2e tests pass, real
VieNeu synthesis + real clone sample).

## Outcome
Runnable HTTP service exposing 3 OpenAI-compatible endpoints for TTS, API-key
auth, pluggable voice backends. First backend: VieNeu-TTS (Vietnamese, CPU/ONNX).

## Design (locked with user)
- Stack: Python 3.11+ / FastAPI / Uvicorn / Pydantic v2. VieNeu is Python → no
  cross-language bridge. Deps via `uv` + `pyproject.toml` + `uv.lock` + `.venv`.
- Audio encoding: PyAV (bundled FFmpeg, no system dep) for mp3/opus/aac/flac;
  stdlib `wave`/raw for wav/pcm.
- Backend = adapter implementing `VoiceBackend` (name, list_voices, synthesize),
  registered in `main._register_backends()`; routers talk only to `registry`.
- CPU-first: `DEVICE=cpu` → VieNeu ONNX (torch-free). `cuda`/`auto` → PyTorch
  engine via `[gpu]` extra.
- OpenAI aliasing ON: unknown model → default backend (vieneu); unknown voice →
  backend's first preset. So the `openai` SDK works unmodified.
- No mock backend (user decision): VieNeu is the only backend; startup fails
  fast if `vieneu` is not importable.
- Concurrency: blocking synth+encode run in a threadpool, bounded by a
  semaphore (`MAX_CONCURRENCY`); VieNeu calls serialised by a per-backend lock.

## Endpoints
- `POST /v1/audio/speech` — {model,input(≤4096),voice,response_format?,speed?} →
  raw audio bytes + correct Content-Type. Errors 401/400/404/500 in
  `{"error":{message,type,code}}`.
- `GET /v1/models` — OpenAI model-list shape.
- `GET /v1/voices` — voices merged across backends (custom, non-OpenAI).

## Files
- `app/{config,schemas,auth,limits,main}.py`
- `app/audio/encoder.py`
- `app/backends/{base,registry,vieneu_backend}.py`
- `app/routers/{speech,voices,models}.py`
- `tests/test_e2e.py` (single end-to-end suite — user decision: no scattered unit tests)
- `pyproject.toml`, `.env.example`, `README.md`

## Acceptance criteria
- `uv sync` installs cleanly; app boots.
- `openai` SDK `audio.speech.create` works unmodified against `/v1`.
- All 6 `response_format`s return non-empty bytes with correct Content-Type.
- Missing/invalid key → 401; input>4096 → 400; unknown model/voice → aliased 200.
- `pytest -q` green (real VieNeu synthesis).

## Voice cloning (added — OpenAI custom-voice API)
- `POST /v1/audio/voices` (multipart: name, audio_sample, consent?), `GET`,
  `GET/{id}`, `DELETE/{id}`, `POST /v1/audio/voice_consents`.
- Backed by VieNeu `add_voice(name, ref_audio)`; **requires PyTorch** (ONNX
  cannot clone — verified). Dual-engine on CPU: ONNX presets (fast) + PyTorch
  clones. Persisted to `data/voices/` (samples + registry.json); re-enrolled at
  startup so clones survive restarts.
- `voice` accepts string OR OpenAI object `{"id": "..."}`.
- Deviations: `consent` optional; consent recordings not persisted.

## Tuning knobs (added — VieNeu as reference standard)
- Optional fields on /v1/audio/speech (via extra_body), forwarded to backend
  `synthesize(..., options)`: style/temperature/top_k/top_p/repetition_penalty/
  silence_p (pause scale)/crossfade_p/max_chars. Validated ranges in schema.
- Pauses also follow punctuation; emotion cues `[cười]` + VI⇄EN code-switch via
  `input`. Other backends map option names to their params or ignore them.
- Docs: docs/kien-truc-va-mo-rong.md (VN, diagrams), docs/architecture.md (EN).
- Model cache: ~/.cache/huggingface/hub (~313MB); override via HF_HOME.

## Phases
- P1 + cloning + tuning knobs + docs: DONE (15/15 e2e green). ← current
- P2: streaming (`stream_format` sse/audio, chunked via `infer_stream`),
  explicit OpenAI-voice→preset map, per-request `style`.
- P3: metrics, rate-limit, Dockerfile, second real backend.

## Verified facts (measured)
- VieNeu `infer()` has NO `speed` param → gateway applies `speed` via
  pitch-preserving time-stretch (librosa) in `app/audio/effects.py`, backend-
  agnostic. Works for all backends.
- Cloning needs torch: `add_voice` on ONNX raises "No module named 'torch'".
- CPU timings: torch engine load ~23s; `add_voice` enrolment ~46s (one-time);
  cloned-voice `infer` ~1.1s for 1.8s audio (faster than real-time).
- Encoder: all 6 formats emit valid containers (RIFF/ID3/fLaC/OggS/ADTS/raw).

## Open questions
- Enrolment (~46s CPU) is slow; consider async enrolment/job status if UX needs.
- Malformed-JSON body returns Starlette's `{"detail":...}` (not our error
  envelope) — pre-handler edge; wrap in P2 if strict parity required.

# API Reference

This document provides details on how to call the API and use the extended features of `all-voice`.

Interactive API documentation (auto-generated): **`http://localhost:8123/docs`** (Swagger) · `/redoc` · `/openapi.json`.

## 🔌 Main API Endpoints
All `/v1/*` routes require the `Authorization: Bearer <key>` header.

| Method | Path | Description |
|--------|------|-------|
| `POST` | `/v1/audio/speech` | Synthesize speech (OpenAI schema) |
| `POST` | `/v1/audio/transcriptions` | Speech recognition → transcript + subtitles (requires `asr` extra) |
| `GET`  | `/v1/models` | List all registered backends |
| `GET`  | `/v1/voices` | List preset voices + cloned voices (all backends) |
| `GET`  | `/v1/voices/{model}/{voice_id}/preview` | Preview voice (mp3) — public |
| `POST` | `/v1/audio/voices` | Create a cloned voice (multipart) |
| `GET` · `DELETE` | `/v1/audio/voices/{id}` | Get / delete a cloned voice |
| `GET`  | `/health` | Liveness check (no auth required) |

## Using with the OpenAI SDK
The protocol is 100% compatible with the official OpenAI SDK.

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8123/v1", api_key="dev-key")

# Text-to-Speech
client.audio.speech.create(
    model="vieneu", voice="Trúc Ly",
    input="Hello, this is all-voice.", response_format="mp3",
).stream_to_file("out.mp3")

# Speech-to-Text
srt = client.audio.transcriptions.create(
    model="whisper-1", file=open("lecture.mp3", "rb"), response_format="srt",
)
```

## 🎙️ Voice Cloning
Enrolling (`add_voice`) takes a few dozen seconds, so it is a **one-time step**. The system will return a `voice_id` for reuse.

```python
# 1) Enroll once
voice = client.audio.voices.create(name="My Voice", audio_sample=open("ref.wav", "rb"))

# 2) Reuse with speech.create
client.audio.speech.create(model="vieneu", voice=voice.id, input="Hello!").stream_to_file("out.mp3")
```

**Sample requirements**: 3–8s, **one speaker**, clean background, clear speech with intonation. If the sample is studio-recorded and very clean, you should disable denoise (`denoise=false`) to preserve the original vocal timbre.

## 🎛️ Voice Tuning Knobs (Style)
Use `extra_body` to adjust the reading style (only applies to supported engines like VieNeu).
```python
client.audio.speech.create(
    model="vieneu", voice="Trúc Ly", input="Once upon a time...",
    extra_body={"style": "doc_truyen"}, # tu_nhien (natural), tin_tuc (news), doc_truyen (storytelling)
)
```

## ⚙️ Environment Configuration (.env)
- `API_KEYS`: List of API keys (comma-separated).
- `DEVICE`: `cpu`, `cuda`, or `auto`.
- `MAX_CONCURRENCY`: Number of concurrent workers.
- `ASR_MODEL`: STT Model (e.g., `tiny`, `small`, `large-v3`).
- Engine configurations: `ENABLE_KOKORO`, `ENABLE_VOICEVOX`.

## 🩺 Log & Debug
System logs rotate at `logs/app.log`. 
- 500 error tracebacks are logged in detail to this file.
- The latency of each API request is recorded (e.g., `-> 200 (150ms)`).

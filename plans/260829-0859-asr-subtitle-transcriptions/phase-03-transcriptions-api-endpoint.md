---
title: "Phase 3: Transcriptions API Endpoint"
status: done
---

# Phase 3: Transcriptions API Endpoint

## Overview

Phơi engine ra HTTP: `POST /v1/audio/transcriptions` (multipart), theo schema OpenAI,
trả đúng `response_format` yêu cầu. Router mỏng, tái dùng auth + semaphore + envelope lỗi
sẵn có. Không đụng router/lõi TTS.

## Requirements

- [ ] Nhận multipart `file` + form fields kiểu OpenAI; auth Bearer bắt buộc
- [ ] `response_format` chọn được: json | text | srt | vtt | verbose_json (mặc định `json`)
- [ ] `timestamp_granularities[]` chấp nhận `segment`/`word` (word ⇒ bật word_timestamps)
- [ ] Transcribe chạy off event-loop, bọc `synth_semaphore` (chung TTS); lỗi trả envelope OpenAI
- [ ] Thiếu extra `asr` → 503 rõ ràng, app không crash

## Architecture

### `app/schemas.py` (thêm)
- `TranscriptionResponseFormat = Literal["json","text","srt","vtt","verbose_json"]`
- `TranscriptionSegment(BaseModel)`: id, seek, start, end, text, temperature, avg_logprob,
  compression_ratio, no_speech_prob.
- `TranscriptionWord(BaseModel)`: word, start, end.
- `TranscriptionVerbose(BaseModel)`: task="transcribe", language, duration, text,
  segments: list[TranscriptionSegment], words: list[TranscriptionWord] | None = None.
- `Transcription(BaseModel)`: text  (cho `response_format=json`).
  (Các model này chỉ để tài liệu OpenAPI đẹp; router có thể trả dict/Response trực tiếp.)

### `app/routers/transcriptions.py` (mới, tham chiếu `voices_admin.py` cho multipart & `speech.py` cho off-thread)
- `POST /audio/transcriptions`, tag `transcriptions`, `_key = Depends(require_api_key)`.
- Form/File fields (mirror OpenAI):
  - `file: UploadFile = File(...)`
  - `model: str = Form("whisper-1")` — chấp nhận mọi tên, dùng engine cấu hình (một engine). Log lại.
  - `language: str | None = Form(None)`
  - `response_format: TranscriptionResponseFormat = Form("json")`
  - `timestamp_granularities[]: list[str] = Form(default_factory=list, alias="timestamp_granularities[]")`
    (OpenAI gửi key có `[]`; nhận cả `timestamp_granularities` không ngoặc cho chắc).
  - `prompt: str | None = Form(None)`, `temperature: float = Form(0.0)` — forward vào transcribe.
    **Lưu ý:** kwarg faster-whisper là `initial_prompt` (không phải `prompt`); transcriber map `prompt`→`initial_prompt`.
- Kiểm tra: file rỗng → 400; `len > MAX_AUDIO_BYTES (25 MiB)` → 400 (hằng số module như `voices_admin`).
- `want_words = "word" in granularities`.
- <!-- Updated: Validation Session 1 — dùng chung synth_semaphore, không tạo asr_semaphore -->
  `from ..limits import synth_semaphore`;
  `async with synth_semaphore: result = await anyio.to_thread.run_sync(partial(transcribe, data, language=..., want_words=want_words, prompt=..., temperature=...))`
  (ngân sách CPU dùng chung với TTS, bounded `MAX_CONCURRENCY`).
- Bắt `AsrUnavailableError` → 503 `{message:"ASR engine not installed. Run `uv sync --extra asr`.", code:"asr_unavailable"}`.
- Trả theo format:
  - `json` → `JSONResponse(to_json(result))`
  - `text` → `Response(result.text, media_type="text/plain; charset=utf-8")`
  - `srt` → `Response(to_srt(result.segments), media_type="text/plain; charset=utf-8")`
  - `vtt` → `Response(to_vtt(result.segments), media_type="text/plain; charset=utf-8")`
  - `verbose_json` → `JSONResponse(to_verbose_json(result))`
- Log 1 dòng: `all_voice.transcribe` — model / bytes / định dạng / language / #segments / thời lượng / ms
  (thêm logger `transcribe` giống `speech`).

### `app/main.py` (sửa)
- `from .routers import ... transcriptions`; `app.include_router(transcriptions.router, prefix="/v1")`.
- Thêm `{"name":"transcriptions","description":"Speech-to-text with subtitle timing."}` vào TAGS_METADATA.
- Startup log: thêm `asr_model=… asr_available=…` (dùng `asr.is_available()`), không chặn khởi động nếu thiếu.

## Related Code Files

- Create: `app/routers/transcriptions.py`
- Modify: `app/schemas.py`, `app/main.py`

## Implementation Steps

1. Thêm schemas transcription.
2. Viết router `transcriptions.py` (multipart, semaphore, off-thread, 5 nhánh format, 503).
3. Mount router + tag + startup log trong `main.py`.
4. Thử qua Swagger `/docs` + curl với `tests/clone_1.wav` cho từng `response_format`.

## Todo

- [ ] schemas.py: TranscriptionResponseFormat / Segment / Word / Verbose / Transcription
- [ ] transcriptions.py: endpoint đầy đủ (fields, giới hạn 25MiB, semaphore, 5 format, 503, log)
- [ ] main.py: mount router + tag + startup log ASR
- [ ] Thử curl/Swagger mọi format

## Success Criteria

- [ ] 401 nếu thiếu Bearer; 400 nếu file rỗng/quá lớn
- [ ] Mỗi `response_format` trả đúng nội dung + content-type
- [ ] `timestamp_granularities[]=word` → verbose_json có `words`
- [ ] SDK OpenAI: `client.audio.transcriptions.create(file=..., model="whisper-1", response_format="srt")` chạy
- [ ] Thiếu extra asr → 503 rõ ràng; các route TTS vẫn hoạt động

## Risk Assessment

Parse `timestamp_granularities[]` (key có ngoặc) qua FastAPI Form/alias có thể trượt.
*Signal:* word không bật dù client gửi. *Response:* nhận cả 2 tên key; test e2e phần word
xác nhận. Job ASR dài giữ `synth_semaphore` (chung với TTS) → có thể chặn synth khi transcribe
audio dài; chấp nhận (cá nhân dùng), tăng `MAX_CONCURRENCY` khi cần.

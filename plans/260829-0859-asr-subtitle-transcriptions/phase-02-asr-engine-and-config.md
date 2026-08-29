---
title: "Phase 2: ASR Engine + Subtitle Formatters"
status: done
---

# Phase 2: ASR Engine + Subtitle Formatters

## Overview

Module `app/asr/` mới: wrapper faster-whisper (nạp lazy, config-driven) và bộ formatter
thuần đổi kết quả → SRT/VTT/verbose_json. Chưa gắn HTTP (Phase 3).

## Requirements

- [ ] Model nạp **lazy** ở lần transcribe đầu (giống VieNeu), cache singleton toàn process
- [ ] Thiếu `faster_whisper` → báo lỗi rõ ràng để router trả 503 + gợi ý cài extra
- [ ] Formatter là **hàm thuần** (không cần model) → test nhanh, tất định
- [ ] Hỗ trợ word-level khi được yêu cầu (`word_timestamps=True`)

## Architecture

### `app/asr/transcriber.py`
- Hàm `transcribe(audio_bytes: bytes, *, language: str | None, want_words: bool, ...) -> TranscriptionResult`.
- `TranscriptionResult` (dataclass): `text: str`, `language: str`, `duration: float`,
  `segments: list[Segment]`, `words: list[Word] | None`.
  - `Segment`: `id, seek, start, end, text, temperature, avg_logprob, compression_ratio, no_speech_prob`
    (map thẳng từ `faster_whisper` Segment; đủ field cho `verbose_json` kiểu OpenAI).
  - `Word`: `word, start, end, probability`.
- Nạp model: `WhisperModel(settings.asr_model, device=_resolve_device(settings.device), compute_type=settings.asr_compute_type)`
  trong singleton lazy (`_model`, `functools.lru_cache` hoặc module global + guard).
  - `_resolve_device("auto")` → "cuda" nếu có, else "cpu" (tránh phụ thuộc engine ngoài; kiểm bằng try import torch hoặc ctranslate2 device — đơn giản: "auto"→"cpu" trừ khi user set "cuda").
- Decode: truyền `io.BytesIO(audio_bytes)` thẳng vào `model.transcribe(...)` — faster-whisper
  tự decode qua `av` và resample 16kHz mono (không cần dùng `app/audio/encoder.py`).
- `model.transcribe(...)` trả generator lazy → **phải consume hết trong thread** (`list(segments)`)
  để đo thời gian và tránh sinh I/O ngoài event loop. `info.duration`, `info.language` lấy từ trả về.
- `is_available() -> bool`: thử `import faster_whisper` → dùng cho startup log / health.
- Nếu import lỗi: `transcribe()` raise `AsrUnavailableError` (exception nội bộ) — router bắt → 503.

### `app/asr/subtitles.py` (thuần, không import faster_whisper)
- `format_timestamp(seconds: float, *, sep: str) -> str` → `HH:MM:SS{sep}mmm` (sep `,` cho SRT, `.` cho VTT).
- `to_srt(segments) -> str` — đánh số 1..N, mỗi block: index / `start --> end` / text.
- `to_vtt(segments) -> str` — header `WEBVTT\n\n` rồi các cue `start --> end` (dấu chấm).
- `to_verbose_json(result) -> dict` — hình dạng OpenAI: `{task:"transcribe", language, duration, text, segments:[...], words?:[...]}`
  (`words` chỉ có khi result.words không None). Dùng cho `response_format=verbose_json`.
- `to_json(result) -> dict` — `{"text": result.text}` (OpenAI `json` mặc định).

### `app/asr/__init__.py`
- Export `transcribe`, `is_available`, `TranscriptionResult`, `AsrUnavailableError`, và các formatter.

## Related Code Files

- Create: `app/asr/__init__.py`, `app/asr/transcriber.py`, `app/asr/subtitles.py`

## Implementation Steps

1. Viết `subtitles.py` trước (thuần, dễ test) — timestamp + SRT + VTT + verbose_json/json.
2. Viết `transcriber.py`: dataclasses, lazy model loader, `transcribe()`, `is_available()`, `AsrUnavailableError`.
3. Export gọn trong `__init__.py`.
4. Smoke thử cục bộ: `ASR_MODEL=tiny` transcribe `tests/clone_1.wav`, in segments + srt.

## Todo

- [ ] `subtitles.py`: format_timestamp / to_srt / to_vtt / to_verbose_json / to_json
- [ ] `transcriber.py`: dataclasses + lazy loader + transcribe() + is_available() + AsrUnavailableError
- [ ] `__init__.py` export
- [ ] Smoke test cục bộ với model `tiny`

## Success Criteria

- [ ] `transcribe(bytes, want_words=False)` trả segments có `start<end`, text non-empty với audio VN
- [ ] `want_words=True` → `result.words` có mốc từng từ
- [ ] `to_srt`/`to_vtt` khớp định dạng chuẩn (`-->`, `WEBVTT`, đúng dấu phân tách mili-giây)
- [ ] Thiếu faster_whisper → `is_available()` False, `transcribe()` raise `AsrUnavailableError`

## Risk Assessment

Độ chính xác timing word dựa DTW của faster-whisper (đủ cho phụ đề/karaoke, không khít bằng
forced-alignment). *Signal:* user thấy lệch. *Response:* đã ghi trong brainstorm là nâng cấp
tương lai (WhisperX) — ngoài scope plan này.

---
title: "Phase 1: Dependency & Config Foundation"
status: done
---

# Phase 1: Dependency & Config Foundation

## Overview

Nền tảng, chưa có hành vi mới: thêm optional extra `asr` (faster-whisper), các setting
ASR trong config, và semaphore riêng cho ASR. Tách khỏi lõi TTS hoàn toàn.

## Requirements

- [ ] Base install (không `--extra asr`) không nặng thêm; faster-whisper chỉ vào khi bật extra
- [ ] `numpy` vẫn `<2.3` sau khi resolve (đã kiểm: →2.2.6); `av` nâng 13→18 chấp nhận được
- [ ] Setting ASR có mặc định an toàn cho CPU 11GB; `ASR_MODEL` đổi được qua `.env`

## Architecture

- `pyproject.toml`: thêm
  ```toml
  [project.optional-dependencies]
  asr = ["faster-whisper>=1.1"]
  ```
  (song song với extra `clone` sẵn có). Sau đó `uv lock` để cập nhật `uv.lock`
  (sẽ nâng `av`→18.x, kéo `ctranslate2`, `onnxruntime`, `tokenizers`).
<!-- Updated: Validation Session 1 — dùng chung synth_semaphore, bỏ asr_max_concurrency/asr_semaphore -->
- `app/config.py` — thêm vào `Settings`:
  - `asr_model: str = "small"` — tên/đường dẫn model faster-whisper (tiny/base/small/medium/large-v3, hoặc repo CT2 như PhoWhisper-ct2).
  - `asr_compute_type: str = "int8"` — kiểu tính; int8 tối ưu CPU. (cuda dùng float16.)
  - Dùng lại `device` **và `max_concurrency`** sẵn có cho ASR — KHÔNG thêm setting concurrency riêng.
- `app/limits.py` — **KHÔNG thêm semaphore mới.** ASR tái dùng `synth_semaphore` (guard job
  CPU-bound dùng chung synth + transcribe, bounded bởi `MAX_CONCURRENCY`). Chỉ sửa docstring
  cho đúng ý nghĩa mới. (Quyết định validation: ngân sách CPU dùng chung, tăng qua `MAX_CONCURRENCY`.)

## Related Code Files

- Modify: `pyproject.toml`, `app/config.py`, `app/limits.py`
- Modify: `.env.example` (thêm ví dụ `ASR_MODEL`, `ASR_COMPUTE_TYPE`; concurrency dùng chung `MAX_CONCURRENCY` sẵn có)

## Implementation Steps

1. Thêm extra `asr` vào `pyproject.toml`; chạy `uv lock` rồi `uv sync --extra clone --extra asr`.
2. Thêm 2 setting ASR (`asr_model`, `asr_compute_type`) vào `Settings` (comment như style hiện có).
3. Cập nhật docstring `synth_semaphore` trong `limits.py` (dùng chung synth + ASR); KHÔNG thêm semaphore mới.
4. Ghi chú `ASR_MODEL`/`ASR_COMPUTE_TYPE` vào `.env.example` và mục "Cấu hình" README (README làm ở Phase 4).

## Todo

- [ ] pyproject: extra `asr`, `uv lock` + `uv sync --extra asr`
- [ ] config.py: `asr_model` / `asr_compute_type`
- [ ] limits.py: cập nhật docstring `synth_semaphore` (dùng chung synth + ASR)
- [ ] .env.example: `ASR_MODEL` / `ASR_COMPUTE_TYPE`

## Success Criteria

- [ ] `uv sync --extra asr` thành công, `python -c "import faster_whisper"` chạy
- [ ] `uv sync` (không extra) vẫn không kéo faster-whisper
- [ ] `import app.config; app.limits` không lỗi; setting đọc từ `.env` đúng

## Risk Assessment

`uv lock` nâng `av`→18 → rủi ro encoder TTS. *Signal:* Phase 4 e2e `test_speech_formats` fail.
*Response:* chạy `uv run pytest -q` ngay sau sync ở cuối phase này để bắt sớm; nếu gãy,
xem xét pin `av` ở khoảng chung hoặc điều chỉnh call trong `encoder.py`.

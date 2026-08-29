---
title: "Phase 4: Tests & Docs"
status: done
---

# Phase 4: Tests & Docs

## Overview

Kiểm thử end-to-end + unit cho formatter, và cập nhật tài liệu người dùng (README +
docs kiến trúc). Xác nhận lõi TTS không hồi quy sau khi nâng `av`.

## Requirements

- [ ] Unit test formatter (thuần, không tải model) — nhanh, tất định
- [ ] E2E test endpoint dùng model nhỏ (`ASR_MODEL=tiny`) trên `tests/clone_1.wav`
- [ ] Toàn bộ test hiện có (25) vẫn xanh (hồi quy `av` 13→18)
- [ ] README + docs phản ánh endpoint mới + cấu hình ASR

## Architecture

### `tests/test_transcriptions.py` (mới)
- **Unit (không model):**
  - `to_srt`/`to_vtt`/`format_timestamp` với segments dựng tay → khẳng định định dạng
    (`1\n00:00:00,000 --> 00:00:01,500\n...`, `WEBVTT`, dấu `.` vs `,`).
  - `to_verbose_json` có/không `words`.
- **E2E (tải model tiny 1 lần):** đặt `os.environ["ASR_MODEL"]="tiny"` trước import app
  (giống cách `API_KEYS` set trong `test_e2e.py`); `TestClient(app)`.
  - auth: thiếu Bearer → 401.
  - `response_format=verbose_json` với `tests/clone_1.wav` → 200, `text` non-empty,
    `segments` có phần tử với `start<end`, `duration>0`.
  - `response_format=srt` → chứa `-->`; `vtt` → `startswith("WEBVTT")`.
  - `timestamp_granularities[]=word` + verbose_json → có `words`, mỗi từ `start<=end`.
  - file rỗng → 400.
- Cân nhắc `@pytest.mark.slow` hoặc guard tải model để CI chọn chạy; giữ nhất quán với
  phong cách test hiện tại (test_e2e đã tải model VieNeu thật).

### Docs
- `README.md`:
  - Bảng "Tính năng": thêm dòng Speech-to-Text/phụ đề.
  - Bảng Endpoints: thêm `POST /v1/audio/transcriptions`.
  - Mục mới "🎬 Tạo phụ đề (Speech-to-Text)": ví dụ SDK OpenAI trả `srt`/`vtt`/`verbose_json`,
    ghi rõ **không dịch**, word-level cho karaoke, cài `uv sync --extra asr`.
  - Mục "Cấu hình": thêm `ASR_MODEL` (mặc định `small`), `ASR_COMPUTE_TYPE`; ghi rõ ASR dùng chung `MAX_CONCURRENCY` với TTS.
  - Yêu cầu: lưu ý model whisper tải ở request transcribe đầu (small ~0.5GB).
- `docs/kien-truc-va-mo-rong.md`: thêm sơ đồ/nói về module `app/asr/` (tách khỏi TTS backend),
  seam `get_transcriber()`, vì sao không dùng registry.

## Related Code Files

- Create: `tests/test_transcriptions.py`
- Modify: `README.md`, `docs/kien-truc-va-mo-rong.md`

## Implementation Steps

1. Viết unit test formatter (chạy `uv run pytest tests/test_transcriptions.py -k srt -q` trước — nhanh).
2. Viết e2e test (ASR_MODEL=tiny); chạy riêng file này.
3. Chạy full `uv run pytest -q` → xác nhận 25 test hiện có + test mới xanh (bắt hồi quy `av`).
4. Cập nhật README + docs kiến trúc.

## Todo

- [ ] Unit test formatter (srt/vtt/verbose_json/timestamp)
- [ ] E2E test endpoint (tiny) mọi response_format + word + auth + file rỗng
- [ ] `uv run pytest -q` toàn bộ xanh
- [ ] README: feature + endpoint + mục phụ đề + cấu hình ASR
- [ ] docs/kien-truc: module asr

## Success Criteria

- [ ] `uv run pytest -q` xanh toàn bộ (cũ + mới)
- [ ] README mô tả đúng endpoint, cách trả SRT/VTT, word-level, và cài extra `asr`
- [ ] docs kiến trúc phản ánh module `app/asr/`

## Risk Assessment

E2E tải model → chậm/cần mạng. *Signal:* CI timeout/offline fail. *Response:* dùng `tiny`,
tách file test, cân nhắc marker slow để chạy chọn lọc — đồng nhất với test VieNeu hiện có.

---
phase: 3
title: "Phase 3: Tests, Verification & Docs"
status: complete
priority: P1
effort: "1h"
dependencies: [1, 2]
---

# Phase 3: Tests, Verification & Docs

## Overview

Viết unit test đầy đủ cho `CapCutBackend` (catalog 24 giọng `vi-VN`, `resolve_voice`, ký request MD5/RSA, mock luồng create/query/download + giải mã MP3 bằng PyAV), cập nhật test Frontend, và bổ sung tài liệu vào `docs/kien-truc-va-mo-rong.md`.

## Requirements

- [x] Tạo `tests/test_capcut.py` kiểm thử:
  - `is_available` trả về `False` khi thiếu file catalog và `True` khi có `app/data/capcut_voices.json`.
  - `list_voices()` trả về đúng 24 giọng `vi` (`model="capcut"`).
  - `resolve_voice()` hoạt động đúng ở cả chế độ `strict=True` (trả `None` khi giọng lạ) và `strict=False` (fallback về `BV421_vivn_streaming`).
  - Hàm ký `make_sign_header` và `make_tts_payload_sign` tạo chữ ký hợp lệ.
  - Luồng `synthesize()` với mock HTTP session (create task → query task → download MP3 mẫu sinh bằng `encode(..., "mp3")`) trả về `AudioResult` PCM float32 hợp lệ.
  - Endpoint `/v1/voices?model=capcut` và `/v1/audio/speech` với `model="capcut"` hoạt động đúng.
- [x] Cập nhật/chạy test Frontend (`vitest`) và build production (`vite build`).
- [x] Cập nhật `docs/kien-truc-va-mo-rong.md` và `.env.example` (nếu có) ghi chú về backend `capcut`.

## Related Code Files

- Create: `tests/test_capcut.py`
- Modify: `frontend/src/api/http-tts-api.test.ts`
- Modify: `docs/kien-truc-va-mo-rong.md`

## Implementation Steps

1. **Viết `tests/test_capcut.py`**:
   - Viết các unit test chạy nhanh dưới `-m "not synth"` (dùng mock HTTP response + MP3 bytes thật tạo từ `app.audio.encoder.encode` để test trọn vẹn cả bước decode PyAV).
   - Thêm 1 test `@pytest.mark.synth` gọi thật CapCut API (skip gọn nếu mạng/dịch vụ ngoài không truy cập được).
2. **Cập nhật `frontend/src/api/http-tts-api.test.ts`**:
   - Thêm test case kiểm tra mapping giọng `model: 'capcut'` từ `/v1/voices`.
3. **Cập nhật `docs/kien-truc-va-mo-rong.md`**:
   - Bổ sung mô tả `CapCutBackend` (24 giọng Tiếng Việt, biến môi trường `ENABLE_CAPCUT`, `CAPCUT_*`).
4. **Chạy toàn bộ bộ kiểm thử**:
   - Backend: `.\.venv\Scripts\pytest.exe -m "not synth" -q`
   - Frontend: `pnpm --dir frontend test --run` và `pnpm --dir frontend build`

## Todo

- [x] Tạo `tests/test_capcut.py`
- [x] Bổ sung test case `capcut` trong `frontend/src/api/http-tts-api.test.ts`
- [x] Cập nhật `docs/kien-truc-va-mo-rong.md`
- [x] Chạy pass toàn bộ pytest + vitest + frontend build

## Success Criteria

- [x] `pytest -m "not synth"` xanh 100%.
- [x] `pnpm --dir frontend test --run` và `pnpm --dir frontend build` xanh 100%.
- [x] Không có bất kỳ import nào trỏ vào `phan_tich/capcut-tts-api`.

## Risk Assessment

- **Phụ thuộc mạng trong CI/Unit Test**: Toàn bộ test mặc định (`not synth`) dùng mock HTTP session kết hợp encoder MP3 nội bộ nên tất định 100% và không phụ thuộc kết nối tới `capcutapi.com`.

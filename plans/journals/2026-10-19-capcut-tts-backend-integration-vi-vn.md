---
title: CapCut TTS Backend Integration (vi-VN)
date: 2026-10-19
summary: "Port idiomatic CapCut TTS with 24 vi-VN voices, PyAV in-memory decode, frontend engine support, and 100% test coverage."
---

# CapCut TTS Backend Integration (vi-VN)

Port idiomatic CapCut TTS with 24 vi-VN voices, PyAV in-memory decode, frontend engine support, and 100% test coverage.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

## Context & Motivation

Dự án `all-voice` hỗ trợ kiến trúc multi-backend text-to-speech tương thích OpenAI API. Mục tiêu là tích hợp 24 giọng đọc Tiếng Việt (`vi-VN`) chất lượng cao từ CapCut Desktop API vào hệ thống dưới dạng backend plugin `model="capcut"`, hoạt động độc lập không phụ thuộc thư mục bên ngoài `phan_tich/capcut-tts-api`.

## Key Implementations

1. **Voice Catalog (`app/data/capcut_voices.json`)**:
   - Trích xuất 24 giọng `vi-VN` sạch (loại trừ `digital_human_voice`) với đầy đủ `voice_type`, `display_name`, `resource_id`, `lang`, `lan`.
2. **Backend Adapter (`app/backends/capcut_backend.py`)**:
   - Hiện thực `CapCutBackend` kế thừa `VoiceBackend`.
   - Thuần Python crypto & signing: MD5 `x-ss-stub`, MD5 `sign` header, và RSA PKCS#1 v1.5 payload signature.
   - Luồng task `/lv/v1/common_task/new` và polling `/lv/v1/common_task/query`.
   - Giải mã MP3 trực tiếp in-memory qua `PyAV` (`io.BytesIO` + `av.open`) sang float32 mono PCM `[-1.0, 1.0]`, không tạo file tạm trên ổ đĩa.
3. **Application Configuration & Registry**:
   - `app/config.py`: bổ sung cấu hình `ENABLE_CAPCUT`, `CAPCUT_*`.
   - `app/main.py`: đăng ký `CapCutBackend` có guard `is_available(settings)` và cập nhật `API_DESCRIPTION`.
4. **Frontend Integration**:
   - `frontend/src/api/types.ts`: bổ sung `'capcut'` vào union type `Voice['engine']`.
   - `frontend/src/api/http-tts-api.ts`: hỗ trợ `'capcut'`, chuẩn hóa tên hiển thị (`.trim()`) và nhận diện giới tính giọng đọc (`female`/`male`/`neutral`, bao gồm họ `BV075_*`).
   - `frontend/src/features/compose/model-select.tsx` & `synth-controls.tsx`: gắn `<ModelSelect />` vào vùng điều khiển Compose với mô tả đa ngôn ngữ (`vi.json` / `en.json`).
   - `frontend/src/features/voice/use-voice-filters.ts`: cho phép tìm kiếm theo tên engine (`capcut`).
   - Hỗ trợ subtitle ASR round-trip tự động.
5. **Code Review Fixes (`ak:code-review`)**:
   - Sử dụng `av.AudioResampler(format="fltp", layout="mono", rate=target_rate)` trong `_decode_mp3_bytes` để giải mã an toàn cả MP3 stereo/mono, `fltp`/`s16p`/`s16`, và tự động chuẩn hóa tần số lấy mẫu (ví dụ `44100 Hz` → `24000 Hz`) để tương thích 100% với bộ mã hóa `libopus`.
   - Đảm bảo an toàn đa luồng (`threading.local()`) cho `requests.Session` và `threading.Lock()` khi nạp catalog.
   - Ràng buộc tổng thời gian thực thi bằng `time.monotonic()` deadline trong `CapCutBackend.synthesize()`.
   - Loại bỏ khoảng trắng thừa ở `"Giọng Nam Trầm"` trong `app/data/capcut_voices.json`.
6. **Testing & Verification**:
   - `tests/test_capcut.py`: 12 unit & mock integration tests (100% pass, tổng cộng 50 backend unit tests pass).
   - `frontend/`: 7 test files / 26 vitest tests pass; `pnpm --dir frontend build` (`tsc -b && vite build`) pass.
   - Cập nhật tài liệu `docs/kien-truc-va-mo-rong.md` và `.env.example`.

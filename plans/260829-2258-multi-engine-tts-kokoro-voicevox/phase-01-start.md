---
title: "Phase 1: Foundation — Deps, Config, Assets, Registration"
status: done
phase: 1
priority: P1
effort: "0.5d"
dependencies: []
---

# Phase 1: Foundation — Deps, Config, Assets, Registration

## Overview

Dựng nền tảng dùng chung cho 2 engine mới **trước khi** viết adapter: optional extras trong `pyproject.toml`, các setting feature-flag + đường dẫn model trong `config.py`, script tải asset (torch-free), và chỗ đăng ký backend trong `main.py` có guard `is_available()` + flag để app vẫn chạy khi extra chưa cài.

## Requirements

- **Functional**
  - Thêm extras `en` (Kokoro) và `ja` (VOICEVOX) độc lập, cài riêng lẻ không kéo theo nhau, không đụng base/`clone`/`asr`.
  - `config.py` có flag bật/tắt + đường dẫn asset cho từng engine (đọc từ env/.env).
  - `main.py::_register_backends()` đăng ký `kokoro`/`voicevox` **chỉ khi** khả dụng (package import được + asset có mặt + flag bật); thiếu → bỏ qua im lặng, log 1 dòng, KHÔNG raise.
  - Script tải model đặt trong `scripts/` (bash), idempotent, in rõ đích tải.
- **Non-functional**
  - App khởi động bình thường ở cấu hình tối thiểu (chỉ VieNeu) — guard không làm vỡ startup.
  - Không thêm dependency nặng vào base install (torch KHÔNG được kéo vào bởi `en`/`ja`).

## Architecture

- Giữ pattern VieNeu: `is_available()` static (importlib) + lazy `_get_engine()`. Phase 1 chỉ lo **điều kiện đăng ký** và **nguồn asset**, chưa viết logic synth.
- `encode()` đã sample-rate-agnostic (đã verify `app/audio/encoder.py`) → **không sửa encoder**; Phase 4 thêm 1 test khẳng định 24kHz round-trip.
- Feature-flag mặc định: `enable_kokoro`/`enable_voicevox` = `true` nhưng đăng ký vẫn phụ thuộc `is_available()` → bật flag mà chưa cài asset thì vẫn skip an toàn.
- Đường dẫn asset mặc định dưới `models/` (gitignore) để tách khỏi code: `models/kokoro/`, `models/voicevox/`.

## Related Code Files

- Modify: `pyproject.toml` — thêm `[project.optional-dependencies]` `en`, `ja`; cân nhắc `dependency-groups` cho asset tooling.
- Modify: `app/config.py` — thêm settings (xem Steps).
- Modify: `app/main.py` — mở rộng `_register_backends()` (import trong hàm để tránh import lỗi khi extra thiếu).
- Modify: `.gitignore` — thêm `models/`.
- Create: `scripts/fetch-kokoro.sh` — tải `kokoro-v1.0.int8.onnx` + `voices-v1.0.bin`.
- Create: `scripts/fetch-voicevox.sh` — tải OpenJTalk dict + VVM (chi tiết ở Phase 3).
- Create: `models/.gitkeep` (thư mục đích).

## Implementation Steps

1. **Extras trong `pyproject.toml`:**
   ```toml
   # English preset TTS. Kokoro-82M v1.0 chạy trên onnxruntime (torch-free);
   # cần system package `espeak-ng` cho G2P (xem docs). Model tải riêng qua
   # scripts/fetch-kokoro.sh (không đóng gói theo wheel).
   en = [
       "kokoro-onnx>=0.4",
       "onnxruntime>=1.20",
       "soundfile>=0.12",
   ]
   # Japanese preset TTS. VOICEVOX Core (Rust core + onnxruntime) chạy in-process.
   # Wheel `voicevox_core` cài từ GitHub releases; OpenJTalk dict + VVM tải qua
   # scripts/fetch-voicevox.sh. Xem phase-03 để pin version wheel chính xác.
   ja = [
       "soundfile>=0.12",
   ]
   ```
   - Ghi chú: `voicevox_core` wheel KHÔNG trên PyPI → không đưa thẳng vào `ja`; hướng dẫn cài bằng URL wheel trong `scripts/fetch-voicevox.sh` + docs. `ja` extra giữ dep phụ trợ (soundfile để test/dev).
   - Verify khi cài: `uv sync --extra en` không kéo torch (`uv pip list | grep -i torch` rỗng).
2. **Settings trong `app/config.py`** (thêm vào `Settings`):
   ```python
   # --- Kokoro (English) ---
   enable_kokoro: bool = True
   kokoro_model_path: str = "models/kokoro/kokoro-v1.0.int8.onnx"
   kokoro_voices_path: str = "models/kokoro/voices-v1.0.bin"
   kokoro_default_voice: str = "af_heart"  # giọng preset mặc định khi lenient
   # --- VOICEVOX (Japanese) ---
   enable_voicevox: bool = True
   voicevox_dict_dir: str = "models/voicevox/open_jtalk_dic_utf_8-1.11"
   voicevox_vvm_dir: str = "models/voicevox/vvms"
   voicevox_onnxruntime: str = ""  # "" = dùng onnxruntime mặc định voicevox_core tải kèm
   # Danh sách speaker_uuid|style_id được phép expose (rỗng = tất cả VVM tải được).
   voicevox_speaker_allowlist: str = ""
   ```
3. **Guard đăng ký trong `app/main.py::_register_backends()`** (thêm sau block VieNeu, import cục bộ):
   ```python
   if settings.enable_kokoro:
       try:
           from .backends.kokoro_backend import KokoroBackend
           if KokoroBackend.is_available(settings):
               registry.register(KokoroBackend(settings), default=False)
       except Exception as e:  # extra/asset thiếu -> chạy tiếp, chỉ log
           get_logger("startup").warning("kokoro backend skipped: %s", e)
   if settings.enable_voicevox:
       try:
           from .backends.voicevox_backend import VoicevoxBackend
           if VoicevoxBackend.is_available(settings):
               registry.register(VoicevoxBackend(settings), default=False)
       except Exception as e:
           get_logger("startup").warning("voicevox backend skipped: %s", e)
   ```
   - `is_available(settings)` (static) kiểm tra: package import được **và** file model/dict tồn tại. Chữ ký khác VieNeu (`is_available()` không tham số) — chấp nhận vì cần biết đường dẫn asset; giữ nhất quán tên method.
4. **`scripts/fetch-kokoro.sh`** — tải int8 model + voices vào `models/kokoro/` (URL từ release `thewh1teagle/kokoro-onnx` model-files-v1.0; cho biến `KOKORO_PRECISION=int8|fp16`). Idempotent (skip nếu đã có, verify size).
5. **`.gitignore`**: thêm `models/` (asset lớn, không commit). Tạo `models/.gitkeep`.
6. **Không sửa encoder/router/schemas.** Chỉ verify bằng đọc lại `encoder.py` (đã xong).

## Success Criteria

- [ ] `uv sync --extra en` cài Kokoro không kéo torch; app import `KokoroBackend` không lỗi khi asset có mặt.
- [ ] Bật flag nhưng thiếu asset → app vẫn khởi động, log `kokoro backend skipped: ...`, `GET /v1/models` không có `kokoro`.
- [ ] `scripts/fetch-kokoro.sh` tải đúng `kokoro-v1.0.int8.onnx` (~88MB) + `voices-v1.0.bin`, chạy lần 2 là no-op.
- [ ] Test VieNeu/ASR hiện có vẫn xanh (`pytest -m "not synth"`).

## Testing / Validation

- `pytest -m "not synth"` xanh (không hồi quy lõi).
- Test guard: monkeypatch `is_available` → False, khởi tạo app, assert `kokoro`/`voicevox` không nằm trong `registry.models()` và app vẫn tạo được.
- `python -c "import app.main"` không raise ở cấu hình chỉ-VieNeu.

## Risk Assessment

- **Rủi ro:** `kokoro-onnx` kéo dependency phonemizer nặng/không mong muốn. **Tín hiệu:** `uv pip list` xuất hiện torch hoặc lib build lỗi. **Phản ứng:** pin dep tối thiểu, tách phonemizer sang tài liệu `espeak-ng`; nếu vẫn nặng → replan sang `pip install kokoro-onnx --no-deps` + khai báo dep thủ công.
- **Rủi ro:** version wheel `voicevox_core` trôi so với VVM. **Tín hiệu:** load VVM lỗi version mismatch. **Phản ứng:** pin cả wheel lẫn model theo cùng release trong `scripts/fetch-voicevox.sh` (chi tiết Phase 3).
- **Rủi ro:** guard `is_available(settings)` lệch chữ ký với VieNeu gây nhầm. **Phản ứng:** ghi docstring rõ; giữ VieNeu nguyên trạng, chỉ engine mới nhận `settings`.

## Rollback

- Xóa 2 block guard trong `_register_backends()` + revert `config.py`/`pyproject.toml`. Không có thay đổi lõi/router → rollback không ảnh hưởng VieNeu/ASR.

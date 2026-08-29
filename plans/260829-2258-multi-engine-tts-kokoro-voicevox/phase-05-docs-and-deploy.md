---
title: "Phase 5: Docs & Deploy"
status: done
phase: 5
priority: P2
effort: "0.5d"
dependencies: [2, 3, 4]
---

# Phase 5: Docs & Deploy

## Overview

Cập nhật tài liệu người dùng + maintainer cho stack 3 engine và ghi chú triển khai: bảng engine, biến môi trường, các bước tải model, dependency hệ thống (`espeak-ng`), credit VOICEVOX, và tác động RAM + lazy-load trên deploy 1-worker.

## Requirements

- **Functional**
  - README: bảng engine (VN/EN/JA) + quick start cho từng engine (cài extra, tải model, gọi API mẫu).
  - `docs/kien-truc-va-mo-rong.md`: thêm mục Kokoro + VOICEVOX (adapter in-process, lazy-load, fallback HTTP của VOICEVOX).
  - Biến môi trường mới (`enable_*`, `*_path`, `voicevox_*`) liệt kê ở nơi tài liệu env hiện có.
  - Bước tải model: trỏ tới `scripts/fetch-kokoro.sh` / `scripts/fetch-voicevox.sh` (không copy chi tiết vào docs — link script).
  - Credit VOICEVOX: mục riêng nêu nghĩa vụ hiển thị `VOICEVOX:<nhân vật>`.
  - Deploy: ghi chú `espeak-ng` (apt), dung lượng đĩa model, RAM tăng theo engine bật + lazy-load, giữ mặc định 1 worker.
- **Non-functional**
  - Chỉ cập nhật surface nhỏ nhất sở hữu thông tin; link tới script/manifest thay vì lặp lại. Không phình docs.

## Architecture

- Nguồn sự thật cho "cách tải/chạy" là **script** (`scripts/*.sh`) + `pyproject.toml`; docs chỉ điều hướng + nêu quyết định.
- Cập nhật `API_DESCRIPTION` trong `app/main.py` để phản ánh nhiều backend + ngôn ngữ (đang ghi "first backend VieNeu").

## Related Code Files

- Modify: `README.md`
- Modify: `docs/kien-truc-va-mo-rong.md`
- Modify: `app/main.py` — `API_DESCRIPTION` (đa engine/đa ngôn ngữ).
- Reference (link, không sửa): `scripts/fetch-kokoro.sh`, `scripts/fetch-voicevox.sh`, `pyproject.toml`.
- Modify (nếu có): file deploy/systemd hoặc `docs/` deploy note hiện hữu (dò qua repo; không giả định tên).

## Implementation Steps

1. README — bảng engine + 3 quick start:
   - VN: nguyên trạng.
   - EN: `uv sync --extra en` → `apt-get install espeak-ng` → `bash scripts/fetch-kokoro.sh` → ví dụ curl `model=kokoro`.
   - JA: `bash scripts/fetch-voicevox.sh` (cài wheel + dict + VVM) → ví dụ curl `model=voicevox` → **credit note**.
2. `docs/kien-truc-va-mo-rong.md`: thêm 2 mục engine (in-process, lazy-load, sample_rate 24k, không clone; VOICEVOX kèm fallback HTTP `voicevox_mode`).
3. Liệt kê env mới ở mục cấu hình (tên + mặc định + ý nghĩa). Trỏ `app/config.py` là nguồn.
4. `API_DESCRIPTION`: đổi câu "first backend VieNeu" → mô tả đa backend (VieNeu VN / Kokoro EN / VOICEVOX JA), giữ phần OpenAI-compat.
5. Deploy note: `espeak-ng` bắt buộc cho EN; dung lượng model (~88MB Kokoro + dict/VVM VOICEVOX); RAM: mỗi engine bật nạp lazy ở request đầu, khuyến nghị giữ 1 worker; cách tắt engine (`enable_*=false`) để giảm RAM.
6. Credit: mục "Giấy phép & ghi công" — VOICEVOX yêu cầu hiển thị credit nhân vật khi phát hành audio.

## Success Criteria

- [ ] README render đúng, 3 quick start chạy theo được (đã thử tay ít nhất EN + JA).
- [ ] Docs nêu `espeak-ng`, bước tải model (link script), credit VOICEVOX, tác động RAM/lazy-load.
- [ ] `API_DESCRIPTION` không còn nói "first backend" như thể chỉ 1 engine.
- [ ] Không có bước tải/model chi tiết bị copy lệch giữa docs và script (docs chỉ link).

## Testing / Validation

- Đọc lại + kiểm link (script tồn tại, biến env khớp `config.py`).
- Làm theo quick start trên máy sạch (hoặc mô tả) để chắc bước đủ.

## Risk Assessment

- **Rủi ro:** docs lệch script khi version model đổi. **Phản ứng:** docs link script + `pyproject`, không nhúng URL/hash → giảm điểm lệch.
- **Rủi ro:** bỏ sót credit VOICEVOX. **Phản ứng:** credit vừa ở docs vừa ở `/v1/voices` (Phase 3) + test (Phase 4).

## Rollback

- Revert các file docs. Không ảnh hưởng runtime.

---
title: "CapCut TTS Backend Integration (vi-VN)"
description: "Port idiomatic phần TTS của capcut-tts-api thành CapCutBackend (model='capcut') với 24 giọng Tiếng Việt (vi-VN), giải mã MP3 in-memory qua PyAV và tích hợp đầy đủ lên Frontend."
status: complete
priority: P1
effort: "4h"
tags: [tts, capcut, backend, frontend, vi-vn, xia-port]
created: 2026-10-19
blockedBy: []
---

# CapCut TTS Backend Integration (vi-VN)

## Overview

Port idiomatic (`--port`) tính năng Text-to-Speech từ `phan_tich/capcut-tts-api` vào kiến trúc plugin [`VoiceBackend`](../../app/backends/base.py) của `all-voice` dưới tên model `capcut`. Tích hợp 24 giọng đọc Tiếng Việt (`vi-VN`), giải mã MP3 trả về từ CapCut CDN trực tiếp trên RAM bằng `PyAV` (`av`) sang `float32` PCM để tương thích 100% với bộ mã hóa đa định dạng (`mp3/wav/opus/aac/flac/pcm`), luồng đọc văn bản dài (`/v1/audio/stream`), bộ nhớ đệm (`result_cache`), nghe thử (`previews`), và giao diện React SPA (`frontend/`).

## Source Manifest & Anatomy (`ak:xia`)

- **Source Path**: `phan_tich/capcut-tts-api`
- **Upstream Remote**: `https://github.com/K07VN/capcut-tts-api` (branch `main`, commit `7ab87fb`, version `1.5.0`)
- **Local Target**: `D:\youtube\all_voice` (branch `main`, commit `7720e03`)
- **Selected Mode**: `--port` (viết lại chuẩn xác theo kiến trúc `all-voice`, độc lập hoàn toàn với thư mục `phan_tich/`)
- **Risk Score**: **Low (0 Critical)**

### Source Anatomy
1. **Signing & Identity (`signer.py`, `config.py`, `models.py`)**:
   - Tạo profile thiết bị giả lập CapCut Desktop (`aid="359289"`, `appvr="8.7.0"`, `pf="3"`, `device_id`/`iid`/`tdid` ngẫu nhiên 20 chữ số).
   - Ký HTTP header `x-ss-stub` (MD5 của request body) và `sign` (`md5("9e2c|" + path[-7:] + "|3|" + appvr + "|" + device_time + "|" + tdid + "|11ac")`).
   - Ký TTS payload `sign` bằng RSA PKCS#1 v1.5 thuần Python (`rsa_encrypt_pkcs1v15`) trên chuỗi `appid:{aid}&did:{device_id}&creditDisable:false&ssml:{md5(ssml)}&extraInfo:{extra_info}` với public key `TTS_SIGN_PUBLIC_KEY_PEM`.
2. **Task Lifecycle (`client.py`)**:
   - Tạo SSML `<speak><voice name="{voice_type}" resource_id="{resource_id}" ...><prosody rate="{speed}">{text}</prosody></voice></speak>`.
   - Gửi `POST /lv/v1/common_task/new` (`req_key="sami_text_to_speech"`, `task_version="v3"`) → lấy `task_id`, `token`, `bind_id`.
   - Poll `POST /lv/v1/common_task/query` đến khi `status` đạt `success`/`succeed`/`succeeded`/`completed`/`done`.
   - Đọc URL từ `payload.audio_subtitles[0]` (`speech_url` / `audio_url` / `url`) và tải bytes MP3.
3. **Catalog (`Voice.json`)**:
   - Lọc 24 giọng `vi-VN` (`catalog_kind != "digital_human_voice"`), mỗi bản ghi gồm `voice_type`, `display_name`, `resource_id`, `lang: "vi-VN"`, `lan: "vi"`.

## Dependency & Decision Matrix

### Dependency Matrix

| Source Component | Local Equivalent | Status | Action |
|---|---|---|---|
| `capcut_tts_api/signer.py` + `config.py` | `app/backends/capcut_backend.py` | `NEW` | Port các hàm ký MD5/RSA PKCS#1 v1.5 và ` DEFAULT_DEVICE` vào adapter |
| `capcut_tts_api/client.py` (TTS) | `app/backends/capcut_backend.py` (`CapCutBackend`) | `NEW` | Cài đặt `VoiceBackend`: `list_voices`, `resolve_voice`, `synthesize` |
| `capcut_tts_api/Voice.json` (24 giọng `vi-VN`) | `app/data/capcut_voices.json` | `NEW` | Trích xuất 24 giọng `vi-VN` thành file JSON gọn nhẹ trong `app/data/` |
| `download_tts_audio` (ghi file `.mp3`) | `av` (PyAV) decode in-memory → `AudioResult` | `CONFLICT` | Tải bytes MP3 vào `io.BytesIO`, giải mã bằng `av.open()` sang `np.float32` mono PCM |
| `VODUploader` + STT/Translate | `app/asr/transcriber.py` (`faster-whisper`) | `DROP` | Giữ nguyên `faster-whisper` local; không port STT của CapCut |

### Approved Challenge Decisions

| # | Decision | Source's Way | Local Way | Approved Choice |
|---|---|---|---|---|
| 1 | **Phạm vi tích hợp** | TTS + VOD Upload + STT + Dịch | TTS đa backend + 1 ASR (`faster-whisper`) | **Chỉ tích hợp CapCut TTS (`model="capcut"`) + cập nhật Frontend** |
| 2 | **Ngôn ngữ giọng đọc** | 129 giọng / 10 ngôn ngữ | Bộ lọc ngôn ngữ UI (`vi`, `en`, `ja`) | **Chỉ lấy 24 giọng Tiếng Việt (`vi-VN`)** |
| 3 | **Đóng gói mã nguồn** | Package rời ở `phan_tich/`, dùng `requests` + ghi file tạm | Self-contained trong `app/`, decode PCM trên RAM bằng `PyAV` | **Port gọn vào `app/backends/capcut_backend.py` + `app/data/capcut_voices.json`, decode in-memory (có thể xóa `phan_tich/` sau khi xong)** |

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Cài đặt `CapCutBackend` (`model="capcut"`) tuân thủ 100% hợp đồng `VoiceBackend` + cấu hình `Settings` | P1 |
| 2 | Đóng gói 24 giọng Tiếng Việt (`vi-VN`) vào `app/data/capcut_voices.json` | P1 |
| 3 | Cập nhật Frontend (`types.ts`, `http-tts-api.ts`, `model-select.tsx`) để chọn model CapCut và 24 giọng đọc | P1 |
| 4 | Viết unit tests, kiểm thử tích hợp và cập nhật tài liệu kiến trúc | P1 |

## Phases

| # | Phase | Status | Dependency |
|---|-------|--------|------------|
| 1 | [Phase 1: Backend Adapter & Catalog (vi-VN)](./phase-01-start.md) | Completed | — |
| 2 | [Phase 2: Frontend Engine & Voice Catalog Support](./phase-02-frontend-engine-voice-catalog-support.md) | Completed | 1 |
| 3 | [Phase 3: Tests, Verification & Docs](./phase-03-tests-verification-docs.md) | Completed | 1, 2 |

## Rollback Strategy

- **Tắt nhanh bằng cấu hình**: Đặt `ENABLE_CAPCUT=false` trong `.env` để không đăng ký `CapCutBackend` khi khởi động mà không cần sửa code.
- **Hoàn tác mã nguồn**: Xóa `app/backends/capcut_backend.py`, `app/data/capcut_voices.json`, `tests/test_capcut.py` và `git checkout` các file `app/config.py`, `app/main.py`, `frontend/src/`.

## Success Criteria

- [x] `GET /v1/models` trả về `capcut` khi `ENABLE_CAPCUT=true`.
- [x] `GET /v1/voices?model=capcut` và `GET /v1/voices?language=vi` trả về đúng 24 giọng Tiếng Việt của CapCut kèm `preview_url`.
- [x] `POST /v1/audio/speech` và `POST /v1/audio/stream` với `model="capcut"` sinh được đầy đủ các định dạng (`mp3`, `wav`, `opus`, `aac`, `flac`, `pcm`) mà không tạo file tạm trên đĩa.
- [x] Giao diện Frontend hiển thị model **CapCut** trong dropdown chọn mô hình và liệt kê 24 giọng Tiếng Việt để nghe thử / tạo giọng nói + phụ đề.
- [x] Toàn bộ unit tests (`pytest -m "not synth"` và `vitest`) chạy xanh; thư mục `phan_tich/` không được import ở bất kỳ đâu trong `app/`.

<!-- slug: capcut-tts-backend-integration -->
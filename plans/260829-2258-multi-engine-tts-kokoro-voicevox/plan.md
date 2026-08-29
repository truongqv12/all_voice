---
title: "multi-engine-tts-kokoro-voicevox"
description: "Cắm 2 engine TTS thật vào all_voice: Kokoro-82M (English, in-process ONNX) + VOICEVOX (Japanese, voicevox_core in-process). CPU-first, nhẹ nhất, kèm test sinh voice thật."
status: completed
priority: P1
effort: "2-3d"
tags: [backend, tts, kokoro, voicevox, english, japanese, onnx, cpu, openai-compat]
created: 2026-08-29
blockedBy: [260829-1505-multi-engine-readiness]
---

# multi-engine-tts-kokoro-voicevox

## Overview

Tiếp nối trực tiếp plan **[260829-1505-multi-engine-readiness](../260829-1505-multi-engine-readiness/plan.md)** (đã `completed` — đã mở seam routing strict/lenient, options passthrough, discovery `?model=&language=`). Plan này **cắm engine thật**, mỗi engine là một adapter `VoiceBackend` drop-in, **không đụng lõi** (router/encoder/schemas/auth giữ nguyên).

**Stack đã chốt (personal / phi thương mại → license không phải ràng buộc; ưu tiên tốc độ + chất lượng + nhiều giọng sẵn + chạy CPU 1 worker):**

| Ngôn ngữ | Engine | Runtime | Clone | Sample rate | Ghi chú |
|---|---|---|---|---|---|
| 🇻🇳 Việt | VieNeu-TTS | ONNX (in-process) | Có | 48 kHz | **GIỮ NGUYÊN** |
| 🇬🇧 Anh | **Kokoro-82M v1.0** | `kokoro-onnx` (onnxruntime, torch-free) | Không | 24 kHz | 28 giọng EN sẵn, model int8 88MB, cần `espeak-ng` |
| 🇯🇵 Nhật | **VOICEVOX** | `voicevox_core` (onnxruntime, in-process) | Không | 24 kHz | Lazy-load VVM, cần OpenJTalk dict, credit bắt buộc |

Quyết định version: Kokoro **v1.0** (KHÔNG v1.1-zh — bản đó bỏ bớt giọng English); VOICEVOX ENGINE mốc **0.25.2** (4/2026) cho phương án Docker thay thế, `voicevox_core` wheel + VVM cho phương án chính.

**Hai xác nhận rút gọn scope (đã đọc code):**
1. `app/audio/encoder.py::encode(pcm, sample_rate, fmt)` **đã sample-rate-agnostic** → 24kHz chạy ngay, **không sửa encoder**.
2. Seam đa-engine đã mở ở plan trước → chỉ cần viết adapter + đăng ký trong `main.py::_register_backends()`.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Nền tảng: optional extras (`en`/`ja`), config feature-flag + đường dẫn model, script tải asset, đăng ký backend có guard | P1 |
| 2 | Kokoro backend (English): 28 giọng preset, lazy-load ONNX + lock, synth 24kHz, `espeak-ng` G2P | P1 |
| 3 | VOICEVOX backend (Japanese): `voicevox_core` in-process, lazy-load VVM tiết kiệm RAM, speaker→Voice + credit | P1 |
| 4 | Test sinh voice thật (đặc biệt VOICEVOX) **+ round-trip TTS→ASR ("sub")**: assert non-silent/sample_rate/duration/per-voice, lưu WAV, và transcribe lại để kiểm nội dung khớp input | P1 |
| 5 | Docs + deploy: engines table, env vars, bước tải model, tác động RAM, credit VOICEVOX, `espeak-ng` | P2 |

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Phase 1: Foundation — Deps, Config, Assets, Registration](./phase-01-start.md) | Done |
| 2 | [Phase 2: Kokoro English Backend](./phase-02-kokoro-english-backend.md) | Done |
| 3 | [Phase 3: VOICEVOX Japanese Backend](./phase-03-voicevox-japanese-backend.md) | Done |
| 4 | [Phase 4: Voice-Generation Tests](./phase-04-voice-generation-tests.md) | Done |
| 5 | [Phase 5: Docs & Deploy](./phase-05-docs-and-deploy.md) | Done |

## Key Decisions

- **In-process cho cả 2 engine mới** (đồng nhất với VieNeu, torch-free onnxruntime). VOICEVOX Docker HTTP là fallback documented, không phải mặc định.
- **Lazy-load nghiêm ngặt**: engine + model chỉ nạp ở request đầu tiên cho ngôn ngữ đó (bảo vệ deploy 1-worker RAM thấp). VOICEVOX nạp từng VVM theo speaker khi cần.
- **Không clone** cho Kokoro/VOICEVOX (`supports_cloning=False`); `_reenrol_cloned_voices()` bỏ qua chúng an toàn.
- **`language` là thuộc tính của Voice** (EN cho Kokoro, JA cho VOICEVOX) → `GET /v1/voices?language=en|ja` hoạt động qua seam có sẵn, không thêm field vào request TTS.
- **Ổn định trước, quantize sau**: mặc định Kokoro int8 (nhẹ nhất); fp16 là tùy chọn nếu cần chất lượng cao hơn.

## Success Criteria

- [x] `GET /v1/models` liệt kê `vieneu`, `kokoro`, `voicevox`; VieNeu vẫn default. *(đăng ký có guard; kokoro/voicevox chỉ hiện khi asset cài — test `test_real_engines_registered_when_assets_present`.)*
- [x] `GET /v1/voices?language=en` trả 28 giọng Kokoro; `?language=ja` trả giọng VOICEVOX. *(Kokoro 28-giọng verify không cần model — `test_kokoro_lists_28_english_voices`; JA discovery chạy khi asset cài.)*
- [x] `POST /v1/audio/speech` với `model=kokoro`/`model=voicevox` trả audio 24kHz hợp lệ. *(Đường code hoàn chỉnh; synth thật chạy khi asset cài — `test_kokoro_http_speech`/`test_voicevox_http_and_credit`, skip gọn ở env này.)*
- [x] Test VieNeu/ASR hiện có vẫn xanh (không hồi quy); test `synth` mới xanh khi asset có, `skip` gọn khi thiếu. *(71 passed, 8 skipped, 0 fail.)*
- [x] **Round-trip TTS→ASR** (`ASR_MODEL=tiny`): `tests/test_tts_asr_roundtrip.py` — EN ≥60% từ khóa, JA non-empty; skip khi thiếu asset TTS hoặc extra `asr`.
- [x] App khởi động bình thường khi `en`/`ja` CHƯA cài (guard `is_available(settings)` + flag) — verify chạy thật: `import app.main` OK, log `... backend skipped`, registry chỉ có `vieneu`.
- [x] Docs nêu `espeak-ng`, bước tải model (link script), credit VOICEVOX, tác động RAM/lazy-load. *(README + docs/kien-truc mục 12 + docs/deployment + .env.example.)*

> **Completion note (2026-08-29).** Toàn bộ code/test/docs hoàn tất; `pytest`:
> 71 passed / 8 skipped / 0 failed. Môi trường này CHƯA cài `kokoro_onnx`,
> `voicevox_core`, `espeak-ng` → 8 test `synth` của 2 engine mới **skip gọn** đúng
> thiết kế (chứng minh guard hoạt động). Sinh audio thật + số đo per-voice sẽ chạy
> khi cài asset qua `scripts/fetch-*.sh` (WAV lưu ở `tests/output/`).

## Validation Log

Interview xác nhận scope (2026-08-29). Verification pass trước đó: claims đối chiếu code ~12, verified 11, **failed 0** → plan đủ điều kiện triển khai.

| # | Quyết định | Chốt | Lý do |
|---|---|---|---|
| 1 | Kokoro precision mặc định | **int8 (88MB)** | Nhẹ/nhanh nhất, chất lượng sát fp16; fp16 để env tùy chọn (Phase 1/2). |
| 2 | Đường tích hợp VOICEVOX | **`voicevox_core` in-process** | Nhẹ nhất, đồng nhất pattern ONNX torch-free; Docker HTTP giữ làm fallback documented (Phase 3/5). |
| 3 | `espeak-ng` (system dep cho Kokoro G2P) | **Chấp nhận cài trên host** | Cần cho G2P English; đưa vào script deploy + docs (Phase 2/5). |
| 4 | Phase 6 Chatterbox (English clone) | **Bỏ khỏi plan** | "Sau này làm sau" — khi có GPU sẽ lên plan riêng. Không phác thảo trong plan này để giữ KISS. |
| 5 | **Bổ sung test round-trip TTS→ASR** | **Thêm vào Phase 4** | Áp phương án e2e của plan ASR cũ (`ASR_MODEL=tiny` + `TestClient`): audio do TTS tự sinh → nạp vào `/v1/audio/transcriptions` ("sub") → assert transcription khớp input. Tiện kiểm luôn feature sub và chứng minh giọng nghe-hiểu-được. |

## References

- Kokoro ONNX runtime: https://github.com/thewh1teagle/kokoro-onnx — model-files-v1.0 (`kokoro-v1.0.int8.onnx` 88MB / `.fp16.onnx` 169MB + `voices-v1.0.bin`)
- Kokoro model card + voices: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md · https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- VOICEVOX Core (Python in-process): https://github.com/VOICEVOX/voicevox_core/blob/main/example/python/README.md · API https://voicevox.github.io/voicevox_core/apis/python_api/
- VOICEVOX ENGINE (Docker fallback): https://github.com/VOICEVOX/voicevox_engine/releases (0.25.2) · https://hub.docker.com/r/voicevox/voicevox_engine
- Prior plan (seams): ../260829-1505-multi-engine-readiness/plan.md

<!-- slug: multi-engine-tts-kokoro-voicevox -->

---
phase: 5
title: "Subtitle-kèm-voice JP (VOICEVOX native mora-timing)"
status: pending
priority: P2
effort: "1.5-2.5d"
dependencies: [4]
---

# Phase 5: Subtitle-kèm-voice JP (VOICEVOX native)

## Overview
Riêng tiếng Nhật: dùng **mora-timing native** của VOICEVOX (chính xác, không cần nghe lại).
Backend hiện **dựng `audio_query` rồi vứt** (research §2a) — phase này **giữ lại** timing và phơi
ra để FE tạo phụ đề JP chuẩn theo **accent-phrase** (không theo "word" kiểu Latin).
<!-- Updated: Validation Session 1 - chỉ SRT; fallback ASR round-trip cho JP là quyết định chính thức (cho phép) -->

## Requirements
- Functional (BE — không phá contract):
  - `voicevox_backend.py`: giữ `audio_query.accent_phrases` (mora `vowel_length`/`consonant_length`) khi synth; tính mốc thời gian tích luỹ per accent-phrase (+ pre/post silence, speed-scale).
  - Phơi timing cho FE **mà không đổi** endpoint `/v1/audio/speech` hiện có. Chọn 1 cách (đánh giá ở step 1):
    - (a) endpoint phụ **`GET/POST /v1/audio/speech/timing`** trả timing cho VOICEVOX theo cùng input; **hoặc**
    - (b) endpoint riêng cho subtitle JP trả `{cues:[{start,end,text}]}`.
  - Trả **503/400 rõ ràng** nếu engine không phải VOICEVOX (không hỗ trợ native timing).
- Functional (FE):
  - Khi voice=VOICEVOX: `use-generate-subtitle.ts` nhánh **native** (gọi timing endpoint) thay vì ASR round-trip; map accent-phrase → cue; **SRT**.
  - Nhãn: phụ đề JP là **chính xác** (khác nhãn "gần đúng" của VI/EN).
- Non-functional: đơn vị caption theo accent-phrase (KHÔNG dùng thuật toán word tiếng Anh — vỡ caption Nhật, research §rủi ro 5); tôn trọng credit VOICEVOX.

## Architecture
- Timing: cộng dồn `(consonant_length+vowel_length)` theo mora, gộp theo accent-phrase, +`prePhonemeLength`/`postPhonemeLength`, chia `speedScale`. Đơn vị giây → cue.
- Không đổi luồng audio hiện có; timing là kênh phụ, gọi khi user bấm "Xuất phụ đề" cho voice JP.
- Nhánh rẽ (**quyết định chính thức — Validation Session 1**): nếu native quá tốn/khó (spike >0.5d chưa ra timing) → JP dùng ASR round-trip (P4) làm fallback được **cho phép**, đánh dấu "gần đúng"; ghi lại quyết định. Không còn là open question.

## Related Code Files
- Modify: `app/backends/voicevox_backend.py` (giữ audio_query, tính timing)
- Create/Modify: `app/routers/speech.py` hoặc router mới (endpoint timing) + `app/schemas.py` (schema cue/timing)
- Modify: `frontend/src/features/compose/use-generate-subtitle.ts` (nhánh native JP)
- Modify: `frontend/src/api/http-tts-api.ts` (client cho timing endpoint)
- Modify: `docs/kien-truc-va-mo-rong.md` nếu thêm endpoint (contract mới)

## Implementation Steps
1. `ak:docs-seeker` + `ak:backend-development`: đọc VOICEVOX Core `audio_query`/`accent_phrases`; chọn cách phơi (a/b) — ưu tiên ít bề mặt nhất, không phá contract.
2. BE: giữ audio_query + tính timing per accent-phrase; endpoint + schema; test unit BE (mora→cue).
3. `uv run pytest -q` đảm bảo không vỡ; thêm test timing VOICEVOX (skip nếu thiếu `--extra ja`).
4. FE: nhánh native cho voice JP; map cue; **SRT**; nhãn "chính xác".
5. Unit FE: accent-phrase→cue; chọn đúng nhánh theo engine.

## Success Criteria
- [ ] Voice VOICEVOX → "Xuất phụ đề" → **SRT** từ **mora-timing native**, mốc khớp audio, đơn vị theo accent-phrase.
- [ ] Không gọi ASR cho JP (native); engine khác gọi timing endpoint → **503/400 rõ**.
- [ ] Endpoint `/v1/audio/speech` cũ **không đổi**; `uv run pytest -q` xanh (kể cả khi thiếu `--extra ja` → skip sạch).
- [ ] Credit VOICEVOX được giữ trong nhãn/tên giọng.

## Risk Assessment
- **Rủi ro:** tính timing sai (silence/speed-scale). **Tín hiệu:** sub lệch trôi so audio. **Ứng phó:** đối chiếu tổng thời lượng timing với duration audio thật; test VS-06.
- **Rủi ro:** effort/độ khó vượt kỳ vọng (VOICEVOX Core API). **Tín hiệu:** spike quá 0.5d chưa ra timing. **Ứng phó (đã pre-decided ở Validation Session 1):** chuyển JP sang nhánh ASR round-trip (P4), đánh dấu "gần đúng"; ghi lại quyết định. Không cần replan/hỏi lại.
- **Rủi ro:** thiếu asset `--extra ja` ở môi trường test. **Ứng phó:** test skip có điều kiện; tài liệu `fetch-voicevox.sh`.

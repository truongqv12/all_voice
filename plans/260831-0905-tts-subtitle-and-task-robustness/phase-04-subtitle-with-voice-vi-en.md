---
phase: 4
title: "Subtitle-kèm-voice VI/EN (ASR round-trip)"
status: pending
priority: P1
effort: "1-1.5d"
dependencies: [1, 2, 3]
---

# Phase 4: Subtitle-kèm-voice VI/EN (ASR round-trip)

## Overview
Tính năng chính: sau khi tạo voice (VieNeu/Kokoro), người dùng **xuất phụ đề** khớp audio.
Cách "gần đúng": lấy audio vừa sinh → đưa qua `/v1/audio/transcriptions` (kèm **`prompt`=text gốc**
để bám chữ) → chunk client-side → **SRT**. Không cần endpoint BE mới.
<!-- Updated: Validation Session 1 - chỉ SRT; timeout 150s chung -->

## Requirements
- Functional:
  - Bật `appConfig.features.ttsToSrt = true`; hiện nút "Xuất phụ đề" ở `audio-result-card.tsx`.
  - Orchestration (`use-generate-subtitle.ts` NEW): nhận audio Blob đã sinh (buffered hoặc stream-đã-gộp) → `POST /v1/audio/transcriptions` với `response_format=verbose_json`, `timestamp_granularities=['word']`, `prompt=<text gốc người dùng>` → nhận segments+words → `chunkCues()` (lib có sẵn) → `toSrt()` → tải file `.srt`.
  - Truyền `AbortSignal`+**timeout 150s chung (P1)**; progress "Đang tạo phụ đề…"; nút Hủy/Retry.
  - UI **cảnh báo "phụ đề gần đúng"** (có thể lệch chữ do nhận dạng lại) — không quảng cáo verbatim.
  - Tùy chọn export (tái dùng `subtitle-export-panel` patterns): max chars/line, lines/cue. **Chỉ định dạng SRT** (quyết định Validation Session 1).
  - Chỉ áp cho engine **vieneu/kokoro** ở phase này (VOICEVOX để P5); ẩn/điều hướng nút đúng theo engine.
- Non-functional: tái dùng `lib/subtitle/*` (không viết lại chunk); không giữ 2 bản audio thừa (revoke); i18n VN/EN; tôn trọng giới hạn 20k (P2).

## Architecture
- Luồng: `generate() → audioBlob` (đã có) → `generateSubtitle(audioBlob, originalText, opts)` → transcribe(prompt) → words→cues → srt.
- Dùng lại `distributeWords`/`chunkCues` (đã có + test). `prompt` giảm lệch nhưng không đảm bảo 100% (ghi rõ ở UI).
- Chi phí: 2× (synth + ASR) — hiển thị progress 2 pha; timeout 150s chung (P1) áp cho pha ASR.

## Related Code Files
- Create: `frontend/src/features/compose/use-generate-subtitle.ts` (orchestration)
- Modify: `frontend/src/config/app-config.ts` (`ttsToSrt: true`)
- Modify: `frontend/src/features/compose/audio-result-card.tsx` (nút + cảnh báo "gần đúng")
- Modify: `frontend/src/api/http-transcribe-api.ts` (nhận `prompt`; signal)
- Reuse: `frontend/src/lib/subtitle/{chunk-cues,to-srt,conventions}.ts` (chỉ SRT ở luồng này)
- Modify: `frontend/src/i18n/index.ts` (copy phụ đề/cảnh báo)

## Implementation Steps
1. `ak:frontend-development` + `ak:ui-ux-pro-max`: thiết kế nút + trạng thái "gần đúng"/progress.
2. Viết `use-generate-subtitle.ts` orchestrate audio→transcribe(prompt)→chunk→srt (dùng abort/timeout 150s P1).
3. Bật flag + nút ở result-card; ẩn cho VOICEVOX (P5 xử lý riêng).
4. Bảo đảm export options + tải SRT đúng chuẩn (tái dùng lib).
5. Unit: orchestration (mock transcribe trả words → cues đúng); prompt được gửi; abort huỷ giữa chừng.

## Success Criteria
- [ ] Tạo voice VI/EN → "Xuất phụ đề" → **SRT** tải về, mốc giờ **khớp audio**, nội dung **bám text gốc** (nhờ prompt).
- [ ] Có nhãn "phụ đề gần đúng"; progress "đang tạo phụ đề"; Hủy/Retry chạy; không rò objectURL.
- [ ] Đổi options (chars/line, format) đổi output; dùng lại lib subtitle (không trùng lặp code).
- [ ] Unit orchestration xanh.

## Risk Assessment
- **Rủi ro:** ASR nghe lại lệch nhiều (tên riêng/số/`[cười]`). **Tín hiệu:** sub sai chữ. **Ứng phó:** `prompt`=text gốc giảm lệch; UI cảnh báo "gần đúng"; (tương lai) cân nhắc align text gốc với word-timing.
- **Rủi ro:** 2× CPU làm chậm/nghẽn slot (429). **Tín hiệu:** 429 khi tạo sub. **Ứng phó:** progress+timeout+retry (P1); nối tiếp synth→ASR (không song song); text ≤20k (P2).
- **Rủi ro:** audio stream chưa gộp đủ khi gọi ASR. **Tín hiệu:** ASR nhận thiếu. **Ứng phó:** chờ stream xong (đã gộp Blob) mới transcribe.

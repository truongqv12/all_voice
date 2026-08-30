---
title: "Phase 4: Speech-to-Text (mock) + subtitle export"
status: done
---

# Phase 4: Speech-to-Text (ASR) — mock + xuất phụ đề SRT/VTT/TXT

## Overview
Dựng khu **`/transcribe`**: thả/chọn file audio → "transcribe" giả lập → xem transcript (segment + word timestamp) → **xuất SRT / VTT / TXT** và copy. Đây là **bề mặt xuất phụ đề chính** của sản phẩm (backend thật đã hỗ trợ `srt`/`vtt`/`verbose_json`+word). Logic **cắt cue theo chuẩn phụ đề chạy THẬT phía client** trên fixture có word-timestamp (không fake), để tích hợp sau chỉ swap `mock → http`.

Xem báo cáo nghiên cứu: `plans/reports/research-260830-srt-subtitle-export.md`.

## Requirements
- Functional: `AudioDropZone` nhận `.mp3/.wav/.m4a` (kéo-thả + chọn); mock progress upload→transcribe→done; `TranscriptPanel` hiện segment + timestamp, highlight cue đang phát khi nghe lại; `SubtitleExportPanel` chọn **format** (SRT/VTT/TXT), **max chars/line** (mặc định 42), **max lines/cue** (2), **granularity** (word-accurate / sentence), hiện **ngôn ngữ**; **Download** (Blob) + **Copy**. 1 fixture transcript (segments + `words[]` có start/end).
- Non-functional: bộ cắt cue **chạy thật** client-side theo chuẩn (≤42 ký tự/dòng, ≤2 dòng/cue, CPS ≤17-20 Latin / ~4 CJK, cue min ~0.83s max ~7s); mobile-first; a11y (aria-live progress, panel export bàn phím được); reduced-motion; **không** dịch (transcribe-only).

## Architecture
- `useTranscribe` (mock): `File` → phát progress (`idle|uploading|transcribing|done|error`) → trả `TranscriptionResult` từ fixture (segments + words). Lỗi định dạng/quá-dài → `error` + copy hướng khắc phục.
- `lib/subtitle/`: **bộ dựng phụ đề client-side** —
  - `chunk-cues.ts`: greedy-fill `words[]` vào dòng tới giới hạn ký tự, ưu tiên ngắt ở dấu câu/mệnh đề, tách cue mới khi vượt thời lượng/CPS; đơn vị **CJK theo cụm** (không theo space).
  - dùng **`subsrt-ts`** (zero-dep) để serialize, hoặc `to-srt.ts`/`to-vtt.ts` tự viết (SRT phẩy + đánh số; VTT chấm + header `WEBVTT`); `to-txt.ts` = văn bản thuần.
  - hằng số chuẩn đặt trong `lib/subtitle/conventions.ts` (đổi 1 chỗ).
- `TranscriptPanel` + `useTranscriptPlayback`: `<audio>` phát lại file đã tải; highlight segment/word theo `currentTime` (tách khỏi preview giọng ở phase 2 & result ở phase 3 — nhiều instance không đá nhau).
- `SubtitleExportPanel`: toggle format + options; **preview** vài cue đầu để thấy hiệu ứng chunk; Download đặt tên `{tên-file}.{srt|vtt|txt}`.
- `TranscribePage` (route `/transcribe`): empty (upload prompt) → progress → transcript + export.
- **Mock→thật:** backend `POST /v1/audio/transcriptions` (`response_format` + `timestamp_granularities[]=word`) → tích hợp = thêm `httpTranscribeApi`; **giữ nguyên** bộ chunk client-side (vì `to_srt`/`to_vtt` backend hiện chỉ segment-level).

## Related Code Files
- Create: `frontend/src/features/transcribe/transcribe-page.tsx`, `audio-drop-zone.tsx`, `transcript-panel.tsx`, `subtitle-export-panel.tsx`, `subtitle-preview.tsx`
- Create: `frontend/src/features/transcribe/use-transcribe.ts`, `use-transcript-playback.ts`
- Create: `frontend/src/lib/subtitle/chunk-cues.ts`, `to-srt.ts`, `to-vtt.ts`, `to-txt.ts`, `conventions.ts`
- Create: `frontend/src/data/transcript-fixture.ts` (segments + word timestamps, VN + 1 EN mẫu)
- Create: `frontend/src/api/transcribe-api.ts` (interface + `mockTranscribeApi`) — cùng pattern `TtsApi`
- Modify: `frontend/src/app/router.tsx` (route `/transcribe`), `frontend/src/i18n/locales/*` (chuỗi ASR/export)

## Implementation Steps
1. `transcribe-api` interface + `mockTranscribeApi` (progress giả + trả fixture); `transcript-fixture` (segments + words).
2. `AudioDropZone`: nhận audio, lỗi định dạng inline; `useTranscribe` chạy progress.
3. `lib/subtitle/conventions.ts` + `chunk-cues.ts` (thuật toán chunk theo chuẩn); unit-test nhỏ vài case (dài dòng, dấu câu, CPS, CJK).
4. `to-srt`/`to-vtt`/`to-txt` (hoặc `subsrt-ts`) serialize từ cue đã chunk.
5. `TranscriptPanel` + `useTranscriptPlayback`: hiện segment + highlight theo `currentTime`.
6. `SubtitleExportPanel`: format + options + preview + Download (Blob) + Copy.
7. Ráp `TranscribePage` (empty/progress/result/error); nối route `/transcribe`.

## Success Criteria
- [ ] Thả/chọn file audio → progress → transcript hiện segment + timestamp; lỗi định dạng demoable.
- [ ] Đổi format SRT/VTT/TXT + options (chars/line, lines/cue, granularity) đổi output; **preview** cập nhật.
- [ ] Download ra file `.srt/.vtt/.txt` **đúng chuẩn** (SRT phẩy/đánh số; VTT header+chấm); Copy hoạt động.
- [ ] Bộ chunk tôn trọng ≤42 ký tự/dòng, ≤2 dòng/cue, min/max thời lượng (kiểm bằng unit-test).
- [ ] Nghe lại audio → highlight cue theo thời gian; không đá nhau với player khác.
- [ ] Mobile: upload + transcript + export xếp gọn, thao tác ngón tay tốt (≥44px).

## Risk Assessment
- **Chunk sai chuẩn** → cue quá dài/nhấp nháy. Mitigation: hằng số từ báo cáo research trong `conventions.ts`; unit-test các ngưỡng. Signal: preview cue vượt 2 dòng.
- **CJK (Nhật) cắt theo "word" tiếng Anh** → vỡ caption. Mitigation: nhánh CJK cắt theo cụm ký tự/độ dài, CPS ~4; đánh dấu trong code.
- **Nhầm SRT/VTT** (phẩy vs chấm, header). Mitigation: 2 serializer tách bạch + test snapshot 1 cue.
- **Kỳ vọng "transcribe thật"** khi đang mock. Mitigation: nhãn rõ "dữ liệu mẫu"; interface sẵn để swap http ở integration.
- **TTS→SRT (tương lai) không thuộc phase này**: verbatim cho Kokoro/VieNeu chưa có lời giải nhẹ (xem research). Chỉ để affordance mock ở result-card TTS (phase 3), không hiện thực.

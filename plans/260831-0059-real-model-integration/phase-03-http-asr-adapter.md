---
phase: 3
title: "http-asr-adapter (transcribe + words→segments)"
status: pending
priority: P1
effort: "0.5-1d"
dependencies: [1]
---

# Phase 3: http-asr-adapter

## Overview

Điền `http-transcribe-api.ts` implement `TranscribeApi` bằng `POST /v1/audio/transcriptions` (multipart, `verbose_json` + word timestamps). Việc then chốt: BE trả `words` **top-level** ⇒ adapter **phân bổ words vào từng segment** theo overlap thời gian và rename `word→text`, để bộ **subtitle chunk client-side** (đã có, giữ nguyên) tiếp tục cắt cue chuẩn.

Skills: `ak:frontend-development`, `ak:docs-seeker` (XHR upload progress; fetch multipart).

## Requirements

- Functional:
  - `transcribe(file, onProgress)`: gửi multipart `file`, `response_format=verbose_json`, `timestamp_granularities[]=word` (+ `language` nếu người dùng chọn). Trả `TranscriptionResult{language, segments:[{id,text,start,end,words:[{text,start,end}]}]}`.
  - **Upload progress** qua `XMLHttpRequest` (`upload.onprogress` → `onProgress('uploading', pct)`); sau khi upload xong chuyển `onProgress('transcribing', <indeterminate>)` (BE trả 1 phát, không có % transcribe).
  - **Phân bổ words → segments**: mỗi word gán vào segment có `[start,end]` chứa `word.start` (hoặc overlap lớn nhất); nếu BE không trả `words` (thiếu extra ASR/word) → `segment.words=[]` và subtitle fallback về segment-level (vẫn chạy).
  - Giữ **subtitle chunk client-side** (`src/lib/subtitle/*`) — **không** dùng `response_format=srt` của BE.
  - Lỗi: `413` (audio quá dài anon) → `ApiError` → `mapError` → `kind='asr-too-long'`; `429` → rate/quota; `503` (chưa cài ASR) → generic "dịch vụ ASR chưa sẵn sàng". **[F1]** `use-transcribe` set `kind` cho `LimitStates` error-driven mount ở transcribe page.
- Non-functional: kiểm `file.size` client-side (≤25 MiB) trước khi gửi để báo sớm; không chặn UI; giữ i18n VN/EN.

## Architecture

- Multipart bằng `FormData`; **dùng XHR** (fetch không expose upload progress ổn định):
  ```ts
  const fd = new FormData()
  fd.append('file', file)
  fd.append('response_format', 'verbose_json')
  fd.append('timestamp_granularities[]', 'word')
  if (language) fd.append('language', language)
  // XHR: upload.onprogress -> onProgress('uploading', e.loaded/e.total*100)
  // onload: parse JSON -> map; onerror/status>=400 -> ApiError(parse envelope)
  ```
- **Map verbose_json → TranscriptionResult:**
  - `language = json.language`
  - `segments = json.segments.map(s => ({ id:String(s.id), text:s.text.trim(), start:s.start, end:s.end, words:[] }))`
  - phân bổ `json.words` (mỗi `{word,start,end}`) vào segment khớp thời gian → push `{text:w.word, start:w.start, end:w.end}`.
- **transcribe indeterminate:** vì BE đồng bộ, giai đoạn 'transcribing' hiện thanh indeterminate (giống stream TTS) — tái dùng pattern progress ở phase 2 nếu component chung, hoặc cờ riêng trong `use-transcribe`.

## Related Code Files

- Modify: `frontend/src/api/http-transcribe-api.ts` (implement đầy đủ)
- Modify: `frontend/src/features/transcribe/use-transcribe.ts` (dùng `useTranscribeApi()`; xử lý indeterminate transcribe + lỗi 413)
- Modify: `frontend/src/features/transcribe/audio-drop-zone.tsx` (check size ≤25MiB, copy 413/limit VN-EN) — nếu chưa có
- Modify: `frontend/src/i18n/locales/vi.json`, `en.json` (chuỗi lỗi ASR: too_long/service_unavailable nếu thiếu)
- Reuse (không đổi): `frontend/src/lib/subtitle/*`, `subtitle-export-panel.tsx`, `subtitle-preview.tsx`

## Implementation Steps

1. Implement XHR upload + parse verbose_json.
2. Viết hàm `distributeWords(segments, words)` (thuần, dễ unit-test ở phase 6).
3. Nối `use-transcribe` với indeterminate 'transcribing' + map lỗi 413/429/503.
4. Thêm client-side size check + chuỗi i18n còn thiếu.
5. Chạy thật: upload 1 file audio ngắn (vi) → xem transcript, timestamp, xuất SRT/VTT/TXT vẫn đúng; thử file >300s để thấy 413 state.

## Success Criteria

- [ ] Upload → transcript segment + timestamp thật; `words` phân bổ đúng vào segment (kiểm bằng unit `distributeWords`).
- [ ] Xuất **SRT/VTT/TXT** vẫn đúng chuẩn (unit subtitle cũ xanh; cue dùng word-level khi có).
- [ ] Upload progress chạy; 'transcribing' hiện indeterminate.
- [ ] File >25MiB chặn sớm client-side; audio >300s (anon) → state `asr-too-long` VN/EN; 503 → thông báo dịch vụ chưa sẵn sàng.
- [ ] `npm run build` xanh.

## Risk Assessment

- **Rủi ro:** BE không trả `words` (thiếu `--extra asr` word hoặc engine tiny bỏ word). **Tín hiệu:** `json.words` undefined. **Ứng phó:** `segment.words=[]`; subtitle chunk fallback segment-level (đã hỗ trợ) — không vỡ.
- **Rủi ro:** ranh giới word không khớp segment (word rơi giữa 2 segment). **Tín hiệu:** word bị bỏ/nhân đôi. **Ứng phó:** gán theo `word.start ∈ [seg.start, seg.end)`; word ngoài mọi segment → segment gần nhất; unit-test ca biên.
- **Rủi ro:** XHR + i18n + reduced-motion phức tạp hoá component. **Ứng phó:** giữ XHR trong adapter (thuần), component chỉ nhận callback — KISS.

---
phase: 3
title: "Preview + error-map + gỡ sample giả"
status: completed
priority: P1
effort: "0.5-1d"
dependencies: [1]
---

# Phase 3: Preview + error-map + gỡ sample giả

## Overview
Sửa 3 defect/giả: (a) preview 404 bị fallback synth câu cứng che → dùng `preview_url` thật;
(b) error-map thiếu/nhầm mã lỗi; (c) gỡ nút "Thử âm thanh mẫu" giả (fixture). Lấp GAP-1/3/6.

## Requirements
- Functional — Preview:
  - `use-voice-preview.ts`: **bỏ** nhánh catch→synth câu cứng ("Xin chào, đây là giọng đọc thử của tôi.").
  - Dùng `voice.previewUrl` do `/v1/voices` cấp (public); chỉ khi thiếu mới dựng `/voices/{engine}/{id}/preview` — và đảm bảo `{engine}/{id}` **đúng** với dữ liệu BE (`http-tts-api.ts:117-119`, `voiceCache`).
  - 404 thật → thông điệp "Giọng này chưa có mẫu nghe thử" (VN/EN), dừng spinner (không xoay vô hạn).
- Functional — error-map (`error-map.ts`):
  - Thêm map: `invalid_audio_file` & `audio_file_too_large` (400) → kind riêng "audio-invalid"/"audio-too-large" (thông điệp file âm thanh không hợp lệ / quá lớn); `preview_not_found` (404) → "no-preview"; `invalid_api_key` (401) → "auth".
  - **Sửa thứ tự:** khớp **`err.code` trước `err.status`** để `asr_unavailable` (503) hiện "ASR chưa sẵn sàng (thiếu extra asr)" **thay vì** "overloaded". Chỉ 503 không có code mới rơi về overloaded.
  - Bổ sung copy VN/EN cho các kind mới vào limit-states/thông điệp lỗi.
- Functional — Gỡ sample:
  - Xoá `transcribeSample()` + import `transcriptFixture` khỏi `use-transcribe.ts`; gỡ nút "Thử âm thanh mẫu" khỏi `audio-drop-zone.tsx`/`transcribe-page.tsx`.
  - Dọn fixture nếu không còn nơi dùng (giữ nếu unit/visual còn cần — kiểm grep).
- Non-functional: không phá luồng upload file thật; i18n đủ; không rò objectURL preview.

## Architecture
- Preview: nguồn đúng = `preview_url` từ list voices (BE đảm bảo `{engine}/{id}` khớp). Root-cause 404 "voice '001'" = FE dựng URL sai/id lệch → ưu tiên dùng URL BE cấp, loại tự-dựng khi có sẵn.
- error-map: `if (err.code) switch(code)…` trước, rồi mới tới `switch(status)`; giữ 413/429/402 như cũ.

## Related Code Files
- Modify: `frontend/src/features/voice/use-voice-preview.ts` (bỏ fallback; 404 rõ)
- Modify: `frontend/src/api/http-tts-api.ts` (getPreviewUrl dùng preview_url; kiểm voiceCache id/engine)
- Modify: `frontend/src/api/error-map.ts` (mã mới + ưu tiên code trước status)
- Modify: `frontend/src/features/transcribe/use-transcribe.ts` (gỡ transcribeSample)
- Modify: `frontend/src/features/transcribe/audio-drop-zone.tsx`, `transcribe-page.tsx` (gỡ nút sample)
- Modify: `frontend/src/i18n/index.ts` (copy lỗi/preview mới)
- Maybe delete: `frontend/src/data/transcript-fixture.ts` (nếu hết tham chiếu)

## Implementation Steps
1. `ak:fix`: preview — bỏ fallback, dùng preview_url, 404 rõ; kiểm `voiceCache` map id↔engine.
2. error-map: thêm mã + đảo thứ tự code-trước-status; copy VN/EN.
3. Gỡ nút sample + `transcribeSample()`; grep dọn fixture.
4. Unit: `error-map.test.ts` mở rộng (400-audio/401/404/503-asr đúng kind); test preview 404 không fallback.

## Success Criteria
- [ ] Nghe thử **nhiều voice** → mỗi voice phát **mẫu riêng** (không ra cùng 1 câu cứng); voice thiếu mẫu → thông điệp rõ, không xoay mãi.
- [ ] 400 audio-invalid / audio-too-large / 401 / 404-preview / 503-asr hiện **đúng thông điệp** (503-asr ≠ "overloaded").
- [ ] Không còn nút "Thử âm thanh mẫu"; `transcribeSample`/fixture path đã gỡ; transcribe chỉ qua file thật.
- [ ] `error-map.test.ts` xanh.

## Risk Assessment
- **Rủi ro:** một số voice thật sự không có preview (VOICEVOX/Kokoro lazy) → 404 hợp lệ. **Tín hiệu:** 404 lần đầu. **Ứng phó:** BE preview on-demand tự synth (`previews.py:180-200`) — thông điệp "đang tạo mẫu" rồi thử lại, hoặc chấp nhận lần đầu chậm; không fallback câu cứng.
- **Rủi ro:** gỡ fixture làm vỡ test/visual đang dùng. **Tín hiệu:** import lỗi. **Ứng phó:** grep trước khi xoá; giữ fixture cho unit nếu cần.

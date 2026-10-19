---
phase: 2
title: "Phase 2: Frontend Engine & Voice Catalog Support"
status: complete
priority: P1
effort: "1h"
dependencies: [1]
---

# Phase 2: Frontend Engine & Voice Catalog Support

## Overview

Cập nhật kiểu dữ liệu TypeScript và các component giao diện trong `frontend/src/` để hỗ trợ engine `'capcut'`, hiển thị đúng nhãn mô hình **CapCut** trong bộ chọn model, và suy luận giới tính hợp lý cho 24 giọng Tiếng Việt của CapCut trên thẻ giọng đọc.

## Requirements

- [x] Mở rộng union type `Voice['engine']` trong `frontend/src/api/types.ts` và `VoiceItem['model']` trong `frontend/src/api/http-tts-api.ts` để bao gồm `'capcut'`.
- [x] Cập nhật `ModelSelect` (`frontend/src/features/compose/model-select.tsx`) để hiển thị nhãn `CapCut` và mô tả phù hợp thay vì rơi vào nhánh mặc định `'Kokoro'`.
- [x] Suy luận giới tính (`female` / `male` / `neutral`) cho các giọng CapCut trong `http-tts-api.ts` dựa trên `voice.id` (`_female_`, `_male_`, `HoaiMy`, `NamMinh`...) và tên hiển thị (`Nữ`, `Nam`, `Cô Gái`, `Nhỏ`, `Mai`, `Ban Mai`, `Đại Đế`...).
- [x] Kiểm tra các chỗ kiểm tra `engine` khác trên Frontend (`use-generate-subtitle.ts`, `voice-card.tsx`, `style-select.tsx`) để đảm bảo `capcut` hoạt động trơn tru (dùng ASR round-trip khi tạo phụ đề kèm giọng giống `vieneu`/`kokoro`).

## Architecture

- Khi Frontend gọi `GET /v1/voices`, 24 giọng `capcut` có `language: "vi"` và `model: "capcut"` sẽ tự động xuất hiện dưới tab ngôn ngữ **Tiếng Việt** (`vi`) và **Tất cả** (`all`).
- Trong `ModelSelect`, danh sách `engines` được gom động từ `voices.map(v => v.engine)`. Khi có `'capcut'`, dropdown hiển thị tùy chọn **CapCut** (`Giọng đọc đa dạng`).
- Khi người dùng chọn một giọng CapCut và bấm tạo phụ đề, `shouldUseNativeTiming('capcut', granularity)` trả về `false` → tự động đi qua luồng ASR `/v1/audio/transcriptions` chuẩn sẵn có.

## Related Code Files

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/http-tts-api.ts`
- Modify: `frontend/src/features/compose/model-select.tsx`
- Modify: `frontend/src/data/voice-fixtures.ts` (nếu cần cho mock/test)

## Implementation Steps

1. **Cập nhật `frontend/src/api/types.ts`**:
   - Đổi `engine: 'vieneu' | 'kokoro' | 'voicevox' | 'clone'` thành `engine: 'vieneu' | 'kokoro' | 'voicevox' | 'capcut' | 'clone'`.
2. **Cập nhật `frontend/src/api/http-tts-api.ts`**:
   - Cập nhật `VoiceItem.model` và `voiceCache` value type thêm `'capcut'`.
   - Bổ sung suy luận `gender` cho giọng `capcut` (ví dụ kiểm tra `item.id` chứa `female` / `HoaiMy` hoặc tên chứa `Nữ` / `Cô Gái` / `Nhỏ` / `Mai` → `'female'`; `item.id` chứa `male` / `NamMinh` hoặc tên chứa `Nam` / `Đại Đế` → `'male'`).
3. **Cập nhật `frontend/src/features/compose/model-select.tsx`**:
   - Thay chuỗi ternary cứng bằng bảng ánh xạ rõ ràng cho `'vieneu'`, `'capcut'`, `'voicevox'`, `'kokoro'`, `'clone'`.

## Todo

- [x] Thêm `'capcut'` vào `frontend/src/api/types.ts`
- [x] Cập nhật `frontend/src/api/http-tts-api.ts` (type + nhận diện giới tính giọng CapCut)
- [x] Cập nhật `frontend/src/features/compose/model-select.tsx` hiển thị tên & mô tả cho `capcut`

## Success Criteria

- [x] `pnpm --dir frontend typecheck` (hoặc `pnpm --dir frontend build`) không báo lỗi TypeScript.
- [x] `ModelSelect` hiển thị đúng tên `CapCut` khi có giọng `model="capcut"`.
- [x] Người dùng chọn giọng CapCut có thể bấm "Nghe thử", "Tạo giọng nói" và "Tạo kèm phụ đề".

## Risk Assessment

- **Xung đột `voiceCache` theo `voice.id`**: Các `voice_type` của CapCut (`BV421_vivn_streaming`, `vi_female_huong`, `multi_female_...`) hoàn toàn khác biệt với ID của `vieneu`, `kokoro` (`af_...`), `voicevox` (`0`, `1`...), nên không xảy ra đè key trong `voiceCache`.

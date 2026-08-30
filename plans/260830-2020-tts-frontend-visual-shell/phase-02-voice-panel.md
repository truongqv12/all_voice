---
title: "Phase 2: Voice Panel (mock)"
status: todo
---

# Phase 2: Voice Panel (mock data)

## Overview
Dựng khu **chọn giọng**: filter (ngôn ngữ/model → giới tính/nhóm → search), lưới voice card, nghe thử single-instance, chip "giọng đang chọn"; kèm state skeleton/empty/error. Mobile: bottom-sheet.

## Requirements
- Functional: lọc voices theo `model`/`language`/gender + text search; card hiện tên + tag (ngôn ngữ·giới tính·style); **nghe thử** toggle play/pause, chỉ 1 preview phát cùng lúc; chọn giọng → cập nhật `SelectedVoiceChip`.
- Non-functional: lưới scannable, không dày đặc; mobile-first (bottom-sheet); loading skeleton thay vì trắng; empty/error có copy + hành động.

## Architecture
- Dữ liệu qua `useTtsApi().listVoices()` (mock, có latency giả để thấy skeleton). Lọc client-side bằng `useVoiceFilters` (memo). Model = engine = ngôn ngữ (vieneu/kokoro/voicevox) → **1 hàng chip ngôn ngữ**, không tách 2 filter.
- `useVoicePreview`: 1 `Audio` singleton; bấm card đang phát → pause; bấm card khác → chuyển. `getPreviewUrl(voice)` (mock trả sample mp3). Trạng thái icon: idle→loading→playing.
- Chọn giọng nâng lên state cha (App/store nhẹ) để phase 3 dùng; `styles` của giọng feed `StyleSelect` (phase 3).
- Mobile: `VoicePanel` render inline ở `lg:`; ở mobile mở qua `BottomSheet` từ `SelectedVoiceChip` trong compose.

## Related Code Files
- Create: `frontend/src/features/voice/voice-panel.tsx`, `voice-filter-bar.tsx`, `voice-grid.tsx`, `voice-card.tsx`, `voice-preview-button.tsx`, `selected-voice-chip.tsx`
- Create: `frontend/src/features/voice/use-voice-filters.ts`, `use-voice-preview.ts`
- Create: `frontend/src/components/ui/skeleton.tsx`, `empty-state.tsx`, `bottom-sheet.tsx` (Radix Dialog)
- Create: `frontend/src/store/selection.ts` (state giọng/model/style đang chọn — context nhẹ hoặc zustand tối giản)
- Modify: `frontend/src/features/tts/tts-page.tsx` (mount VoicePanel vào slot phải / bottom-sheet), `frontend/src/i18n/locales/*` (chuỗi voice/filter)

## Implementation Steps
1. `use-voice-filters`: chuẩn hoá voices → nhóm theo ngôn ngữ/model; áp filter chip + search (bỏ dấu khi search VI).
2. `VoiceFilterBar`: chips ngôn ngữ (VI/EN/JP) → giới tính/nhóm → ô search + reset.
3. `VoiceCard` + `VoicePreviewButton`: layout card, tag, nút play tròn; state selected nổi bật (viền/nền accent nhạt).
4. `use-voice-preview`: singleton audio, toggle, dừng preview khác; loading khi buffering.
5. `VoiceGrid`: skeleton khi loading; empty ("không có giọng khớp" + reset); error (retry — mock toggle để demo).
6. `SelectedVoiceChip`: hiện tên + style; trên mobile là nút mở `BottomSheet` chứa cả filter+grid.
7. Nối state chọn giọng vào `store/selection`.

## Success Criteria
- [ ] Lọc theo ngôn ngữ/model/giới tính + search hoạt động; reset về đủ.
- [ ] Nghe thử toggle play/pause; mở giọng khác thì giọng cũ dừng (single-instance).
- [ ] Chọn giọng cập nhật chip + store; card selected nổi bật.
- [ ] Skeleton khi loading; empty & error demoable, có hành động.
- [ ] Mobile: bottom-sheet chọn giọng mượt; desktop: panel phải.

## Risk Assessment
- **Nghe thử chồng tiếng** nếu không singleton. Mitigation: 1 Audio dùng chung trong `use-voice-preview`; test bấm nhanh nhiều card.
- **Search tiếng Việt có dấu** không khớp. Mitigation: normalize (bỏ dấu, lower) cả query lẫn tên khi so.
- **Lưới quá dày trên mobile** → rối. Signal: card chật, chữ tràn. Response: 1 cột mobile / 2 cột md / 2-3 cột lg, giữ khoảng thở.

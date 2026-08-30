---
title: "Phase 6: Ancillary, i18n, a11y & polish"
status: todo
---

# Phase 6: Ancillary, i18n coverage, a11y & responsive polish

## Overview
Chạy **sau khi cả 3 khu tính năng đã dựng** (TTS · Speech-to-Text · Voice Cloning). Hoàn thiện các khu phụ trợ dùng chung (UsageGuide, DonateCard) + mọi UX state còn thiếu (giới hạn anon giả lập), phủ đủ chuỗi i18n VN/EN **trên toàn bộ 3 khu**, và **đánh bóng** a11y + responsive để đạt "đẹp, mạch lạc, không AI-slop".

## Requirements
- Functional: UsageGuide collapsible (mẹo chuẩn hoá text VN + 2-3 use-case); DonateCard (QR + BuyMeACoffee); state giới hạn anon giả lập (429 rate-limit, quota ngày, quá-dài) hiển thị tử tế; empty-first-load có copy hướng dẫn.
- Non-functional: 100% chuỗi qua i18n (không hard-code); a11y đạt checklist; responsive sạch 375/768/1024/1440; reduced-motion; không AI-slop.

## Architecture
- `UsageGuide`: Radix Collapsible; nội dung mẹo VN (viết số/ngày dạng chuẩn, tránh viết tắt) + use-case (video/sách nói/học phát âm) — đặt gần editor, không modal.
- `DonateCard`: ảnh QR (placeholder `assets/donate-qr.png`) + nút BuyMeACoffee (link đặt trong config); tĩnh, dismissible, không tiers, không chặn generate.
- **Limit states (mock)**: `lib/limits.ts` + một "demo states" switch (dev-only, ẩn) để trình diễn 429/quota/too-long; ErrorState inline gần nút + Toast (aria-live) cho thông báo tạm; copy giải thích + hướng khắc phục, **không** giọng "mua thêm credit".
- a11y sweep: focus ring mọi control, contrast ≥4.5 (kiểm cả dark), aria-label icon-only, keyboard nav (tab/enter/space), `prefers-reduced-motion` tắt pulse.
- Responsive sweep: kiểm 4 breakpoint; không cuộn ngang; safe-area; touch target ≥44px.

## Related Code Files
- Create: `frontend/src/features/guide/usage-guide.tsx`
- Create: `frontend/src/features/support/donate-card.tsx`
- Create: `frontend/src/features/status/limit-states.tsx`, `frontend/src/features/status/toast-region.tsx`
- Create: `frontend/src/components/ui/collapsible.tsx`
- Create: `frontend/src/config/app-config.ts` (link BMC, ảnh QR, cờ demo-states)
- Modify: `frontend/src/i18n/locales/vi.json`, `en.json` (phủ đủ chuỗi 3 khu), `frontend/src/components/layout/{app-shell,footer}.tsx` (DonateCard global) + `frontend/src/features/tts/tts-page.tsx` (UsageGuide gần editor), các component phase 1-5 (thay chuỗi cứng → i18n, vá a11y)

## Implementation Steps
1. `UsageGuide` (Collapsible) + nội dung mẹo VN/EN.
2. `DonateCard` (QR placeholder + BMC link) đặt cuối workspace + slot header nhẹ.
3. `limit-states` + `toast-region` (aria-live polite); nối demo switch để trình diễn 429/quota/too-long.
4. Empty-first-load: placeholder editor + gợi ý ("Dán văn bản, chọn giọng, bấm Tạo").
5. i18n sweep **toàn 3 khu** (TTS + Speech-to-Text + Voice Cloning + nav): rà tất cả chuỗi cứng → khoá i18n; kiểm cả 2 ngôn ngữ không vỡ layout.
6. a11y sweep **toàn 3 khu**: focus/contrast/aria/keyboard/reduced-motion (dùng checklist ak:ui-ux-pro-max); chú ý form cloning (consent) + panel export SRT/VTT.
7. Responsive sweep 375/768/1024/1440 + landscape trên cả 3 khu + nav; sửa tràn/cuộn ngang; safe-area; touch ≥44px.

## Success Criteria
- [ ] UsageGuide + DonateCard hiển thị nhẹ nhàng, không chặn; QR + BMC có mặt (placeholder).
- [ ] 429 / quota / quá-dài demoable với copy thân thiện VN/EN, có hướng khắc phục.
- [ ] 100% chuỗi qua i18n **trên cả 3 khu** (TTS/ASR/Cloning + nav); đổi VN/EN không vỡ layout.
- [ ] a11y **toàn 3 khu**: contrast ≥4.5 (light+dark), focus ring, keyboard nav, aria-label icon, reduced-motion.
- [ ] Không cuộn ngang ở 375/768/1024/1440 trên cả 3 khu; touch target ≥44px; không emoji làm icon.

## Risk Assessment
- **AI-slop lẻn vào** (gradient/glass/hero generic). Mitigation: bám tokens Swiss/flat, review trước phase 5; phase 5 vision sẽ bắt.
- **Chuỗi EN dài hơn VN gây tràn**. Signal: nút/nhãn vỡ ở EN. Response: dành chỗ cho chuỗi dài, test cả 2 ngôn ngữ.
- **Contrast dark mode fail**. Mitigation: kiểm riêng dark, không suy từ light.
- **Donate placeholder tưởng thật**. Mitigation: đánh dấu placeholder rõ; link/ảnh thật lấy từ user (open question).

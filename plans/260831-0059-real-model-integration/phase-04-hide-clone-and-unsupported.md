---
phase: 4
title: "Ẩn Cloning + affordance backend chưa hỗ trợ"
status: pending
priority: P1
effort: "0.5d"
dependencies: [1, 2]
---

# Phase 4: Ẩn Cloning + affordance backend chưa hỗ trợ

## Overview

Thực thi nguyên tắc **"cái gì backend chưa hỗ trợ (an toàn cho anon công khai) thì ẩn đi"** bằng **feature flag**, giữ toàn bộ code để bật lại khi có auth/scope-per-user. Ẩn: khu **Voice Cloning** (nav+route+picker group), filter **giới tính**, **mô tả** giọng, **speed** cho VieNeu, affordance **TTS→SRT**, và **format** BE không nhận.

Skills: `ak:frontend-development`, `ak:react-best-practices`, `ak:ui-ux-pro-max` (nav 2 khu vẫn cân đối, không để khoảng trống lạ).

## Requirements

- Functional:
  - `app-config.ts`: `features: { cloning: false, ttsToSrt: false }` (mở rộng khi cần). Đọc override từ `import.meta.env.VITE_FEATURE_CLONING` (tùy chọn, mặc định off).
  - **Cloning ẩn:** `feature-nav.tsx` bỏ mục Clone khi `!features.cloning`; `router.tsx` bỏ/redirect route `/clone` → `/` (deep-link an toàn, không 404 trắng); selection/voice-picker bỏ nhóm **"Giọng của bạn"** (clone) khi off. Code khu clone (`features/clone/*`, `http-clone-api.ts`) **giữ nguyên**, chỉ không mount.
  - **Filter giới tính ẩn:** `voice-filter-bar.tsx` + `use-voice-filters.ts` bỏ control + tiêu chí gender (BE `/v1/voices` không có `gender`).
  - **Mô tả giọng ẩn:** `voice-card.tsx` bỏ dòng `description` (BE thiếu) → fallback hiển thị `language · engine` (+ styles chips nếu có).
  - **Speed theo engine:** `synth-controls.tsx`/`speed-slider.tsx` ẩn slider speed khi engine giọng chọn = `vieneu` (BE bỏ qua speed); giữ cho engine khác.
  - **Style-select có điều kiện:** chỉ hiện khi giọng chọn có `styles.length > 0`.
  - **TTS→SRT ẩn:** affordance/nút trên `audio-result-card.tsx` bị ẩn khi `!features.ttsToSrt`.
  - **[Validation F2]** **Format-select = mp3 + wav** (bỏ `ogg`; `AudioFormat`='mp3'|'wav' đã thu hẹp ở phase 1).
- Non-functional: ẩn = không mount/không render (không chỉ `display:none`), để không gọi API chết; giữ i18n; a11y không còn control mồ côi; visual không lệch lưới 8px.

**[Validation detail-corrections — bám verification]:**
- `feature-nav.tsx:14` mobile nav hardcode `grid grid-cols-3` → **đổi `grid-cols-2`** (hoặc tính động theo số item) khi ẩn clone, tránh ô trống lệch lưới.
- `use-voice-filters.ts:10` search string ghép `voice.description` → **bỏ `description`** khỏi chuỗi tìm (chỉ `name` + `styles`) khi field bị bỏ.
- `synth-controls.tsx` hiện KHÔNG nhận engine → **truyền engine giọng đang chọn** vào `SynthControls`/`SpeedSlider` để gate speed theo engine (VieNeu ẩn speed).

## Architecture

- **Feature flag tập trung** ở `app-config.ts` (đã là `as const`) — thêm nhánh `features`. Component đọc `appConfig.features.*`. Đây là "công tắc ẩn" DRY: 1 chỗ bật lại khi có auth.
- **Router:** dùng loader/guard đơn giản — nếu `!features.cloning`, không khai báo route `/clone` (hoặc khai báo redirect `<Navigate to="/" replace />`). Ưu tiên **không khai báo** + 1 catch-all redirect để deep-link cũ không vỡ.
- **Voice mapping (từ phase 2):** `gender` luôn `'neutral'`, `description` `''` — nên UI phải **không phụ thuộc** 2 field này; phase này gỡ chỗ dùng chúng.

## Related Code Files

- Modify: `frontend/src/config/app-config.ts` (`features`)
- Modify: `frontend/src/components/layout/feature-nav.tsx` (ẩn nav Clone)
- Modify: `frontend/src/app/router.tsx` (bỏ/redirect `/clone`)
- Modify: `frontend/src/features/voice/voice-filter-bar.tsx`, `frontend/src/features/voice/use-voice-filters.ts` (bỏ gender)
- Modify: `frontend/src/features/voice/voice-card.tsx` (bỏ description, fallback)
- Modify: `frontend/src/features/compose/synth-controls.tsx`, `speed-slider.tsx`, `style-select.tsx`, `format-select.tsx` (speed theo engine, style/format có điều kiện)
- Modify: `frontend/src/features/compose/audio-result-card.tsx` (ẩn TTS→SRT)
- Modify: `frontend/src/store/selection.tsx` (bỏ nhóm clone ở picker khi off)
- Keep (không xoá): `frontend/src/features/clone/*`, `frontend/src/api/http-clone-api.ts`

## Implementation Steps

1. Thêm `features` vào `app-config.ts`.
2. Ẩn nav + route Clone (+ redirect deep-link).
3. Bỏ nhóm "Giọng của bạn" ở picker/selection khi off.
4. Bỏ filter gender + description; fallback voice-card.
5. Speed ẩn theo engine; style/format có điều kiện.
6. Ẩn affordance TTS→SRT.
7. Smoke: nav còn 2 khu, `/clone` redirect, TTS controls đúng theo engine, không control mồ côi; chạy cả mock lẫn http.

## Success Criteria

- [ ] Không có nav `/clone`; vào thẳng `/clone` → redirect `/` (không màn trắng).
- [ ] Picker giọng không có nhóm clone; filter **không** còn giới tính.
- [ ] Voice-card không mô tả rỗng; hiển thị `language · engine` gọn (+ styles nếu có).
- [ ] Chọn giọng VieNeu → **không** thấy slider speed; giọng khác vẫn có.
- [ ] Style-select chỉ hiện khi có styles; format-select chỉ liệt kê format BE nhận; **không** có nút TTS→SRT.
- [ ] Bật `features.cloning=true` (dev) → khu Clone hiện lại nguyên vẹn (chứng minh code còn sống).
- [ ] `npm run build` xanh; a11y không control mồ côi.

## Risk Assessment

- **Rủi ro:** ẩn quá tay làm mất tính năng hợp lệ (vd giọng non-VieNeu vẫn cần speed). **Tín hiệu:** người dùng mất control đáng có. **Ứng phó:** điều kiện ẩn bám **engine cụ thể**/`features` flag, không ẩn cứng toàn cục.
- **Rủi ro:** deep-link `/clone` được index/bookmark → 404. **Tín hiệu:** báo lỗi route. **Ứng phó:** catch-all `<Navigate to="/" replace />`.
- **Rủi ro:** flag rải rác nhiều component khó bật lại. **Tín hiệu:** bật cloning=true mà vẫn lỗi chỗ nào đó. **Ứng phó:** tập trung đọc `appConfig.features`; test bật/tắt ở phase 6.

---
title: "Phase 1: Scaffold, Tokens, Theme & i18n"
status: todo
---

# Phase 1: Scaffold, Design Tokens, Theme & i18n Foundation

## Overview
Dựng khung app `frontend/` chạy được: Vite+React+TS+**Tailwind v4**, design tokens, font Be Vietnam Pro, theme light/dark (no-FOUC + toggle + persist), i18n VN/EN, **định tuyến đa khu tính năng** (react-router-dom v7: `/` Text-to-Speech · `/transcribe` Speech-to-Text · `/clone` Voice Cloning), layout shell mobile-first (AppShell/Header nav 3 khu/Footer), bộ primitives, và **lớp mock API** (interface + fixtures) làm nền cho phase 2-6.

## Requirements
- Functional: app dev chạy; theme toggle nhớ + không nháy; ngôn ngữ VN/EN đổi toàn UI; shell hiển thị đúng ở mobile & desktop; mock `TtsApi` sẵn sàng inject.
- Non-functional: mobile-first; tokens tập trung (đổi 1 chỗ đổi toàn app); không AI-slop (không gradient/glass, 1 accent); a11y nền (focus ring, semantic, contrast).

## Architecture
- **Tokens (Tailwind v4, CSS-first)**: khai báo tokens bằng `@theme { --color-*, --radius-*, --shadow-*, --font-*, --spacing … }` trong CSS entry (không cần `tailwind.config.ts`; dùng plugin `@tailwindcss/vite`). Màu theme-aware qua biến CSS ở `:root` / `.dark` (map vào `@theme` để sinh utility). Palette: bg `#F8FAFC`, surface `#FFFFFF`, border `#E2E8F0`, text `#0F172A`/muted `#475569`, primary `#4F46E5`/hover `#4338CA`, success `#059669`, warning `#D97706`, danger `#DC2626`; dark: bg `#0F172A`, surface `#1E293B`, text `#F1F5F9`, primary `#818CF8`. Spacing 4/8, radius, shadow 1 cấp.
- **Theme no-FOUC**: inline `<script>` đồng bộ trong `<head>` đọc `localStorage.theme` → fallback `matchMedia('(prefers-color-scheme: dark)')` → gắn class `dark` lên `<html>` **trước paint**. `ThemeProvider` + `useTheme` chỉ flip class + ghi localStorage. Dark-variant Tailwind v4: `@custom-variant dark (&:where(.dark, .dark *));` (class-based, không dùng `darkMode:'class'` của v3).
- **i18n**: `react-i18next` + `i18next-browser-languagedetector` (thứ tự: localStorage → navigator.language → 'vi'); catalog phẳng `vi.json`/`en.json`; hook `useTranslation`. Ngôn ngữ **giao diện** ≠ ngôn ngữ giọng đọc.
- **Font**: `@fontsource/be-vietnam-pro` (400/500/600/700) import ở entry; số dùng `font-variant-numeric: tabular-nums`.
- **Mock API layer**: `TtsApi` interface (`listVoices`, `getPreviewUrl`, `synth`, `synthStream`) + `mockTtsApi` (fixtures + latency giả); `ApiProvider`/`useTtsApi` context để component chỉ biết interface.
- **Routing đa khu**: `react-router-dom v7` (`createBrowserRouter`) với `AppShell` là layout gốc + 3 route con: `/` (Text-to-Speech, phase 2-3), `/transcribe` (Speech-to-Text, phase 4), `/clone` (Voice Cloning, phase 5). Deep-linkable (chia sẻ URL), back-button chuẩn. Phase 1 dựng route + màn placeholder rỗng cho mỗi khu; feature thật đắp vào ở phase sau. `React.lazy` mỗi route để tách bundle.
- **Header nav**: 3 mục (icon+label) với **active state** rõ (`NavLink` isActive); desktop = nav ngang trong header; mobile = bottom-bar hoặc menu gọn (≤5 mục, theo rule nav). Badge ngôn ngữ giọng + Mẹo + Ủng hộ + theme/lang toggle vẫn ở header.
- **Layout mobile-first (route TTS)**: base = 1 cột; `lg:` = 2 vùng (compose | voice). `AppShell` giữ header sticky mỏng + `<Outlet/>` + footer; dùng `min-h-dvh`.

## Related Code Files
- Create: `frontend/package.json`, `frontend/vite.config.ts` (plugin `@tailwindcss/vite` + react), `frontend/tsconfig.json`, `frontend/index.html` (kèm no-FOUC script), `frontend/.gitignore` — **Tailwind v4 CSS-first: KHÔNG cần `tailwind.config.ts` / `postcss.config.js`** (tokens khai trong CSS `@theme`)
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/tokens.css` (`@import "tailwindcss"` + `@custom-variant dark` + `@theme`), `frontend/src/styles/global.css`
- Create: `frontend/src/app/router.tsx` (createBrowserRouter: `/` TTS · `/transcribe` ASR · `/clone` Cloning; lazy mỗi route); route element: `frontend/src/features/tts/tts-page.tsx` (layout 2 slot compose|voice — đắp ở phase 2-3), placeholder `frontend/src/features/transcribe/transcribe-page.tsx`, `frontend/src/features/clone/clone-page.tsx` (rỗng ở phase 1)
- Create: `frontend/src/theme/theme-provider.tsx`, `frontend/src/theme/use-theme.ts`
- Create: `frontend/src/i18n/index.ts`, `frontend/src/i18n/locales/vi.json`, `frontend/src/i18n/locales/en.json`
- Create: `frontend/src/components/layout/app-shell.tsx` (Outlet), `header.tsx` (nav 3 khu), `footer.tsx`, `frontend/src/components/layout/feature-nav.tsx` (NavLink active-state; desktop ngang / mobile bottom-bar)
- Create: `frontend/src/components/ui/button.tsx`, `icon-button.tsx`, `chip.tsx`, `slider.tsx`, `tooltip.tsx`, `toast.tsx`, `theme-toggle.tsx`, `language-toggle.tsx`
- Create: `frontend/src/api/types.ts`, `tts-api.ts`, `mock-tts-api.ts`, `api-context.tsx`
- Create: `frontend/src/data/voice-fixtures.ts`, `frontend/src/assets/` (sample mp3 mock, QR placeholder)
- Create: `frontend/design-system/MASTER.md` (sinh bằng `ak:ui-ux-pro-max --design-system --persist` — nguồn token/quy tắc cho cook)
- Modify: none (giữ `web/` nguyên trạng)

## Implementation Steps
1. Scaffold Vite React-TS trong `frontend/` (**bản stable mới nhất**, web-search doc khi cần); đặt dev server **port 5273 `strictPort`** (tránh đụng backend 8123/8124, không auto-increment); cài **Tailwind v4** qua `@tailwindcss/vite` (không PostCSS); CSS entry `@import "tailwindcss"` + `@custom-variant dark (&:where(.dark, .dark *))` + `@theme` tokens.
2. Thêm no-FOUC theme script vào `index.html <head>`; viết `ThemeProvider`/`useTheme` + `ThemeToggle`.
3. Cài i18n (react-i18next + language-detector); tạo catalog `vi/en` khởi điểm; `LanguageToggle`.
4. Import Be Vietnam Pro (@fontsource); set type scale + tabular-nums.
5. Dựng primitives UI (Button/IconButton/Chip/Slider(Radix)/Tooltip/Toast) đúng tokens + trạng thái hover/press/focus/disabled.
6. Cài `react-router-dom v7`; dựng `router.tsx` (AppShell layout + 3 route `/` · `/transcribe` · `/clone`, lazy) + `FeatureNav` (NavLink active-state, desktop ngang / mobile bottom-bar ≤5 mục); màn placeholder rỗng cho 3 route.
7. Dựng `AppShell/Header/Footer` mobile-first (header: tên app · **FeatureNav** · badge ngôn ngữ giọng · Mẹo · Ủng hộ · theme/lang toggle; `<Outlet/>` cho route).
8. Định nghĩa `types.ts` (Voice, SynthParams, SynthResult, Tier…) + `TtsApi` + `mockTtsApi` + `ApiProvider`; seed `voice-fixtures` (VI VieNeu nhiều style, EN Kokoro US/UK, JP VOICEVOX).
9. Ráp `App` = ApiProvider→Theme→i18n→RouterProvider(AppShell) với route TTS chứa 2 slot rỗng (compose/voice), route `/transcribe` + `/clone` placeholder.
10. Sinh design system nền: `ak:ui-ux-pro-max --design-system --persist` → `frontend/design-system/MASTER.md`. Áp **`ak:react-best-practices`** xuyên suốt: functional component + typed props, rules-of-hooks, memo/`useCallback` **chỉ khi đo có lợi**, tách concern, TS strict, tránh re-render thừa.

## Success Criteria
- [ ] `npm run dev` chạy; shell render đúng mobile 375px và desktop; không cuộn ngang.
- [ ] Theme toggle đổi light/dark, **không nháy** khi reload, nhớ lựa chọn (Tailwind v4 `@custom-variant dark`).
- [ ] Language toggle đổi VN/EN toàn bộ chuỗi shell; mặc định VN; tự nhận trình duyệt.
- [ ] **Nav 3 khu** (`/` · `/transcribe` · `/clone`) điều hướng được, deep-link mở đúng route, active-state rõ, back-button chuẩn; mobile nav gọn.
- [ ] Tokens + font áp dụng nhất quán; primitives có đủ state hover/press/focus/disabled.
- [ ] `mockTtsApi.listVoices()` trả fixtures VI/EN/JP; `ApiProvider` inject được.

## Risk Assessment
- **Tailwind v4 (mới, CSS-first)**: cú pháp khác v3 (`@theme`, `@custom-variant`, plugin `@tailwindcss/vite` thay PostCSS). Signal nếu sai: utility/dark không sinh ra. Response: web-search doc Tailwind v4 hiện hành khi setup; giữ tokens tập trung trong 1 file CSS để đổi 1 chỗ.
- **No-FOUC script sai vị trí** → nháy theme. Signal: thấy flash khi reload. Response: đảm bảo script **đồng bộ, đặt trước** mọi stylesheet trong `<head>`.
- **Client-side routing + static host**: SPA cần fallback `try_files → index.html` khi deploy (giai đoạn tích hợp). Signal: refresh `/transcribe` ra 404 trên host tĩnh. Response: dev/preview Vite tự lo; ghi chú cấu hình nginx cho integration-stage (không thuộc plan này).
- **i18n lẫn trục ngôn ngữ** (UI vs giọng đọc). Mitigation: đặt tên khoá rõ (`ui.*` vs `voice.language`), tài liệu ngắn trong `i18n/index.ts`.

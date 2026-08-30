---
title: "TTS Frontend — Standalone Visual Shell (mock-first, mobile-first, multi-feature)"
description: "Bộ source FE độc lập (chưa tích hợp backend), mock data, mobile-first, dark/light + i18n VN/EN, đa khu (TTS · Speech-to-Text + xuất SRT/VTT/TXT · Voice Cloning), kết thúc bằng E2E screenshot + vision review thẩm mỹ."
status: done
priority: P1
effort: "6-9d"
tags: [frontend, ui-ux, react, vite, tailwind-v4, react-router, mock, mobile-first, i18n, asr, subtitles, voice-cloning, e2e, visual-qa]
created: 2026-08-30
---

# TTS Frontend — Standalone Visual Shell (multi-feature)

## Overview

Giai đoạn 1 của web `all_voice`: dựng **bộ source frontend độc lập, CHƯA tích hợp backend**, chạy hoàn toàn bằng **mock data** để **soi thẩm mỹ trước** — đẹp/không, rối/không, có "AI-slop" không. Theo câu chốt **"làm hết"**, shell dựng **đủ 3 khu tính năng**: **Text-to-Speech**, **Speech-to-Text** (kèm **xuất phụ đề SRT/VTT/TXT**), **Voice Cloning** (consent-first). Tích hợp API thật để **giai đoạn sau** (chỉ swap lớp adapter `mock → http`, không đụng UI). Xuyên suốt **mobile-first**. Kết thúc bằng **phase E2E**: Playwright chụp ảnh (breakpoints × light/dark × states, cả 3 khu) rồi gọi **`agy` (Antigravity) vision** chấm điểm thẩm mỹ + phát hiện AI-slop, xuất report.

Nền tảng đã chốt (brainstorm + research): React + Vite + TypeScript + **Tailwind v4** + **react-router-dom v7**, Be Vietnam Pro, Swiss/flat single-accent indigo, Radix (a11y) + Lucide. Kiến trúc deploy "giấu API" (nginx sẵn có) là việc của **giai đoạn tích hợp**. Nghiên cứu xuất phụ đề: `plans/reports/research-260830-srt-subtitle-export.md`.

## Contract

- **Outcome:** một SPA static độc lập trong `frontend/`, mobile-first, dark/light + i18n VN/EN, **định tuyến 3 khu** (TTS · Speech-to-Text · Voice Cloning) với mọi UX state, chạy bằng mock adapter, đủ đẹp/mạch lạc để review trực quan; khép lại bằng E2E screenshot + vision review.
- **Constraints:** không gọi backend thật (mock adapter; đổi sang thật sau chỉ bằng lớp `http*`); mobile-first; **Tailwind v4** (CSS-first, `@custom-variant dark`); design tokens theo brief; **không AI-slop** (không gradient/glass; Swiss/flat; Be Vietnam Pro; 1 accent); a11y (contrast ≥4.5, focus, keyboard, reduced-motion, deep-link); **cloning consent-first**; xuất phụ đề cắt cue theo **chuẩn** (chunk chạy thật client-side); build static; giữ `web/index.html` **nguyên trạng** giai đoạn này.
- **Non-goals (plan này):** tích hợp API/proxy/nginx thật; streaming MSE thật (chỉ giả lập progress+player); **synth / transcribe / clone THẬT** (mock hết); **auth/consent enforcement thật** (cloning chỉ dựng UI); **TTS→SRT verbatim** (đã nghiên cứu — follow-on backend; chỉ affordance mock trên result-card TTS); server-side SRT generation; tài khoản/history server; xoá `web/index.html` (integration-stage).
- **Acceptance:** xem "Success Criteria" cuối file.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | FE độc lập chạy bằng mock, mobile-first, dark/light + VN/EN, **routing 3 khu** | P1 |
| 2 | Khu **TTS**: voice filter/preview/select + compose/generate/progress/result | P1 |
| 3 | Khu **Speech-to-Text**: upload → transcript → **xuất SRT/VTT/TXT** (chunk chuẩn client-side) | P1 |
| 4 | Khu **Voice Cloning**: enrol form **consent-first** → clone list (mock) | P1 |
| 5 | Mọi UX state (empty/loading/error/success + giới hạn anon giả lập) trên cả 3 khu | P1 |
| 6 | Thẩm mỹ đạt: rõ ràng, hiện đại, không rối, **không AI-slop** | P1 |
| 7 | E2E chụp ảnh + `agy` vision review chấm điểm thẩm mỹ, xuất report | P1 |

## Phases

| # | Phase | Status | Depends |
|---|-------|--------|---------|
| 1 | [Scaffold, Tokens, Theme, i18n, Routing & Nav](./phase-01-start.md) | Done | — |
| 2 | [Voice Panel (mock)](./phase-02-voice-panel.md) | Done | 1 |
| 3 | [Compose Panel + mock generate](./phase-03-compose-panel.md) | Done | 1, 2 |
| 4 | [Speech-to-Text (mock) + subtitle export](./phase-04-asr.md) | Done | 1 |
| 5 | [Voice Cloning (mock, consent-first)](./phase-05-cloning.md) | Done | 1, 2 |
| 6 | [Ancillary, i18n, a11y & polish (toàn 3 khu)](./phase-06-ancillary-and-polish.md) | Done | 2, 3, 4, 5 |
| 7 | [E2E Visual QA + Vision Review](./phase-07-e2e-visual-qa.md) | Done | 6 |

## Architecture (tổng thể)

```
frontend/  (SPA static, độc lập — KHÔNG đụng app/ Python)
├─ index.html            # no-FOUC theme script trong <head>
├─ vite.config.ts        # plugin @tailwindcss/vite + react
├─ src/
│  ├─ styles/            # tokens.css (@import "tailwindcss" + @custom-variant dark + @theme)
│  ├─ app/               # router.tsx (3 route, lazy)
│  ├─ api/               # types + TtsApi + transcribe-api + clone-api (+ mock*)  ← đổi mock→http sau ở đây
│  ├─ data/              # voice-fixtures, transcript-fixture, clone-fixtures, 1 sample audio (mock chung)
│  ├─ theme/             # theme provider (light/dark, persist), no-FOUC
│  ├─ i18n/              # react-i18next + catalog vi.json/en.json
│  ├─ lib/subtitle/      # chunk-cues + to-srt/to-vtt/to-txt + conventions (chạy THẬT client-side)
│  ├─ components/ui/     # primitives (Button, Chip, Slider, Tooltip, Toast, Skeleton, BottomSheet…)
│  ├─ components/layout/ # AppShell(Outlet), Header, FeatureNav (active-state), Footer
│  ├─ features/voice/    # (TTS) VoicePanel + filter/grid/card/preview/selected-chip
│  ├─ features/compose/  # (TTS) ComposePanel + editor/upload/controls/generate/progress/result
│  ├─ features/transcribe/ # (ASR) drop-zone/transcript/subtitle-export
│  ├─ features/clone/    # (Cloning) enrol-form/consent/sample/clones-list/auth-gate
│  ├─ features/guide/    # UsageGuide
│  └─ features/support/  # DonateCard (QR + BuyMeACoffee)
└─ e2e/                  # Playwright capture + vision-review (phase 7)
```

**Nguyên tắc DRY tách backend:** UI chỉ phụ thuộc các interface (`TtsApi`, `transcribe-api`, `clone-api`). Giai đoạn này inject bản `mock*`; tích hợp thật = thêm `http*` gọi same-origin `/api` và swap ở provider — **0 thay đổi** ở component. Riêng bộ **chunk phụ đề client-side** giữ nguyên khi tích hợp (backend `to_srt`/`to_vtt` hiện chỉ segment-level).

## Key decisions (đã chốt)

- Stack: **Vite + React 18 + TypeScript + Tailwind v4** (CSS-first: `@import "tailwindcss"`, `@theme`, `@custom-variant dark (&:where(.dark, .dark *))`, plugin `@tailwindcss/vite` — không PostCSS/`tailwind.config.ts`) + **react-router-dom v7** (deep-link 3 khu) + Radix + Lucide + **react-i18next** + `i18next-browser-languagedetector`.
- Font: **Be Vietnam Pro** self-host qua `@fontsource` (offline, chuẩn dấu tiếng Việt).
- Style: Swiss/flat, grid 8px, **single-accent indigo `#4F46E5`** trên `#F8FAFC`; dark = slate-950/indigo-400. Không gradient/glass.
- Vị trí: thư mục **`frontend/`** ở gốc repo; **giữ `web/index.html`** giai đoạn này.
- Donate: **QR (ảnh) + BuyMeACoffee (link)** — tĩnh, không modal, không tiers.
- Mock preview/generate: **1 file mp3 mẫu CHUNG cho mọi giọng** (đủ để review hình thức; đánh dấu rõ là mock).
- **Xuất phụ đề (ASR):** SRT/VTT/TXT dựng **client-side** (`subsrt-ts` + `chunk-cues` theo chuẩn ≤42 ký tự/dòng, ≤2 dòng/cue, CPS/min-max). **TTS→SRT verbatim:** follow-on backend (VOICEVOX-native trước; Kokoro/VieNeu chờ chốt verbatim-vs-ASR) — **không build**, chỉ affordance mock.
- Cloning: **consent-first** (đồng ý bắt buộc để submit); auth/enforcement thật = integration-stage.
- **Bản mới nhất + doc hiện hành:** dùng phiên bản **stable mới nhất** và **web-search doc** (Vite/React/Tailwind v4/react-router/Playwright/react-i18next/Radix/subsrt-ts).

## Skills áp dụng (nhúng vào từng phase)

| Skill | Dùng ở | Việc |
|---|---|---|
| `ak:ui-ux-pro-max` | Phase 1, 6 | Chốt design system + tokens (`--design-system --persist` → `frontend/design-system/MASTER.md`); checklist a11y/visual pre-delivery |
| `ak:react-best-practices` | Phase 1-6 | Chuẩn React: functional component + typed props, đúng rules-of-hooks, memo/`useCallback` **chỉ khi đo có lợi**, tách concern, error boundary, `React.lazy` theo route, TS strict; tránh re-render thừa |
| `ak:web-testing` | Phase 7 | Playwright: capture ma trận 3 khu, chờ `fonts.ready`/network-idle, ép reduced-motion, cross-viewport |
| **`agy` (Antigravity)** | Phase 7 | **Vision review chính** — `agy --add-dir <thư-mục-ảnh> -p '<rubric>' --output-format json`. Fallback: `ak:ai-multimodal` (Multix) |
| `ak:frontend-development` | Phase 1-5 | Patterns React/TS khi dựng component |

## Ports (cố định, tránh đụng backend)

Backend chiếm **8123** (nginx) + **8124** (API). FE dùng port **riêng, cố định, `strictPort`** (không auto-increment — theo rule process-management):

- **Dev server (tự soi):** `http://localhost:5273` — `vite --port 5273 --strictPort`.
- **E2E preview (Phase 7):** `http://localhost:4273` — `vite preview --port 4273 --strictPort`.

Mỗi phase khi chạy để bạn kiểm tra sẽ mở đúng **:5273**; dừng server cũ trước khi mở lại (không chồng tiến trình).

## Success Criteria (Acceptance)

- [x] `cd frontend && npm i && npm run dev` chạy, render **mobile (375px) + desktop** không lỗi, **không cuộn ngang** ở 375/768/1024/1440.
- [x] Toggle **theme** light/dark mượt, **không FOUC**, nhớ lựa chọn (Tailwind v4 `@custom-variant dark`).
- [x] Toggle **ngôn ngữ giao diện** VN/EN đổi toàn bộ chuỗi (cả 3 khu); mặc định VN, tự nhận trình duyệt.
- [x] **Nav 3 khu** (`/` · `/transcribe` · `/clone`) điều hướng + deep-link + active-state + back-button chuẩn; mobile nav gọn.
- [x] **TTS**: lọc giọng theo ngôn ngữ/model/giới tính + search; **nghe thử** single-instance; chọn giọng cập nhật chip; nhập/thả `.txt` + char counter; controls (model/style/speed/format); **Tạo → progress → player + Download + Tạo lại**; text dài → "stream-mode" progress.
- [x] **Speech-to-Text**: thả audio → transcript (segment + timestamp); **xuất SRT/VTT/TXT đúng chuẩn** + Copy; đổi options (chars/line, lines/cue, granularity) đổi output; chunk chuẩn (kiểm bằng unit-test).
- [x] **Voice Cloning**: enrol form **consent bắt buộc** + mẫu → Tạo (mock) → clone vào list; xoá có confirm; `AuthGate` demo chưa/đã đăng nhập; clone hiện ở voice picker TTS (nhóm "Giọng của bạn").
- [x] Mọi UX state demoable, gồm **giới hạn anon giả lập** (429/quota/quá-dài) với copy thân thiện VN/EN.
- [x] UsageGuide + DonateCard (QR + BMC) hiển thị nhẹ nhàng, không chặn.
- [x] a11y: contrast ≥4.5, focus ring, keyboard nav, `prefers-reduced-motion`; không emoji làm icon; form cloning + panel export dùng bàn phím được.
- [x] **Phase 7**: Playwright chụp đủ ma trận (state cốt lõi 3 khu × 4 breakpoint × 2 theme); **`agy` vision** chạy + xuất **report chấm điểm** vào `plans/reports/`.

## Validation Log

**Verification pass (2026-08-30) — 0 failures:**
- Toolchain: Node **v22.23.1**, npm **10.9.8**, `npx` có; `agy`, `ak`, `python3` trên PATH.
- Greenfield: `frontend/` **chưa tồn tại** (không xung đột); `web/index.html` giữ nguyên.
- Ports free: **5273** (dev) + **4273** (preview) trống; backend giữ 8123/8124.

**Câu hỏi validate — đã chốt (3):**
1. **Tailwind → v4 (mới nhất)** — chuyển từ v3; dark-variant dùng `@custom-variant dark`, tokens CSS-first `@theme`, plugin `@tailwindcss/vite`. Đã lan sang plan + phase-01.
2. **Phạm vi shell → "làm hết"** — mở từ core-TTS sang **đa khu**: thêm **Speech-to-Text (phase 4)** + **Voice Cloning (phase 5)** + **routing/nav (phase 1)**. Cấu trúc phase: 5→**7**; ancillary 4→6; e2e 5→7. Mong muốn tương lai **xuất SRT sub** → đã **nghiên cứu** (báo cáo `plans/reports/research-260830-srt-subtitle-export.md`): ASR→SRT khả thi (chunk client-side, làm trong phase 4); **TTS→SRT verbatim = follow-on backend** (chỉ affordance mock).
3. **Audio mock → 1 mẫu chung cho mọi giọng** — đã ghi ở Key decisions.

**Whole-plan consistency:** phase 1-7 tuần tự đúng thứ tự dependency; polish (6) sau khi cả 3 khu dựng xong; e2e (7) chụp cả 3 khu. Không còn mâu thuẫn "core TTS only" (đã thay bằng multi-feature).

## Run cadence (goal-warmup 2026-08-30)

Long-run cook cả 7 phase, nhưng **có checkpoint vision giữa chừng**:

- **Git:** nhánh `feat/tts-frontend-visual-shell` (plan đã commit trước khi cook).
- **Vision-fix LOOP (tự sửa — dùng ở checkpoint phase-3 và phase-7):** `capture` ma trận đa thiết bị (375/768/1024/1440 × light/dark) → **`agy` vision** trả findings (severity + vị trí + đề xuất) → **TỰ SỬA** finding nghiêm trọng (AI-slop / vỡ layout / contrast fail / cuộn ngang / rối / touch-target) → **re-capture → re-review** → lặp tới **hội tụ** (không còn finding nghiêm trọng) hoặc chạm **trần 4 vòng**. Mỗi vòng ghi `plans/reports/visual-review-*.md` (điểm + finding + ảnh + diff đã sửa).
- **Checkpoint sau phase 3:** chạy vision-fix loop trên **subset harness (Playwright) của phase 7** cho **shell + TTS core** — bắt lỗi design sớm (rẻ hơn trước khi ASR/Cloning đắp lên cùng design-language). Hội tụ → **tự tiếp phase 4-7**; nếu quá 4 vòng chưa sạch → **dừng, báo user** finding còn lại.
- **Phase 7:** chạy vision-fix loop trên **đủ 3 khu** (cổng cuối); hội tụ → verdict "đẹp"; còn finding sau trần → liệt kê rõ cho user.
- **Scope guard:** ở mỗi ranh giới phase, đối chiếu việc làm với Contract; lệch vật chất → dừng hỏi user; không kết thúc dưới scope; không làm yếu test để đạt điều kiện dừng.

## Open questions

1. ~~Tailwind v3 vs v4~~ — **CHỐT v4**.
2. ~~CLI vision~~ — **CHỐT `agy` (Antigravity)**; fallback `ak:ai-multimodal`.
3. ~~Audio mock 1 vs nhiều~~ — **CHỐT 1 mẫu chung**.
4. **Donate asset** — cần bạn cung cấp **ảnh QR thật** + **link BuyMeACoffee** (giai đoạn này để placeholder).
5. **TTS→SRT (tương lai, không chặn plan này):** caption **phải verbatim** theo text nhập, hay **ASR-recovered chấp nhận được**? VOICEVOX-native làm trước; Kokoro/VieNeu chờ quyết định này (xem research). Không build ở plan này.
6. **Deferred sang integration:** auth/consent thật cho cloning; đường `/api` vs `/v1`; SPA fallback `try_files` trên nginx; xoá `web/index.html`.

<!-- slug: tts-frontend-visual-shell -->

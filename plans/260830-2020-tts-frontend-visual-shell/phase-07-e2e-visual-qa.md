---
title: "Phase 7: E2E Visual QA + Vision Review"
status: todo
---

# Phase 7: E2E Visual QA + Vision Aesthetic Review

## Overview
Phase khép lại: Playwright build+serve FE, chụp ảnh ma trận (breakpoints × light/dark × states) **trên cả 3 khu tính năng (TTS · Speech-to-Text · Voice Cloning)**, rồi gọi **CLI vision** soi ảnh chấm điểm thẩm mỹ + phát hiện AI-slop, xuất **report** vào `plans/reports/`. Đây là cổng "đẹp/không rối/không slop" người dùng yêu cầu.

## Requirements
- Functional: chụp screenshot tự động cho ma trận đầy đủ; feed ảnh vào vision model qua CLI với rubric; sinh report chấm điểm + findings; ảnh lưu để người dùng tự xem.
- Non-functional: chạy trên **build production** (`vite build` + preview) chứ không dev; deterministic (chờ font/animation settle, tắt animation khi chụp để ổn định); không cài browser Playwright lên box prod (chỉ dev/CI — theo `docs/deployment.md`).

## Architecture
- **Capture (Playwright)**: `vite build` → `vite preview` (cổng cố định) → spec điều hướng tới từng state, set viewport + theme, `page.screenshot` full-page.
- **Ma trận**:
  - Breakpoints: 375 (mobile), 768 (tablet), 1024, 1440.
  - Theme: light, dark.
  - States — **TTS**: (1) empty-first-load, (2) voice panel + filter, (3) voice preview playing, (4) đã chọn giọng + compose có text, (5) đang generate (progress), (6) result player, (7) lỗi/quota (429/too-long), (8) usage-guide mở, (9) donate.
  - States — **Speech-to-Text**: (10) upload prompt (empty), (11) đang transcribe (progress), (12) transcript + panel export (SRT/VTT/TXT), (13) lỗi định dạng/quá dài.
  - States — **Voice Cloning**: (14) enrol form (rỗng), (15) đã có mẫu + consent checkbox, (16) đang xử lý, (17) danh sách clone, (18) gate "cần đăng nhập/consent".
  - Nav/chrome: (19) header nav 3 khu + active state; (20) mobile nav (bottom-bar/menu).
  - Ưu tiên chụp state cốt lõi mỗi khu ở **mọi** breakpoint; state phụ chụp ở mobile + 1440.
  - Điều khiển state qua query param/`demo-states` switch (phase 4) để deterministic.
- **Vision review**: gom ảnh → gọi vision CLI với prompt rubric: *đẹp/hiện đại*, *rõ ràng/hierarchy*, *rối/lộn xộn*, *AI-slop tells* (gradient tím, glass neon, hero generic, emoji-icon, spacing lộn xộn), *mobile-first đúng*, *contrast/đọc được*. Chấm 1-5 mỗi tiêu chí/màn + nhận xét + đề xuất sửa.
  - **Tool chính**: **`agy` (Antigravity)** — agent CLI vision tốt (đã có trên PATH). Print-mode: `agy --add-dir frontend/e2e/__screenshots__ -p '<rubric>' --output-format json` (có thể `--json-schema <schema>` ép cấu trúc điểm; `--dangerously-skip-permissions` khi chạy tự động). Fallback: `ak:ai-multimodal` (Multix). Dùng **model/agent bản mới nhất**.
- **Report**: `plans/reports/visual-review-{YYMMDD-HHmm}.md` — bảng điểm theo màn/breakpoint/theme, top findings, ảnh tham chiếu (đường dẫn), verdict đẹp/cần sửa. Findings vòng lại phase 2-4 nếu cần.

## Related Code Files
- Create: `frontend/e2e/playwright.config.ts`, `frontend/e2e/capture.spec.ts`, `frontend/e2e/states.ts` (map state→URL/param), `frontend/e2e/README.md`
- Create: `frontend/package.json` scripts (`build`, `preview`, `e2e:capture`)
- Create: `scripts/visual-review/run-vision.sh` (gom ảnh + gọi vision CLI + prompt rubric), `scripts/visual-review/rubric.md`
- Output: `frontend/e2e/__screenshots__/` (ảnh), `plans/reports/visual-review-*.md` (report)
- Modify: `.gitignore` (bỏ qua ảnh nặng nếu cần)

## Implementation Steps
1. Cài Playwright (dev), `playwright.config.ts` (projects theo viewport, cổng preview).
2. `states.ts`: liệt kê state + cách đưa app về state đó (param/demo switch).
3. `capture.spec.ts`: loop viewport × theme × state → screenshot full-page; chờ font/animation settle; đặt tên `{state}__{bp}__{theme}.png`.
4. Script `run-vision.sh`: gom ảnh → gọi **`agy --add-dir <thư-mục-ảnh> -p "$(cat rubric.md)" --output-format json`** → thu JSON chấm điểm (fallback `ak:ai-multimodal`). Chạy `agy help` một lần để xác nhận cờ hiện hành.
5. Tổng hợp → `plans/reports/visual-review-*.md` (bảng điểm + findings + verdict + link ảnh).
6. Nếu có finding "slop/rối/contrast" → mở việc vòng lại phase 2-4; chụp lại; cập nhật report.

## Success Criteria
- [ ] `npm run e2e:capture` chụp đủ ma trận (state cốt lõi **của cả 3 khu TTS/ASR/Cloning** × 4 breakpoint × 2 theme) trên build production.
- [ ] Vision CLI chạy, sinh report chấm điểm 6 tiêu chí + nhận xét/đề xuất mỗi màn.
- [ ] Report `plans/reports/visual-review-*.md` có bảng điểm, top findings, verdict đẹp/cần-sửa, link ảnh.
- [ ] Không còn finding "AI-slop" nghiêm trọng; các finding còn lại được liệt kê rõ để xử lý.

## Risk Assessment
- **Screenshot flaky** (font/animation chưa settle). Mitigation: chờ `document.fonts.ready`, tắt animation lúc chụp (`prefers-reduced-motion` ép), chờ network idle.
- **Vision CLI**: đã chốt **`agy` (Antigravity)** (có sẵn PATH). Nếu lỗi permission khi chạy tự động: thêm `--dangerously-skip-permissions`; nếu lỗi khác: fallback `ak:ai-multimodal`.
- **Vision đánh giá chủ quan/nhiễu**. Mitigation: rubric cố định + chấm số + yêu cầu dẫn chứng cụ thể trên ảnh; người dùng là trọng tài cuối.
- **Ảnh nặng vào git**. Mitigation: gitignore ảnh, chỉ commit report; hoặc lưu ảnh ngoài repo.

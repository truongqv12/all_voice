---
title: "Phase 7: E2E Visual QA + Vision Review"
status: done
---

# Phase 7: E2E Visual QA + Vision Aesthetic Review

## Overview
Phase khép lại, chạy dạng **VÒNG LẶP TỰ SỬA bằng vision**: Playwright build+serve FE, chụp ảnh ma trận (breakpoints × light/dark × states) **trên cả 3 khu (TTS · Speech-to-Text · Voice Cloning)** → **`agy` vision** soi hết lỗi (chấm điểm thẩm mỹ + AI-slop + vỡ layout/contrast) → **tự sửa** finding nghiêm trọng → **re-capture → re-review** → lặp tới **hội tụ** (không còn finding nghiêm trọng) hoặc **trần 4 vòng**. Mỗi vòng xuất report vào `plans/reports/`. Đây là cổng "đẹp/không rối/không slop" người dùng yêu cầu — **agy soi hết lỗi, loop tự xử lý**.

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
- **Vision-fix loop (driver)**: `scripts/visual-review/loop.sh` (hoặc runner Node) điều phối vòng: (1) `e2e:capture` → (2) `agy` vision (`--json-schema` ép findings có `severity` ∈ {critical,major,minor} + `screen/bp/theme` + `suggestion`) → (3) lọc finding `severity≥major` (AI-slop/vỡ layout/contrast/cuộn ngang/rối/touch<44) ; rỗng → **hội tụ, thoát** → (4) áp sửa theo suggestion vào component khu liên quan → (5) re-capture + re-review. **Trần 4 vòng**; quá trần mà chưa sạch → thoát + liệt kê finding còn lại cho user (không tự nới trần).
- **Report**: `plans/reports/visual-review-{YYMMDD-HHmm}.md` — mỗi vòng 1 mục: bảng điểm theo màn/breakpoint/theme, findings (severity), sửa gì (diff/summary), verdict vòng đó; cuối cùng verdict tổng "đẹp/hội tụ" hoặc "còn N finding".

## Related Code Files
- Create: `frontend/e2e/playwright.config.ts`, `frontend/e2e/capture.spec.ts`, `frontend/e2e/states.ts` (map state→URL/param), `frontend/e2e/README.md`
- Create: `frontend/package.json` scripts (`build`, `preview`, `e2e:capture`)
- Create: `scripts/visual-review/loop.sh` (driver vòng lặp: capture→vision→sửa→re-check, trần 4 vòng), `scripts/visual-review/run-vision.sh` (gom ảnh + gọi `agy` + rubric), `scripts/visual-review/rubric.md`, `scripts/visual-review/findings.schema.json` (ép cấu trúc `agy --json-schema`)
- Output: `frontend/e2e/__screenshots__/` (ảnh), `plans/reports/visual-review-*.md` (report)
- Modify: `.gitignore` (bỏ qua ảnh nặng nếu cần)

## Implementation Steps
1. Cài Playwright (dev), `playwright.config.ts` (projects theo viewport, cổng preview).
2. `states.ts`: liệt kê state + cách đưa app về state đó (param/demo switch).
3. `capture.spec.ts`: loop viewport × theme × state → screenshot full-page; chờ font/animation settle; đặt tên `{state}__{bp}__{theme}.png`.
4. Script `run-vision.sh`: gom ảnh → gọi **`agy --add-dir <thư-mục-ảnh> -p "$(cat rubric.md)" --output-format json --json-schema findings.schema.json`** → thu JSON findings (severity + màn/bp/theme + suggestion); fallback `ak:ai-multimodal`. Chạy `agy help` một lần để xác nhận cờ hiện hành.
5. `loop.sh` (vòng lặp tự sửa): `for i in 1..4` → `e2e:capture` → `run-vision.sh` → nếu **0 finding `severity≥major`** thì **break (hội tụ)**; ngược lại áp sửa theo suggestion vào component khu liên quan → tiếp vòng. Ghi report mỗi vòng.
6. Sau loop: nếu hội tụ → verdict "đẹp"; nếu chạm trần 4 vòng còn finding → **dừng, liệt kê finding còn lại cho user** (không tự nới trần, không làm yếu rubric để "đạt").
7. Report tổng `plans/reports/visual-review-*.md`: các vòng + verdict cuối + link ảnh trước/sau.

## Success Criteria
- [x] `npm run e2e:capture` chụp đủ ma trận (state cốt lõi **của cả 3 khu TTS/ASR/Cloning** × 4 breakpoint × 2 theme) trên build production.
- [x] `loop.sh` chạy **vòng lặp tự sửa**: capture→`agy` vision→sửa→re-check, dừng khi **hội tụ** (0 finding `severity≥major`) hoặc **trần 4 vòng**.
- [x] `agy` vision chạy với `--json-schema` → findings có severity + màn/bp/theme + suggestion; fallback `ak:ai-multimodal` hoạt động.
- [x] Report `plans/reports/visual-review-*.md` ghi từng vòng (điểm + finding + sửa gì) + verdict cuối + ảnh trước/sau.
- [x] Kết thúc: **hội tụ (0 finding nghiêm trọng)**; nếu chạm trần còn finding thì liệt kê rõ cho user (không tự nới trần / không làm yếu rubric).

## Risk Assessment
- **Screenshot flaky** (font/animation chưa settle). Mitigation: chờ `document.fonts.ready`, tắt animation lúc chụp (`prefers-reduced-motion` ép), chờ network idle.
- **Vision CLI**: đã chốt **`agy` (Antigravity)** (có sẵn PATH). Nếu lỗi permission khi chạy tự động: thêm `--dangerously-skip-permissions`; nếu lỗi khác: fallback `ak:ai-multimodal`.
- **Vision đánh giá chủ quan/nhiễu**. Mitigation: rubric cố định + chấm số + yêu cầu dẫn chứng cụ thể trên ảnh; người dùng là trọng tài cuối.
- **Loop không hội tụ / thrash** (sửa vòng này phá vòng khác). Mitigation: **trần 4 vòng cứng**; chỉ sửa finding `severity≥major`; diff nhỏ, khu trú; nếu điểm không cải thiện 2 vòng liên tiếp → dừng báo user. **Không tự nới trần, không làm yếu rubric** để "đạt".
- **Auto-fix gây regression chức năng**. Mitigation: mỗi vòng chỉ sửa **thuần trình bày** (spacing/màu/layout/typography), không đụng logic; chạy lại focused test của khu vừa sửa sau mỗi vòng.
- **Ảnh nặng vào git**. Mitigation: gitignore ảnh, chỉ commit report; hoặc lưu ảnh ngoài repo.

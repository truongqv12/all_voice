---
phase: 7
title: "E2E Visual QA + agy Vision Review (chạy thật, giao diện)"
status: pending
priority: P1
effort: "0.5d"
dependencies: [6]
---

# Phase 7: E2E Visual QA + agy Vision Review

## Overview

Cổng **giao diện** cuối, giống plan cũ (phase-07): Playwright chụp **ma trận ảnh** (breakpoints × light/dark × states) trên **build production** với **dữ liệu THẬT** (voices/synth/ASR thật, sau khi đấu nối) → **`agy` vision** soi thẩm mỹ + AI-slop + vỡ layout/contrast/cuộn ngang → **vòng lặp tự sửa** (trần 4 vòng) → report `plans/reports/visual-review-*.md`. Tái dùng harness `frontend/e2e/capture-phase7.mjs` + `__screenshots__/` đã có.

Khác plan cũ: chụp trên **UI đã tích hợp thật** (không mock), và **chỉ 2 khu** (TTS + ASR) vì Cloning đã ẩn. `agy` là tool vision chính (đã có trên PATH); fallback `ak:ai-multimodal`.

Skills/Tools: **`agy` CLI** (vision review chính), `ak:web-testing` (Playwright capture), fallback `ak:ai-multimodal`.

## Requirements

- Functional:
  - **Capture:** `vite build` → `vite preview :4273` (proxy `/v1` → backend anon thật) → chụp full-page các state cốt lõi **2 khu (TTS · ASR)** × breakpoints **375/768/1024/1440** × theme **light/dark**. State gồm: voice list, đã chọn giọng + compose, kết quả synth (player), ASR transcript + subtitle-export, các limit-state (429/too-long qua intercept), empty/loading.
  - **Vision review (`agy`):** gom ảnh → `agy --add-dir frontend/e2e/__screenshots__ -p "$(cat rubric)" --output-format json [--json-schema findings.schema.json] [--dangerously-skip-permissions]`. Rubric: đẹp/hiện đại, rõ ràng/hierarchy, không rối, **không AI-slop** (không gradient tím/glass/neon/emoji-icon), mobile-first đúng, contrast/đọc được, **dữ liệu thật hiển thị gọn** (tên giọng thật dài? style id thô? player thật?). Chấm 1–5/tiêu chí + finding có `severity` + vị trí (screen/bp/theme) + suggestion.
  - **Vòng lặp tự sửa:** lọc finding `severity≥major` (AI-slop/vỡ layout/contrast<4.5/cuộn ngang/touch<44/dữ liệu thật tràn) → tự sửa component khu liên quan → re-capture → re-review → lặp tới **hội tụ** (0 finding major) hoặc **trần 4 vòng**; quá trần còn finding → **dừng, liệt kê cho user** (không tự nới trần, không làm yếu rubric).
  - **Report:** `plans/reports/visual-review-260831-*.md` — mỗi vòng: bảng điểm theo màn/bp/theme + findings + sửa gì (diff/summary) + verdict; cuối: verdict tổng "đẹp/hội tụ" hoặc "còn N finding".
- Non-functional: chạy build production (không dev); deterministic (chờ `fonts.ready`/network-idle, tắt animation khi chụp); **không** cài browser Playwright lên box prod (chỉ dev/CI).

## Architecture

- **Reuse:** `frontend/e2e/capture-phase7.mjs` (đã có) — cập nhật danh sách state cho **UI thật** (bỏ Cloning; thêm state dữ liệu thật) + đảm bảo chụp sau khi `/v1` trả dữ liệu thật (chờ voices load).
- **Backend cho capture:** khởi động app anon (`ANON_ENABLED=true WORKERS=1 uvicorn ... :8124`) để synth/ASR thật render; limit-state qua route-intercept để ổn định.
- **Driver vòng lặp:** `scripts/visual-review/loop.sh` (hoặc runner Node) điều phối capture→`agy`→sửa→re-check (trần 4). `run-vision.sh` gom ảnh + gọi `agy` + rubric; `findings.schema.json` ép cấu trúc; `rubric.md`. (Tạo mới nếu chưa có; chạy `agy --help` xác nhận cờ hiện hành trước.)

## Related Code Files

- Modify: `frontend/e2e/capture-phase7.mjs` (state cho UI thật, bỏ Cloning)
- Create: `scripts/visual-review/loop.sh`, `run-vision.sh`, `rubric.md`, `findings.schema.json` (nếu chưa có từ plan cũ — kiểm trước)
- Output: `frontend/e2e/__screenshots__/` (ảnh mới), `plans/reports/visual-review-260831-*.md`

## Implementation Steps

1. `agy --help` xác nhận cờ; kiểm scripts visual-review cũ còn dùng lại được không.
2. Cập nhật `capture-phase7.mjs` cho UI thật (2 khu, chờ dữ liệu `/v1`).
3. Khởi động backend anon + `vite build && vite preview :4273`.
4. Chạy `loop.sh`: capture → `agy` vision (JSON findings) → nếu 0 finding major → hội tụ; else tự sửa → re-check. Trần 4 vòng.
5. Xuất report tổng; nếu chạm trần còn finding → liệt kê cho user.

## Success Criteria

- [ ] `capture` chụp đủ ma trận state cốt lõi **2 khu (TTS/ASR)** × 4 breakpoint × 2 theme trên **build production, dữ liệu thật**.
- [ ] `agy` vision chạy, trả findings (severity + màn/bp/theme + suggestion); fallback `ak:ai-multimodal` hoạt động khi cần.
- [ ] Vòng lặp tự sửa chạy tới **hội tụ** (0 finding `severity≥major`) hoặc **trần 4 vòng** rồi dừng-báo.
- [ ] Report `plans/reports/visual-review-260831-*.md` ghi từng vòng (điểm + finding + sửa) + verdict cuối + ảnh trước/sau.
- [ ] Không còn AI-slop / vỡ layout / cuộn ngang / contrast fail ở verdict cuối (hoặc finding còn lại được liệt kê rõ cho user).

## Risk Assessment

- **Rủi ro:** dữ liệu thật (tên giọng/style id thô, transcript dài) làm tràn/vỡ layout mà mock không lộ. **Tín hiệu:** finding overflow/truncate. **Ứng phó:** đây chính là mục tiêu phase — sửa clamp/ellipsis/wrap; rubric nêu đích danh "dữ liệu thật tràn".
- **Rủi ro:** `agy` permission/nhiễu chủ quan. **Ứng phó:** `--dangerously-skip-permissions` khi tự động; rubric cố định + chấm số + dẫn chứng; fallback `ak:ai-multimodal`; user là trọng tài cuối.
- **Rủi ro:** loop thrash (sửa vòng này phá vòng khác). **Ứng phó:** trần 4 vòng cứng; chỉ sửa `severity≥major`; diff nhỏ khu trú; điểm không cải thiện 2 vòng → dừng báo.
- **Rủi ro:** ảnh nặng vào git. **Ứng phó:** gitignore `__screenshots__/`, chỉ commit report.

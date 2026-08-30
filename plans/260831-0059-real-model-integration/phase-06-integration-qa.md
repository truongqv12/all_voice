---
phase: 6
title: "Functional QA — test-case độc lập (e2e thao tác + unit) chạy thật"
status: pending
priority: P1
effort: "0.5-1d"
dependencies: [2, 3, 4, 5]
---

# Phase 6: Functional QA (test-case độc lập, chạy thật)

## Overview

Cổng chức năng: **chạy thử từng chức năng theo test-case độc lập** trên backend **thật** (tắt mock), gồm unit (logic thuần) + e2e **thao tác** (điều khiển UI thật qua từng luồng). Bộ test-case do **subagent** (agent `tester`) điều phối/chạy **hoặc** `agy` CLI chạy tự động — mỗi case độc lập, xuất **report pass/fail** vào `plans/reports/`. Tái dùng harness sẵn có `frontend/e2e/test-all-features.mjs`.

Skills/Agents: `ak:web-testing` (Playwright), `ak:test` (chạy suite), **subagent `tester`** hoặc **`agy` CLI** (chạy test-case tự động), `ak:code-review` (review diff trước merge).

## Requirements

- Functional:
  - **Unit (Vitest):** `distributeWords(segments, words)` (words→segment, ca biên); map `/v1/voices`→`Voice` (engine←model, gender neutral, previewUrl, styles); `mapError`→LimitKind (429/400/413/503); subtitle chunk (test cũ `chunk-cues.test.ts`) vẫn xanh.
  - **E2E thao tác — test-case độc lập** (mỗi case tự setup, chạy thật, assert, teardown):
    - TC1 Voices: `/v1/voices` render giọng thật; lọc theo ngôn ngữ/engine + search đổi danh sách; **không** có control giới tính.
    - TC2 Preview: bấm nghe thử → phát audio thật (single-instance).
    - TC3 Synth ngắn (≤1200): Tạo → có `<audio>`/objectURL + Download đúng format; `model` theo engine giọng.
    - TC4 Synth dài (>1200): stream → progress indeterminate → player + Download; UI không treo.
    - TC5 Style/Speed theo engine: giọng VieNeu **không** có speed; style-select chỉ hiện khi có styles; **không** nút TTS→SRT.
    - TC6 ASR: upload audio mẫu ngắn → transcript segment+timestamp; xuất **SRT/VTT/TXT** có nội dung; đổi options (chars/line…) đổi output.
    - TC7 Limit: intercept `/v1/*` trả envelope **429/400/413** → hiện limit-state VN/EN đúng (ổn định CI, không cần ép limit thật).
    - TC8 Cloning ẩn: không nav `/clone`; deep-link `/clone` → redirect `/`; picker không nhóm clone.
    - TC9 Deep-link `/transcribe` load trực tiếp OK (SPA fallback).
    - TC10 i18n/theme: đổi VN↔EN đổi chuỗi; light↔dark không FOUC (smoke).
  - **Orchestration (chốt ở validation):** chạy test-case qua **subagent `tester`** (tự chạy từng TC, tổng hợp Status DONE/CONCERNS + report) **hoặc** `agy` CLI print-mode (autonomous). Ghi report `plans/reports/tester-260831-*.md`.
  - Thay/gỡ e2e cũ (`tests/e2e/*` phục vụ `web/index.html`) — phối hợp phase 5.
- Non-functional: mỗi TC **độc lập** (không phụ thuộc thứ tự/state case khác); chờ `network-idle`/`fonts.ready`; không flaky; tài liệu cách chạy.

## Architecture

- **Harness:** mở rộng `frontend/e2e/test-all-features.mjs` (đã có) thành bộ test-case có tên + assert + report; hoặc `frontend/e2e/functional.spec.ts` (Playwright test-runner) — 1 `test()` / case = độc lập.
- **Chạy thật:** script khởi động backend anon (`ANON_ENABLED=true WORKERS=1 uvicorn app.main:app --port 8124`) + build/preview FE (`vite preview --port 4273`) proxy `/v1`; happy-path gọi thật, case limit dùng route-intercept.
- **Subagent-driven:** giao `tester` agent prompt: env (cwd `/home/truong/all_voice`, backend port 8124 anon, FE preview 4273), danh sách TC + acceptance, files được đọc/sửa (chỉ test + report), reports path `plans/reports/`, kết thúc bằng Status/Summary/Concerns. **Hoặc** `agy` CLI: `agy --add-dir frontend -p '<chạy từng test-case, báo pass/fail>' --output-format json --dangerously-skip-permissions`.
- **Fixture:** 1 file audio mẫu ngắn cho TC6 (asset test riêng, không commit nặng vào git).

## Related Code Files

- Create: `frontend/src/api/*.test.ts` (unit: distribute-words, voice-map, error-map)
- Create/Modify: `frontend/e2e/functional.spec.ts` (hoặc mở rộng `test-all-features.mjs`) — 10 TC độc lập
- Create: `frontend/e2e/playwright.config.ts` (nếu dùng test-runner), fixture audio ngắn
- Modify: `frontend/package.json` (scripts `test`, `test:e2e`; devDeps Vitest/Playwright nếu thiếu)
- Delete (phối hợp phase 5): `tests/e2e/ui-smoke.spec.ts` + config cũ
- Output: `plans/reports/tester-260831-*.md` (bảng TC pass/fail + concern)

## Implementation Steps

1. Vitest + unit cho 3 hàm thuần; chạy subtitle test cũ.
2. Viết 10 TC e2e độc lập (happy-path thật + limit intercept).
3. Script khởi động backend anon + preview FE cho e2e.
4. Chạy bộ TC qua **subagent `tester`** hoặc **`agy` CLI** (theo chốt validation) → thu report pass/fail.
5. Sửa regression (không làm yếu test); `ak:code-review` diff toàn bộ phase (bug/regression/leak objectURL/i18n sót).

## Success Criteria

- [ ] Unit xanh (`distributeWords`, voice-map, `mapError`, subtitle).
- [ ] 10 TC e2e **độc lập** chạy thật, **pass hết** (TC7 limit qua intercept); report `plans/reports/tester-260831-*.md` liệt kê từng TC pass/fail.
- [ ] Bộ TC chạy được qua **subagent `tester`** hoặc **`agy` CLI** (autonomous), không cần thao tác tay từng bước.
- [ ] `ak:code-review` không finding nghiêm trọng; **không rò rỉ objectURL**.
- [ ] E2E cũ (web demo) đã thay; CI xanh.

## Risk Assessment

- **Rủi ro:** e2e gọi model thật chậm/flaky (CPU synth lâu). **Tín hiệu:** timeout. **Ứng phó:** text ngắn + timeout rộng; e2e-real ở local/manual, CI giữ phần intercept ổn định.
- **Rủi ro:** TC phụ thuộc lẫn nhau (không độc lập). **Tín hiệu:** đổi thứ tự → đỏ. **Ứng phó:** mỗi TC tự navigate + reset state; không dùng chung selection.
- **Rủi ro:** thiếu `--extra asr` → ASR 503. **Tín hiệu:** TC6 đỏ. **Ứng phó:** tài liệu `uv sync --extra asr`; skip có điều kiện + báo rõ.
- **Rủi ro:** subagent/`agy` chạy sai phạm vi (sửa code ngoài test). **Ứng phó:** prompt giới hạn files sửa = chỉ test + report; review diff.

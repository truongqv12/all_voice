---
phase: 6
title: "E2E functional QA — sub-agent thao tác"
status: completed
priority: P1
effort: "1-1.5d"
dependencies: [2, 3, 4, 5]
---

# Phase 6: E2E functional QA — sub-agent thao tác

## Overview
QA lại toàn bộ bằng **test-case độc lập** từ báo cáo rà soát
([`qa-260831-0840-tts-subtitle-review-testplan.md`](../reports/qa-260831-0840-tts-subtitle-review-testplan.md)),
do **sub-agent `tester` thao tác thật** trên backend dev + unit cho logic mới. Ưu tiên nhóm High.

## Requirements
- Functional — Unit (Vitest):
  - P1: timeout→abort; requestId bỏ kết quả cũ; error-map `timeout`.
  - P3: `error-map.test.ts` mở rộng (400-audio/401/404/503-asr đúng kind; code-trước-status).
  - P4: orchestration subtitle (words→cues, prompt gửi đúng); P5: accent-phrase→cue; giữ `chunk-cues.test.ts` xanh.
- Functional — E2E thao tác (Playwright, mỗi case tự setup/teardown, độc lập), map theo báo cáo:
  - **High bắt buộc:** VT-01..03, VF-02/03, VL-02/03 (2000/20k), VL-04 (429 không hang), VS-01/02/04/05 (subtitle VI/EN + gần đúng + progress), SF-01/02/04/05/06/07/08 (transcribe file thật + biên + 503-asr), UP-01/02 (cancel picker/đổi file), PG-01/03/04 (progress/timeout/double-run), RF-01/03/05 (F5/đổi khu khi chạy), VA-01/03 (empty guard), EH-01..05 (mã lỗi), RR-01 (retry), EC-01/02/03/04 (double-click/race/output rỗng/preview khác nhau).
  - **SF-03:** xác nhận **đã gỡ** nút "sample".
  - Case lệ thuộc model thật (chậm): text ngắn + timeout rộng; case limit (EH/429/413/503) dùng **route-intercept** cho ổn định CI.
- Non-functional: mỗi TC độc lập (đổi thứ tự vẫn xanh); chờ network-idle/fonts.ready; không flaky; tài liệu cách chạy; **sub-agent `tester`** tổng hợp Status/Summary/Concerns → report `plans/reports/tester-260831-*.md`.

## Architecture
- Harness: mở rộng `frontend/e2e/functional.spec.ts` (Playwright test-runner), 1 `test()`/case.
- Backend dev cho E2E: `ANON_ENABLED=true WORKERS=1 uv run uvicorn app.main:app --port 8125` (+ `uv sync --extra asr`; `--extra ja` cho case JP), **KHÔNG** đụng :8124 live. FE `vite preview --port 4273` proxy `/v1`→:8125.
- Sub-agent `tester`: prompt kèm env (cwd, port 8125 anon, FE 4273), danh sách TC + acceptance, files được sửa (chỉ test + report), reports path, Status/Summary/Concerns cuối. Fixture audio ngắn thật cho SF (asset test, không commit nặng).

## Related Code Files
- Create/Modify: `frontend/e2e/functional.spec.ts` (test-case mới, High trước)
- Create: `frontend/src/**/*.test.ts` (unit P1/P3/P4/P5)
- Create: fixture audio ngắn cho SF (asset test)
- Modify: `frontend/package.json` (scripts test/test:e2e nếu thiếu)
- Output: `plans/reports/tester-260831-*.md` (bảng TC pass/fail + concern)

## Implementation Steps
1. `ak:test`: chạy unit trước (nhanh) — sửa tới xanh.
2. `ak:web-testing`: viết test-case E2E (High trước) — happy-path thật + limit intercept.
3. Script khởi động backend dev :8125 + FE preview 4273.
4. **Spawn sub-agent `tester`** chạy từng TC tự động, thu report pass/fail (kèm env đúng chuẩn orchestration-protocol).
5. Sửa regression (không làm yếu test); `ak:code-review` diff toàn phase (bug/regression/rò objectURL/i18n sót).

## Success Criteria
- [ ] Unit xanh (P1/P3/P4/P5 + subtitle cũ).
- [ ] Test-case **High pass hết** (limit qua intercept), do **sub-agent `tester`** thao tác thật; report liệt kê từng TC pass/fail.
- [ ] SF-03 xác nhận không còn nút sample; preview EC-04 mỗi voice khác nhau.
- [ ] `ak:code-review` không finding nghiêm trọng; không rò objectURL.

## Risk Assessment
- **Rủi ro:** model thật chậm/flaky (CPU synth+ASR lâu, subtitle 2×). **Tín hiệu:** timeout E2E. **Ứng phó:** text ngắn, timeout rộng; case nặng chạy local/manual, CI giữ phần intercept.
- **Rủi ro:** thiếu `--extra asr`/`--extra ja` → SF/JP đỏ. **Ứng phó:** skip có điều kiện + báo rõ; tài liệu `uv sync`.
- **Rủi ro:** sub-agent sửa ngoài phạm vi. **Ứng phó:** prompt giới hạn files=chỉ test+report; review diff.
- **Rủi ro:** đụng nhầm backend :8124 live. **Ứng phó:** ép port 8125 dev; kiểm `lsof -i` trước khi start; dừng process dev khi xong (process-management).

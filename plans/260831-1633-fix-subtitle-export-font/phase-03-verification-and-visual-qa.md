# Phase 3: Verification và visual QA

## Overview

Priority P1 · Completed. Chứng minh bug cũ không tái diễn và không gây regression trên TTS/transcription.

## Related files

- `frontend/src/lib/subtitle/*.test.ts`
- `frontend/src/features/compose/use-generate-subtitle.test.ts`
- `frontend/e2e/functional.spec.ts`

## Implementation steps

1. Chạy unit tests subtitle/download và toàn bộ Vitest.
2. Chạy `pnpm build` để typecheck + production build.
3. Chạy Playwright smoke phù hợp; xác minh `/` và `/transcribe` ở mobile/desktop, console sạch.
4. Kiểm tra bytes file mẫu có BOM `EF BB BF` và decode Unicode đúng.
5. Delegate tester, code-reviewer; sửa mọi finding correctness trước khi chốt.

## Todo / success criteria

- [x] Regression tests đỏ với contract cũ, xanh với fix.
- [x] Vitest/build/E2E đều exit 0.
- [x] Không còn sample affordance; selector line/word thao tác được ở 375px và desktop.

## Risks / rollback / security

Nếu test cho thấy caller phụ thuộc `sentence`, giữ compatibility shim có kiểm soát thay vì âm thầm phá contract. Rollback từng phase độc lập; không có migration/data mutation.

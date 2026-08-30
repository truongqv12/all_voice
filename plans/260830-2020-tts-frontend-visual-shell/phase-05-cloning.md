---
title: "Phase 5: Voice Cloning (mock, consent-first)"
status: done
---

# Phase 5: Voice Cloning — mock, consent-first

## Overview
Dựng khu **`/clone`**: luồng **nhân bản giọng** ở dạng **visual/mock** — form đăng ký (tên + mẫu giọng + **đồng ý bắt buộc**) → "xử lý" giả lập → danh sách clone của bạn → dùng như một giọng trong TTS (mock). Backend thật **gate sau đăng nhập + consent**; ràng buộc thật là việc **giai đoạn tích hợp** — phase này chỉ dựng **UI + đặt consent làm trung tâm** để review hình thức.

## Requirements
- Functional: `CloneEnrolForm` gồm **tên clone**, **mẫu giọng** (upload `.wav/.mp3` hoặc ghi âm mock 10-30s), và **consent checkbox** (xác nhận có quyền dùng giọng — không mạo danh); nút Tạo **chỉ bật khi đủ mẫu + đã đồng ý**; mock progress → clone mới vào `MyClonesList`; mỗi clone: tên/ngày/trạng thái + xoá (confirm); clone hiện trong voice picker TTS như nhóm **"Giọng của bạn"** (mock). `AuthGate` mock (toggle demo) để trình diễn cả **chưa đăng nhập** (CTA đăng nhập) lẫn **đã đăng nhập** (form).
- Non-functional: **consent first-class**, không ẩn/không gợi "mua thêm"; a11y form (label hiện, error dưới field, required, focus-first-invalid); mobile-first; ghi âm dùng mock (không bắt buộc mic thật ở visual stage).

## Architecture
- `clone-api` interface + `mockCloneApi` (`createClone`, `listClones`, `deleteClone`) — cùng pattern `TtsApi`/`transcribe-api`.
- `CloneEnrolForm`: `NameField` + `SampleInput` (upload hoặc `RecordButton` mock) + `ConsentCheckbox` (câu đồng ý rõ ràng, bắt buộc) → submit disabled tới khi hợp lệ; `useClone` (mock) chạy progress `idle|processing|done|error`.
- `MyClonesList` + `CloneCard`: danh sách, empty-state ("chưa có giọng nhân bản"), xoá có confirm (destructive, aria).
- `AuthGate` (mock): demo-state "chưa đăng nhập" → panel CTA (nút đăng nhập mock, giải thích vì sao cần); "đã đăng nhập" → form + list. Phản ánh việc backend gate cloning sau auth.
- Kết nối: clone tạo xong feed vào `store/selection` (phase 2) như nhóm "Giọng của bạn" để chọn ở TTS (mock).
- **Ràng buộc thật (không thuộc phase này):** auth/consent/kiểm định giọng do backend + integration lo; ở đây chỉ dựng UI và nhấn mạnh consent.

## Related Code Files
- Create: `frontend/src/features/clone/clone-page.tsx`, `clone-enrol-form.tsx`, `consent-checkbox.tsx`, `sample-input.tsx`, `record-button.tsx` (mock), `my-clones-list.tsx`, `clone-card.tsx`, `auth-gate.tsx`
- Create: `frontend/src/features/clone/use-clone.ts`
- Create: `frontend/src/data/clone-fixtures.ts` (0-2 clone mẫu cho list)
- Create: `frontend/src/api/clone-api.ts` (interface + `mockCloneApi`)
- Modify: `frontend/src/app/router.tsx` (route `/clone`), `frontend/src/store/selection.ts` (nhóm "Giọng của bạn"), `frontend/src/i18n/locales/*` (chuỗi cloning/consent)

## Implementation Steps
1. `clone-api` interface + `mockCloneApi` + `clone-fixtures`.
2. `ConsentCheckbox` + `SampleInput` (upload; `RecordButton` mock đếm giây); validate hợp lệ = có mẫu + đã đồng ý.
3. `CloneEnrolForm` + `useClone`: submit → progress → thêm clone; error demoable.
4. `MyClonesList`/`CloneCard`: list + empty + xoá (confirm).
5. `AuthGate` mock: toggle demo chưa/đã đăng nhập; CTA đăng nhập (mock).
6. Feed clone vào `store/selection` như nhóm "Giọng của bạn"; kiểm chọn ở TTS.
7. Ráp `ClonePage`; nối route `/clone`.

## Success Criteria
- [ ] Form cloning: tên + mẫu + **consent bắt buộc**; nút Tạo chỉ bật khi đủ điều kiện.
- [ ] Tạo (mock) → progress → clone vào danh sách; xoá có confirm; empty-state có mặt.
- [ ] Clone hiện trong voice picker TTS như nhóm "Giọng của bạn" (mock).
- [ ] `AuthGate` demo được cả chưa/đã đăng nhập; copy giải thích vì sao cần đăng nhập.
- [ ] a11y form: label/error/required/focus-first-invalid; destructive (xoá) có confirm + màu danger.
- [ ] Mobile: form + list xếp gọn, thao tác ngón tay tốt (≥44px).

## Risk Assessment
- **Consent bị coi nhẹ** (ẩn/checkbox mờ). Mitigation: consent là điều kiện bắt buộc để submit, text rõ, không mặc định tick. Signal: submit được khi chưa tick → lỗi.
- **Mock tưởng thật** (người dùng nghĩ đã clone). Mitigation: nhãn "bản mẫu/mock" rõ; interface sẵn để swap http + auth thật ở integration.
- **Quyền mic khi ghi âm**. Mitigation: giai đoạn visual dùng mock đếm giây (không cần mic thật); MediaRecorder thật để integration.
- **Đạo đức/mạo danh giọng**. Mitigation: UI nhấn consent + "không mạo danh"; enforcement thật do backend (auth-gated) — ghi rõ là integration-stage.

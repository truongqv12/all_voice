---
phase: 1
title: "FE task-lâu robustness (timeout/abort/retry/progress/race)"
status: completed
priority: P1
effort: "1-1.5d"
dependencies: []
---

# Phase 1: FE task-lâu robustness

## Overview
Nền tảng độ bền cho mọi task lâu (synth dài, ASR file lớn, subtitle round-trip): thêm
**timeout**, **AbortController (hủy)**, **retry**, **progress rõ theo giai đoạn**, **requestId guard**
chống race + chống double-run. Lấp GAP-5/GAP-7 của rà soát QA.

## Requirements
- Functional:
  - `http-client.ts` nhận `AbortSignal` và **timeout** (mặc định 150s, override qua tham số) — hết giờ → abort + ném `ApiError{code:'timeout'}`.
  - `synth`/`synthStream` (`http-tts-api.ts`) + `transcribe` (`http-transcribe-api.ts`) truyền `signal` xuyên suốt fetch/XHR; XHR gọi `xhr.abort()` khi signal abort.
  - `use-generate.ts` / `use-transcribe.ts`: mỗi lần chạy tạo `AbortController` + `requestId` tăng dần; **chỉ nhận** response khớp `requestId` hiện tại (bỏ response cũ khi user đổi input/model/voice).
  - **Nút Hủy** hiện khi đang chạy → gọi `controller.abort()` → reset UI về idle (không kẹt loading).
  - **Nút Retry** hiện ở error-state → chạy lại request gần nhất với cùng tham số.
  - **Chống double-run:** nút hành động disabled khi đang chạy (đã có ở compose — bổ sung cho transcribe).
  - **Progress theo giai đoạn:** `progress-status.tsx` hiện nhãn ("Đang chuẩn bị…/Đang tổng hợp…/Đang nhận dạng…") + %/KB khi có; không đứng 0% câm như treo.
- Non-functional: cleanup `AbortController` + revoke objectURL khi unmount/đổi request (không rò `use-audio-player.ts`); i18n VN/EN cho nhãn mới; không đổi contract API.

## Architecture
- `HttpClientOptions{ signal?, timeoutMs? }`: bọc `fetch` với `AbortSignal.any([caller, timeout])` (hoặc timeout tự tạo controller + `setTimeout`→abort, clear khi xong).
- Hook pattern: `const idRef=useRef(0); const id=++idRef.current; const ac=new AbortController();` → sau await, `if(id!==idRef.current) return;` (bỏ kết quả cũ). Lưu `lastParams` cho retry.
- Progress: giữ nguyên cơ chế byte/stage hiện có, chỉ thêm nhãn giai đoạn + map `progress===0 && running` → "đang xử lý".

## Related Code Files
- Modify: `frontend/src/api/http-client.ts` (signal + timeout)
- Modify: `frontend/src/api/http-tts-api.ts`, `frontend/src/api/http-transcribe-api.ts` (truyền signal; XHR abort)
- Modify: `frontend/src/features/compose/use-generate.ts` (requestId, abort, retry, lastParams)
- Modify: `frontend/src/features/transcribe/use-transcribe.ts` (requestId, abort, retry, disable-guard)
- Modify: `frontend/src/features/compose/progress-status.tsx` (nhãn giai đoạn)
- Modify: `frontend/src/features/compose/compose-panel.tsx`, `frontend/src/features/transcribe/transcribe-page.tsx` (nút Hủy/Retry)
- Modify: `frontend/src/features/compose/use-audio-player.ts` (revoke objectURL)
- Modify: `frontend/src/api/error-map.ts` (thêm `timeout` kind), `frontend/src/i18n/index.ts` (chuỗi mới)

## Implementation Steps
1. `ak:frontend-development` + `ak:docs-seeker` (AbortSignal.any / XHR abort/timeout hiện hành).
2. Thêm signal+timeout vào `http-client.ts`; lan xuống tts/transcribe api (fetch + XHR).
3. requestId guard + AbortController + lastParams vào `use-generate.ts` & `use-transcribe.ts`.
4. UI nút Hủy + Retry + disable-guard; nhãn progress theo giai đoạn; i18n.
5. Đảm bảo revoke objectURL khi đổi/hủy/unmount.
6. Unit test (Vitest): timeout→abort; requestId bỏ kết quả cũ; error-map `timeout`.

## Success Criteria
- [ ] BE giả chậm > timeout → UI hiện lỗi timeout + nút Retry (không treo vô hạn).
- [ ] Bấm Hủy khi đang chạy → request abort, UI về idle sạch.
- [ ] Đổi input/model/voice giữa chừng → kết quả cũ **không** ghi đè kết quả mới (requestId).
- [ ] Double/triple click Tạo/Transcribe → chỉ 1 request.
- [ ] Progress hiện nhãn giai đoạn (không 0% câm); objectURL được revoke (không rò).
- [ ] Unit mới xanh.

## Risk Assessment
- **Rủi ro:** `AbortSignal.any` không hỗ trợ ở target trình duyệt cũ. **Tín hiệu:** lỗi runtime. **Ứng phó:** fallback tự tạo controller + `setTimeout`.
- **Rủi ro:** abort stream để lại objectURL/partial. **Tín hiệu:** rò bộ nhớ. **Ứng phó:** revoke trong finally; test đóng tab (`streaming.py:127-129` BE tự refund).
- **Rủi ro:** timeout mặc định cắt oan đoạn dài hợp lệ. **Tín hiệu:** đoạn ~20k bị timeout. **Ứng phó:** timeout cấu hình được; đo ở P6, chỉnh cho phù hợp inference thật.

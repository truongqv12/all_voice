---
phase: 1
title: "API foundation (env, proxy, http-client, error-map, provider)"
status: pending
priority: P1
effort: "0.5-1d"
dependencies: []
---

# Phase 1: API foundation

## Overview

Dựng nền tảng để mọi adapter `http*` dùng chung: biến môi trường base URL, Vite dev proxy `/v1`, một `http-client` fetch wrapper hiểu OpenAI error-envelope, một `error-map` quy lỗi về `LimitKind` cho UI, và **hợp nhất** `ttsApi`+`transcribeApi`+`cloneApi` qua `ApiProvider` (chọn mock/http bằng env). Chưa gọi endpoint cụ thể — chỉ khung.

Skills: `ak:frontend-development`, `ak:react-best-practices`, `ak:docs-seeker` (Vite `server.proxy`/env vars hiện hành).

## Requirements

- Functional:
  - `VITE_API_BASE` (default `/v1`) là base cho mọi request; `VITE_USE_MOCK=1` ⇒ dùng mock adapter; không cờ ⇒ http.
  - Vite dev proxy `/v1` → `VITE_API_PROXY_TARGET` (default `http://127.0.0.1:8124`), `changeOrigin`, giữ path.
  - `http-client` trả JSON hoặc `Blob`/`Response` tuỳ endpoint; khi HTTP lỗi, parse envelope `{error:{message,type,code}}` → ném `ApiError{status, code, message}`.
  - `error-map` chuyển `ApiError` (code/status) → `LimitKind` = `'rate'|'quota'|'too-long'|'overloaded'|'asr-too-long'` (dùng dấu gạch nối khớp key demo cũ), non-limit → `null` (UI hiện lỗi generic).
  - **[Validation F1]** `limit-states.tsx` hiện là **demo** (đọc URL `?limit=`), CHƯA nối lỗi thật → **refactor thành error-driven**: `LimitStates` nhận prop `kind: LimitKind | null`, render khi có kind; **bỏ đường `?limit=` demo**. Wiring: `use-generate`/`use-transcribe` catch `ApiError` → `mapError` → set `kind` → truyền vào `LimitStates` mount ở compose/transcribe panel.
  - `ApiProvider` cung cấp `ttsApi`, `transcribeApi`, `cloneApi`; thêm hook `useTranscribeApi()`, `useCloneApi()` (đồng bộ với `useTtsApi()` đã có).
- Non-functional: TS strict, không đụng UI hiển thị; giữ khả năng chạy mock cho visual QA; không rò rỉ resource.

## Architecture

- `http-client.ts`: `apiFetch(path, init)` → `fetch(`${BASE}${path}`, init)`; nếu `!res.ok` đọc body JSON envelope (fallback text) → `throw new ApiError(...)`. Không tự set `Authorization` (anon). Export helper `apiJson<T>()`, `apiBlob()`, và trả thẳng `Response` cho streaming.
- `error-map.ts`: bảng `code → LimitKind`:
  - `rate_limit_exceeded` → `rate`; `quota_exceeded` → `quota`; `input_too_long` → `too_long`; `server_overloaded` → `overloaded`; HTTP `413` (ASR) → `asr_too_long`; còn lại → `generic`.
- `api-context.tsx` (mở rộng): context giữ object `{ ttsApi, transcribeApi, cloneApi }`. Chọn implementation:
  - `const useMock = import.meta.env.VITE_USE_MOCK === '1'`
  - `ttsApi = useMock ? mockTtsApi : httpTtsApi` (tương tự transcribe/clone). Cho phép override qua props (test).
- Đưa **ASR + Clone qua context** (hiện đang import mock trực tiếp) — sửa `use-transcribe.ts`, `clone-enrol-form.tsx`, `my-clones-list.tsx` dùng `useTranscribeApi()`/`useCloneApi()` thay vì import `mock*`.

## Related Code Files

- Create: `frontend/src/api/http-client.ts`
- Create: `frontend/src/api/error-map.ts`
- Create: `frontend/src/api/http-tts-api.ts` (stub export để provider import; điền ở phase 2)
- Create: `frontend/src/api/http-transcribe-api.ts` (stub; điền ở phase 3)
- Create: `frontend/src/api/http-clone-api.ts` (stub; điền ở phase 4, để dành)
- Modify: `frontend/src/api/api-context.tsx` (cung cấp 3 api + 2 hook mới + chọn mock/http)
- Modify: `frontend/src/api/types.ts` (thêm `previewUrl?: string` vào `Voice`; nới `TranscriptionResult.language` sang `string`; **[F2]** `AudioFormat` = `'mp3'|'wav'`)
- Modify: `frontend/src/features/status/limit-states.tsx` (**[F1]** refactor error-driven: prop `kind`, bỏ `?limit=`)
- Modify: `frontend/src/features/compose/compose-panel.tsx` (truyền `kind` lỗi thật vào `LimitStates`)
- Modify: `frontend/src/features/transcribe/transcribe-page.tsx` (mount `LimitStates` + `kind` lỗi ASR) <!-- Updated: Validation Session 1 - F1 error-driven limit states -->
- Modify: `frontend/src/lib/limits.ts` (giữ `textLimits`; đồng bộ ngưỡng 1200/20000 với BE anon)
- Modify: `frontend/vite.config.ts` (`server.proxy['/v1']`)
- Modify: `frontend/src/features/transcribe/use-transcribe.ts` (dùng `useTranscribeApi()`)
- Modify: `frontend/src/features/clone/clone-enrol-form.tsx`, `frontend/src/features/clone/my-clones-list.tsx` (dùng `useCloneApi()`)
- Modify: `frontend/.env.example` (NEW nếu chưa có) ghi `VITE_API_BASE`, `VITE_USE_MOCK`, `VITE_API_PROXY_TARGET`

## Implementation Steps

1. Thêm `server.proxy` vào `vite.config.ts`; đọc target từ `loadEnv`/`process.env.VITE_API_PROXY_TARGET` (default `http://127.0.0.1:8124`).
2. Viết `http-client.ts` (`ApiError` class, `apiFetch`, `apiJson`, `apiBlob`).
3. Viết `error-map.ts` (`mapError(err): LimitKind`), khớp key mà `limit-states.tsx` đang render.
4. Tạo 3 stub `http-*-api.ts` (export object đúng interface, tạm `throw new Error('not implemented')` — sẽ điền ở phase sau) để provider compile.
5. Mở rộng `api-context.tsx`: context 3-api, hook `useTranscribeApi`/`useCloneApi`, chọn mock/http theo `VITE_USE_MOCK`.
6. Chuyển 3 consumer ASR/Clone sang hook context.
7. Thêm `previewUrl?` vào `Voice`; nới `language` type ở `TranscriptionResult`.
8. `frontend/.env.example` + ghi chú README FE ngắn (nếu có).
9. `npm run build` + `npm run dev` (mock) đảm bảo không vỡ (chạy `VITE_USE_MOCK=1` để xác nhận đường mock vẫn sống).

## Success Criteria

- [ ] `vite.config.ts` có proxy `/v1`; `npm run dev` không lỗi.
- [ ] `VITE_USE_MOCK=1 npm run dev` → app chạy y như trước (mock), 3 khu render.
- [ ] `http-client` ném `ApiError{code}` đúng khi server trả envelope lỗi (test tay bằng 1 fetch giả/hoặc unit ở phase 6).
- [ ] ASR + Clone lấy api qua context (không còn `import { mock* }` trong component).
- [ ] TS strict pass, `npm run build` xanh.

## Risk Assessment

- **Rủi ro:** provider import stub `http-*` chưa implement → runtime lỗi khi không set mock. **Tín hiệu:** app crash lúc gọi synth/transcribe ở chế độ http trước phase 2/3. **Ứng phó:** giữ `VITE_USE_MOCK=1` trong lúc dev phase 1; stub chỉ throw khi *được gọi*, không throw lúc import.
- **Rủi ro:** dev proxy target sai port (8123 vs 8124). **Tín hiệu:** 502/ECONNREFUSED ở `/v1`. **Ứng phó:** đọc `.env` `PORT`; cho override `VITE_API_PROXY_TARGET`; ghi rõ ở `.env.example`.
- **Rủi ro:** đổi consumer ASR/Clone sang context làm vỡ test/visual. **Tín hiệu:** trang `/transcribe` `/clone` lỗi context. **Ứng phó:** đảm bảo `ApiProvider` bọc toàn app (đã bọc ở `App.tsx`); smoke cả 3 khu ở mock.

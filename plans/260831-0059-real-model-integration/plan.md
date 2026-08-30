---
title: "Real-Model Integration — đấu nối FE `frontend/` vào backend `/v1` thật (thay demo cũ)"
description: "Swap mock adapter → http adapter cho TTS + ASR gọi backend /v1 thật, same-origin sau nginx (serve frontend/dist + SPA fallback), retire web/index.html. Ẩn mọi thứ backend chưa hỗ trợ cho anon công khai: Voice Cloning, filter giới tính, mô tả giọng, speed cho VieNeu, affordance TTS→SRT."
status: pending
priority: P1
effort: "4-6d"
tags: [frontend, integration, http-adapter, tts, asr, streaming, nginx, spa, deploy, react, vite, same-origin, anon]
created: 2026-08-31
---

# Real-Model Integration (thay phần demo)

## Overview

Giai đoạn 2 của web `all_voice`: **đấu nối FE độc lập** (đã dựng ở plan `260830-2020-tts-frontend-visual-shell`, status *done*, chạy bằng mock) vào **backend FastAPI thật ở prefix `/v1`**. Theo thiết kế DRY của plan cũ: chỉ **thêm lớp `http*` adapter** và swap ở provider — **UI components gần như không đổi**. Đồng thời **thay UI demo cũ** (`web/index.html` vanilla) bằng SPA `frontend/dist` do nginx serve **same-origin** (khỏi CORS).

**Nguyên tắc chốt (theo yêu cầu):** *cái gì backend chưa hỗ trợ (an toàn cho anon công khai) thì **ẩn đi***, giữ code sau feature-flag để bật lại khi có điều kiện.

Bằng chứng contract: brainstorm `plans/reports/brainstorm-260830-1940-tts-frontend-ui-ux.md` + phân tích đấu nối phiên này (map đầy đủ FE↔BE). Backend surface: `app/main.py` (prefix `/v1`), `app/routers/*`, `app/schemas.py`, `app/limits.py`, `app/quota.py`, `app/auth.py`.

## Contract

- **Outcome:** `frontend/` gọi `/v1` thật cho **TTS** (`/v1/audio/speech`, `/v1/audio/stream`) + **ASR** (`/v1/audio/transcriptions` + phụ đề chunk client-side), chạy same-origin sau nginx (serve `frontend/dist` + proxy `/v1` + SPA fallback), **retire `web/index.html`**. Khu **Cloning + mọi affordance BE chưa hỗ trợ** bị **ẩn** khỏi UI anon (giữ code sau flag).
- **Constraints:** same-origin (không CORS — `app/` không bật CORS middleware); anon tier cho TTS+ASR (không cần API key); giữ **subtitle chunk client-side** (BE chỉ segment-level); chỉ đụng `frontend/src/api/*`, `frontend/src/config/*`, `frontend/vite.config.ts`, một số component cho progress/flag, `deploy/nginx*`, `docs/deployment.md`, `deploy/install-service.sh` — **KHÔNG đụng `app/` backend**; `WORKERS=1` khi anon bật; canh limit FE theo BE; map lỗi OpenAI-envelope → `limit-states` VN/EN.
- **Non-goals:** auth/login; scope clone per-user; đấu nối clone thật; MSE true-streaming (indeterminate là đủ); TTS→SRT verbatim; sửa model/endpoint backend; bổ sung `gender`/`description` vào backend.
- **Acceptance:** xem "Success Criteria" cuối file.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Nền tảng API: `VITE_API_BASE` + Vite dev proxy `/v1`, http-client dùng chung, error→limit-state map, hợp nhất `ttsApi`+`transcribeApi`+`cloneApi` qua `ApiProvider` (chọn mock/http bằng env) | P1 |
| 2 | `http-tts-api`: voices (map `model→engine`, ẩn field BE thiếu) + preview thật + synth buffered + stream (indeterminate) | P1 |
| 3 | `http-transcribe-api`: multipart `verbose_json`+word timestamps → `segment.words[]`; giữ subtitle client-side; upload progress | P1 |
| 4 | Ẩn thứ BE chưa hỗ trợ cho anon: **Cloning** (nav+route+picker group), filter **giới tính**, **mô tả** giọng, **speed** cho VieNeu, affordance **TTS→SRT** | P1 |
| 5 | Deploy: nginx serve `frontend/dist` + `try_files` SPA fallback + proxy `/v1`; build step; **retire `web/index.html`**; update docs | P1 |
| 6 | **Functional QA**: unit + e2e **thao tác theo test-case độc lập** chạy thật (do **subagent `tester`** hoặc **`agy` CLI** điều phối) + code-review | P1 |
| 7 | **E2E Visual QA + `agy` vision** (giống plan cũ): chụp ma trận ảnh dữ liệu thật → vision soi thẩm mỹ/AI-slop → vòng lặp tự sửa → report | P1 |

## Phases

| # | Phase | Status | Depends |
|---|-------|--------|---------|
| 1 | [API foundation (env, proxy, http-client, error-map, provider)](./phase-01-start.md) | Pending | — |
| 2 | [http-tts-adapter (voices/preview/synth/stream)](./phase-02-http-tts-adapter.md) | Pending | 1 |
| 3 | [http-asr-adapter (transcribe + words→segments)](./phase-03-http-asr-adapter.md) | Pending | 1 |
| 4 | [Ẩn Cloning + affordance BE chưa hỗ trợ](./phase-04-hide-clone-and-unsupported.md) | Pending | 1, 2 |
| 5 | [Deploy: nginx SPA + retire demo cũ](./phase-05-deploy-nginx-spa-retire-demo.md) | Pending | 2, 3, 4 |
| 6 | [Functional QA — test-case độc lập (subagent/agy)](./phase-06-integration-qa.md) | Pending | 2, 3, 4, 5 |
| 7 | [E2E Visual QA + agy Vision Review](./phase-07-visual-qa-agy-vision.md) | Pending | 6 |

## Architecture (đấu nối)

```
Prod (public):  browser ──HTTPS──> Cloudflare edge ──> cloudflared ──> nginx :8123
                                                                        ├─ /            -> serve frontend/dist (SPA, try_files /index.html)
                                                                        └─ /v1/*        -> proxy 127.0.0.1:8124 (FastAPI app)
Dev (local):    vite :5273 ──/v1 proxy──> 127.0.0.1:8124 (uvicorn app.main:app)

frontend/src/api/
├─ types.ts                 # +engine passthrough, +previewUrl (Voice), nới language type
├─ http-client.ts     (NEW) # fetch wrapper: base=VITE_API_BASE, parse OpenAI error envelope -> ApiError{code}
├─ error-map.ts       (NEW) # ApiError.code / HTTP status -> LimitKind ('rate'|'quota'|'too-long'|'overloaded'|'asr-too-long')
├─ http-tts-api.ts    (NEW) # implements TtsApi via /v1/voices, /v1/audio/speech, /v1/audio/stream
├─ http-transcribe-api.ts (NEW) # implements TranscribeApi via /v1/audio/transcriptions (verbose_json+word)
├─ http-clone-api.ts  (NEW, để dành) # implements CloneApi via /v1/audio/voices (ẩn sau flag, không dùng ở anon)
├─ api-context.tsx         # mở rộng: cung cấp ttsApi + transcribeApi + cloneApi; chọn mock|http theo env
├─ tts-api.ts / transcribe-api.ts / clone-api.ts   # interfaces giữ nguyên (contract UI)
└─ mock-*.ts               # giữ nguyên (dùng khi VITE_USE_MOCK=1, cho visual QA)

frontend/src/config/app-config.ts   # + features: { cloning:false }  (feature flags "ẩn cái BE chưa hỗ trợ")
frontend/vite.config.ts             # + server.proxy['/v1'] -> VITE_API_PROXY_TARGET (default http://127.0.0.1:8124)
```

**DRY:** UI chỉ phụ thuộc interface `TtsApi`/`TranscribeApi`/`CloneApi`. Đấu nối = inject bản `http*` ở `ApiProvider`. Bộ chunk phụ đề client-side (`src/lib/subtitle/`) giữ nguyên.

**QA harness (tái dùng):** đã có `frontend/e2e/` từ plan cũ (`capture-phase7.mjs`, `test-all-features.mjs`, `__screenshots__/`) — phase 6 mở rộng thành test-case độc lập; phase 7 tái dùng để chụp ma trận + `agy` vision (đã có trên PATH).

## Key decisions (đã chốt ở brainstorm phiên này)

- **Đường API:** dùng thẳng **`/v1`** (không alias `/api`). Base = `VITE_API_BASE` (mặc định `/v1`, same-origin prod; dev qua vite proxy).
- **Same-origin:** nginx serve SPA + proxy `/v1` cùng origin ⇒ **không cần CORS** ở `app/`. (Nếu sau này tách origin mới phải thêm CORS — ngoài scope.)
- **Cloning = ẩn:** BE clone CRUD **bắt buộc API key** và `/v1/voices` là **global** (mọi anon thấy/xoá clone của nhau) ⇒ **không an toàn** cho anon công khai khi chưa có auth + scope-per-user. Quyết định: **ẩn khu Cloning** (nav+route+picker group) sau `features.cloning=false`; giữ `http-clone-api.ts` + code UI để bật khi có auth.
- **Streaming:** `/v1/audio/stream` trả chunked MP3 **không có % progress** ⇒ đọc ReadableStream→Blob, hiển thị **progress indeterminate**, xong mới phát + Download. (MSE để pha sau nếu cần.)
- **ASR words:** BE trả `words` **top-level** khi `timestamp_granularities[]=word` ⇒ adapter **phân bổ words vào từng segment** theo overlap thời gian; rename `word→text`.
- **Ẩn field BE thiếu:** `/v1/voices` không có `gender`/`description` ⇒ **ẩn filter giới tính** + **bỏ mô tả** trên voice-card (fallback: dòng `language · engine`). VieNeu **bỏ qua `speed`** ⇒ **ẩn slider speed** khi engine=vieneu. `styles` rỗng ⇒ **ẩn style-select**. Affordance **TTS→SRT** trên result-card ⇒ **ẩn** (BE chưa verbatim).
- **Mock vẫn giữ:** `VITE_USE_MOCK=1` để chạy visual QA offline; mặc định (không cờ) = http thật.
- **Dùng bản mới nhất + web-search doc** khi cần (Vite proxy/env, fetch streaming ReadableStream, XHR upload progress).

## Skills áp dụng (nhúng theo phase)

| Skill | Dùng ở | Việc |
|---|---|---|
| `ak:frontend-development` | 1–4 | Patterns React/TS khi dựng adapter + context + flag |
| `ak:react-best-practices` | 1–4 | Context/hooks đúng chuẩn, không re-render thừa, cleanup objectURL, error boundary |
| `ak:docs-seeker` | 1,3,5 | Tra doc hiện hành: Vite `server.proxy`/env, fetch streaming, nginx `try_files` SPA |
| `ak:ui-ux-pro-max` | 4 | Nav còn 2 khu vẫn cân đối; empty/hidden state gọn gàng |
| `ak:deploy` / `ak:devops` | 5 | nginx serve SPA + proxy `/v1`, systemd/install-service, kiểm tra topology CF Tunnel |
| `ak:docs` | 5 | Cập nhật `docs/deployment.md` (build+serve dist, retire demo) |
| `ak:web-testing` | 6,7 | Playwright: e2e thao tác theo test-case + capture ma trận ảnh |
| `ak:test` | 6 | Chạy unit (map adapter, subtitle) + suite hiện có |
| subagent `tester` / `agy` CLI | 6 | Chạy **test-case độc lập** tự động (autonomous), tổng hợp pass/fail |
| **`agy` (Antigravity)** | 7 | **Vision review chính** — soi thẩm mỹ/AI-slop trên ảnh; fallback `ak:ai-multimodal` |
| `ak:code-review` | 6 | Review diff trước merge (bug/regression/leak objectURL) |

## Ports (giữ nguyên, tránh đụng)

- Backend: nginx **8123** (cửa công khai) → app **8124** (nội bộ, `.env` `PORT=8124`).
- FE dev: **5273** (`vite --port 5273 --strictPort`); e2e preview: **4273**.
- Vite dev proxy `/v1` → `VITE_API_PROXY_TARGET` (mặc định `http://127.0.0.1:8124`; đổi nếu app chạy port khác).

## Success Criteria (Acceptance)

- [ ] `frontend/` build & chạy: mặc định gọi `/v1` thật; `VITE_USE_MOCK=1` quay lại mock.
- [ ] **Voices thật**: `/v1/voices` render đủ giọng (map `model→engine`, lọc theo ngôn ngữ/engine + search hoạt động); **không** còn filter giới tính; voice-card không mô tả (fallback gọn).
- [ ] **Preview thật**: nút nghe thử phát audio từ `preview_url` (public, không key), single-instance.
- [ ] **TTS ngắn (≤1200)**: `/v1/audio/speech` → phát audio thật + Download đúng format; `model` gửi theo engine giọng chọn.
- [ ] **TTS dài (>1200)**: `/v1/audio/stream` → progress **indeterminate** → player + Download; không treo UI.
- [ ] **Style/speed đúng engine**: style-select chỉ hiện khi giọng có `styles`; speed ẩn với VieNeu; affordance TTS→SRT đã ẩn.
- [ ] **ASR thật**: upload → transcript segment+timestamp; `words` phân bổ đúng vào segment; **xuất SRT/VTT/TXT** vẫn đúng chuẩn (unit-test xanh); upload progress chạy, transcribe indeterminate.
- [ ] **Limit thật**: chạm 429/400/413 → hiện state VN/EN thân thiện (map từ envelope `code`); reserve-refund không tính oan.
- [ ] **Cloning ẩn**: không có nav `/clone`, deep-link `/clone` redirect an toàn, không có group "Giọng của bạn" ở picker; code clone còn nguyên sau flag.
- [ ] **Deploy + GO-LIVE**: nginx serve `frontend/dist`, deep-link `/transcribe` OK (SPA fallback), `/v1/*` proxy chạy; **`web/index.html` đã retire**; `docs/deployment.md` cập nhật; **`:8123` public phục vụ SPA thật** (sudo cp dist→/var/www/all-voice + nginx reload), **API :8124 + tunnel không gián đoạn**.
- [ ] **Functional QA**: unit map-adapter + subtitle xanh; **10 test-case e2e độc lập** chạy thật pass (do subagent `tester`/`agy` điều phối); `ak:code-review` không finding nghiêm trọng (đặc biệt rò rỉ objectURL).
- [ ] **Visual QA**: `agy` vision chạy trên ma trận ảnh **dữ liệu thật** (2 khu × 4 bp × 2 theme); vòng lặp tự sửa tới hội tụ (0 finding major) hoặc trần 4 vòng; report `plans/reports/visual-review-*.md`; không AI-slop/vỡ layout/cuộn ngang ở verdict cuối.

## Validation Log

### Verification Results (2026-08-31, Full tier — 7 phases)
- Claims checked: ~22 (paths/symbols/endpoints/schemas). Verified: 18 · Failed(→resolved): 2 · Detail-corrections: 3.
- **VERIFIED:** BE routers mount `/v1` (`app/main.py:165-170`); endpoints `/audio/speech` `/audio/stream` `/audio/transcriptions` `/voices` `/voices/{model}/{voice_id}/preview`. `VoiceInfo` **không có gender/description** (`app/schemas.py:153-166`: id,name,model,language,styles,preview_url,preview_base64). ASR `words` **top-level**, field `word` (`app/asr/transcriber.py:31,58-59,185-188`). `SynthRequest.response_format` = mp3/opus/aac/flac/wav/pcm (`schemas.py:38`), VieNeu bỏ speed (`schemas.py:45`). Router `/clone` + nav `/clone` tồn tại (`router.tsx:13`, `feature-nav.tsx:8`). Gender filter tồn tại (`use-voice-filters.ts:8-11`). SpeedSlider luôn render (`synth-controls.tsx:7`). Subtitle lib `frontend/src/lib/subtitle/*` tồn tại. Harness `frontend/e2e/*` + `agy` (PATH) tồn tại.
- **FAILED → RESOLVED:**
  - **F1** `limit-states.tsx` là **demo** (URL `?limit=rate|quota|too-long`), CHƯA nối lỗi API thật → **QĐ: refactor thành error-driven**.
  - **F2** `format-select.tsx` có `ogg` (BE không nhận) → **QĐ: chỉ mp3+wav**.
- **Detail-corrections (fold vào phase):** mobile nav hardcode `grid grid-cols-3` (`feature-nav.tsx:14`) → cols-2 khi ẩn clone; filter search dùng `voice.description` (`use-voice-filters.ts:10`) → bỏ khi bỏ description; `SynthControls` chưa nhận engine → cần truyền engine để gate speed. (`selection.tsx` không thấy nhóm clone ở picker → xác nhận khi impl.)

### Validation Answers (2026-08-31)
1. **Real-error UX (F1):** **Refactor `LimitStates` thành error-driven** — nhận `kind` từ lỗi thật (`rate|quota|too-long|overloaded|asr-too-long`), mount ở compose+transcribe, drive từ catch của `use-generate`/`use-transcribe`; tái dùng copy VN/EN; **bỏ demo `?limit=`**. → phase 1 (error-map keys), 2 (synth error), 3 (ASR 413).
2. **Format (F2):** **Chỉ mp3 + wav** — bỏ `ogg`; `AudioFormat` = `'mp3'|'wav'`. → phase 2, 4, types.ts.
3. **QA orchestration:** **Cả hai** — functional test-case độc lập qua **subagent `tester`** (phase 6) + visual/giao diện qua **`agy` CLI** vision (phase 7).
4. **Retire demo:** **Xoá hẳn `web/index.html`** + gỡ `tests/e2e/*` cũ, thay bằng e2e SPA (phase 5+6).

### Whole-Plan Consistency Sweep (2026-08-31)
Re-đọc plan.md + 7 phase: đồng bộ `/v1` base, port 8123/8124, streaming indeterminate, words→segment, cloning ẩn sau flag (code giữ), QA subagent+agy. Đã lan F1 (error-driven LimitStates) + F2 (mp3+wav) vào phase 1/2/3/4. **0 mâu thuẫn chưa giải quyết.**

## Run cadence (goal-warmup 2026-08-31 — Ready)

Autonomous "làm hết plan" 7 phases, tuần tự theo dependency. **Locked decisions:**
- **Branch:** ở nguyên `feat/tts-frontend-visual-shell` (commit theo từng phase, conventional, không AI refs).
- **Backend cho e2e/visual (phase 6-7):** dùng lại **uvicorn :8124 đang chạy** (anon đã bật) — proxy `/v1`→:8124; text ngắn để giới hạn CPU load lên prod.
- **GO-LIVE (phase 5, IN scope):** build `frontend/dist` → `sudo cp -r` vào `/var/www/all-voice/` → `sudo nginx -t && sudo systemctl reload nginx` (graceful). **KHÔNG** restart/kill uvicorn :8124 (không đổi backend code) và **KHÔNG** đụng cloudflared — dịch vụ live không gián đoạn.
- **Deferred tự chạy trong cook:** `npm ci` (đầu phase 1), `npx playwright install` (đầu phase 6).

**Scope guard (mỗi ranh giới phase):** đối chiếu việc làm với Contract; lệch vật chất → dừng hỏi user; không kết thúc dưới scope; không làm yếu test để đạt điều kiện dừng; **tuyệt đối không sửa `app/` backend, không kill :8124/cloudflared, không go-live nếu build/QA chưa xanh.**

## Open questions

1. **Dev proxy target**: app dev chạy `:8124` (theo `.env` `PORT`) hay `:8123` (default code)? → mặc định proxy `:8124`, cho override bằng `VITE_API_PROXY_TARGET`. Xác nhận khi chạy.
2. **Retire `web/index.html`**: xoá hẳn hay giữ file nhưng ngừng serve? → mặc định **xoá** sau khi grep chắc không còn tham chiếu (load-test/e2e cũ). Phase 5 kiểm trước.
3. **Voicevox voice string**: id giọng JP có dạng `VOICEVOX:...`? Dùng `voice.id` từ `/v1/voices` là đủ — xác nhận ở phase 2 khi gọi thật.

<!-- slug: real-model-integration -->

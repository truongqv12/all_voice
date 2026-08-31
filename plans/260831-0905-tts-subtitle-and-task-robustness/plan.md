---
title: "TTS Subtitle + Task-lâu Robustness — vá QA gap (preview, error-map, threshold 2000/20k, subtitle-kèm-voice, E2E+vision)"
description: "Hiện thực các quyết định đã chốt từ rà soát QA: subtitle-kèm-voice (ASR round-trip VI/EN + VOICEVOX native JP), ngưỡng ≤2000 buffered / >2000 stream / max 20k, thêm timeout+abort+retry+progress, sửa preview 404 (bỏ fallback giả) + error-map thiếu + race, gỡ nút sample giả; QA lại bằng E2E sub-agent thao tác + vision review kết quả."
status: completed
priority: P1
effort: "5-8d"
tags: [frontend, backend, tts, asr, subtitle, srt, streaming, robustness, timeout, abort, e2e, vision, qa]
created: 2026-08-31
blockedBy: []
---

# TTS Subtitle + Task-lâu Robustness

## Overview

Vá các khoảng trống phát hiện trong rà soát QA (báo cáo nguồn:
[`plans/reports/qa-260831-0840-tts-subtitle-review-testplan.md`](../reports/qa-260831-0840-tts-subtitle-review-testplan.md)).
Ba nhóm việc: **(A) tính năng mới** — tạo voice **kèm phụ đề**; **(B) độ bền task lâu** —
ngưỡng buffered/stream + timeout/abort/retry/progress; **(C) sửa defect + bỏ giả** —
preview 404, error-map thiếu mã, race đổi input, gỡ nút "sample" giả. Cuối cùng **QA lại**
bằng E2E do **sub-agent thao tác** trên backend thật + **vision review** ma trận ảnh kết quả.

Đây là bước tiếp sau `260831-0059-real-model-integration` (đã go-live SPA gọi `/v1` thật).
Plan đó chốt "không đụng backend"; **plan này CÓ CHỦ ĐÍCH mở lại một phần backend** (config
giới hạn ký tự + phơi mora-timing VOICEVOX) — ghi rõ ở Key decisions.

## Contract

- **Outcome:**
  1. Người dùng tạo voice **có thể xuất phụ đề .srt** kèm audio — VI/EN qua ASR
     round-trip (Whisper, kèm `prompt`=text gốc, "gần đúng"), JP qua VOICEVOX mora-timing native.
  2. Text tới **20.000 ký tự**: **≤2000 → buffered** (có cache), **>2000 → stream**;
     mọi task lâu có **progress rõ + timeout + nút hủy/retry**, không treo vô hạn.
  3. Preview nghe thử phát **đúng mẫu của từng voice** (bỏ fallback synth câu cứng);
     lỗi API hiện **đúng thông điệp** (audio-invalid, ASR-unavailable, quá dài, quá tải…).
  4. Gỡ nút "Thử âm thanh mẫu" giả; race đổi input/model không ghi đè kết quả sai.
  5. **Bộ E2E chạy lại** (sub-agent thao tác thật) + **vision review** xác nhận không vỡ UI/AI-slop.
- **Constraints:** giữ tương thích OpenAI + same-origin (không CORS); anon tier cho TTS+ASR;
  subtitle chunk **client-side** (tái dùng `frontend/src/lib/subtitle/*`); thay đổi backend **tối thiểu**
  và **không phá** endpoint/tương thích cũ; **không kill** uvicorn :8124/cloudflared đang live khi
  test — dùng backend dev riêng cho E2E; giữ `WORKERS=1` khi anon; KISS/DRY.
- **Non-goals:** verbatim-alignment nặng (MFA/WhisperX/torch) cho VI/EN; auth/login; clone per-user;
  MSE true-streaming (indeterminate/byte-progress là đủ); dịch (translate) trong ASR; thêm
  gender/description vào backend.
- **Acceptance:** xem "Success Criteria" cuối file + Success Criteria từng phase.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | FE task-lâu robustness: timeout + AbortController (hủy) + retry + progress rõ + requestId guard (race) + chống double-run | P1 |
| 2 | Giới hạn & ngưỡng: FE max 20k, ≤2000 buffered / >2000 stream (bỏ 120); BE nâng `anon_max_chars_buffered` 1200→2000 (stream đã verify hỗ trợ 20k — không sửa schema) | P1 |
| 3 | Sửa defect + bỏ giả: preview dùng `preview_url` thật (bỏ fallback) + fix voice-id map; error-map đủ mã (400 audio, 401, 404, 503-asr) sửa nhầm "overloaded"; gỡ nút sample fixture | P1 |
| 4 | Subtitle-kèm-voice **VI/EN** qua ASR round-trip (client orchestration, `prompt`=text gốc), bật `ttsToSrt`, UI "gần đúng" + progress | P1 |
| 5 | Subtitle-kèm-voice **JP** qua VOICEVOX mora-timing native (backend phơi timing; FE dùng thay round-trip) | P2 |
| 6 | E2E functional: bộ test-case (High trước) do **sub-agent `tester`** thao tác thật + unit cho logic mới | P1 |
| 7 | E2E Visual + **vision review** kết quả (đọc ảnh ma trận, soi AI-slop/vỡ layout, vòng lặp tự sửa) | P1 |

## Phases

| # | Phase | Status | Depends |
|---|-------|--------|---------|
| 1 | [FE task-lâu robustness (timeout/abort/retry/progress/race)](./phase-01-start.md) | Completed — unit + 9/9 e2e | — |
| 2 | [Giới hạn & ngưỡng 2000/20k (FE + BE)](./phase-02-limits-and-threshold.md) | Completed — backend + e2e verified | 1 |
| 3 | [Preview + error-map + gỡ sample giả](./phase-03-preview-errormap-remove-sample.md) | Completed — e2e + code-review verified | 1 |
| 4 | [Subtitle-kèm-voice VI/EN (ASR round-trip)](./phase-04-subtitle-with-voice-vi-en.md) | Completed — e2e + unit verified | 1, 2, 3 |
| 5 | [Subtitle-kèm-voice JP (VOICEVOX native)](./phase-05-subtitle-with-voice-jp-voicevox.md) | Completed — timing endpoint + cap + unit | 4 |
| 6 | [E2E functional QA — sub-agent thao tác](./phase-06-e2e-functional-qa-subagent.md) | Completed — 6/6 Playwright pass | 2, 3, 4, 5 |
| 7 | [E2E Visual + vision review](./phase-07-visual-vision-qa.md) | Completed — vision 0 major (3 defects fixed) | 6 |

## Architecture (điểm chạm)

```
FE (frontend/src)
├─ api/http-client.ts          # + timeout + AbortSignal truyền vào fetch/XHR (P1)
├─ api/error-map.ts            # + mã 400-audio/401/404; fix ưu tiên code trước status (503-asr) (P3)
├─ api/http-tts-api.ts         # getPreviewUrl dùng preview_url thật; synth/synthStream nhận signal; round-trip helper (P3,P4)
├─ api/http-transcribe-api.ts  # nhận signal; hỗ trợ prompt=text gốc (P4)
├─ features/compose/
│   ├─ use-generate.ts         # ngưỡng ≤2000 buffered / >2000 stream; requestId guard; abort (P1,P2)
│   ├─ use-audio-player.ts     # revoke objectURL (không rò)
│   ├─ progress-status.tsx     # nhãn giai đoạn + %/KB + spinner "đang xử lý" (P1)
│   ├─ audio-result-card.tsx   # nút "Xuất phụ đề" khi ttsToSrt bật + cảnh báo "gần đúng" (P4)
│   └─ use-generate-subtitle.ts (NEW) # orchestrate audio→transcribe(prompt)→chunk→srt (P4)
├─ features/transcribe/
│   ├─ use-transcribe.ts       # GỠ transcribeSample()/fixture; nhận abort (P1,P3)
│   └─ audio-drop-zone.tsx     # bỏ nút "Thử âm thanh mẫu" (P3)
├─ features/voice/use-voice-preview.ts # bỏ fallback synth; dùng preview_url; 404 → thông điệp rõ (P3)
├─ config/app-config.ts        # ttsToSrt: true (P4)
└─ lib/subtitle/*              # tái dùng chunk-cues/to-srt (subtitle-kèm-voice = chỉ SRT) (P4,P5)

BE (app)
├─ config.py                   # anon_max_chars_buffered 1200→2000 (P2) — thay đổi BE duy nhất của P2
│                              # (stream đã verify: StreamSpeechRequest không cap 4096 → 20k chạy sẵn)
└─ backends/voicevox_backend.py + routers # phơi mora-timing (accent_phrases) cho JP subtitle (P5)

E2E (frontend/e2e)
├─ functional.spec.ts          # + test-case mới (High trước) — sub-agent thao tác (P6)
└─ capture matrix + vision     # ảnh 2-3 khu × bp × theme × state → vision review (P7)
```

## Key decisions (chốt từ rà soát QA — user 31/08)

1. **Subtitle-kèm-voice = "gần đúng".** VI/EN: sinh audio → `POST /v1/audio/transcriptions`
   (`verbose_json`+`timestamp_granularities[]=word`, **`prompt`=text gốc** để bám chữ) → chunk
   client-side → **SRT** (chốt validation: chỉ SRT). Chấp nhận **không verbatim tuyệt đối** (đồng âm/tên riêng/số/cue).
   **VI/EN không cần endpoint BE mới** — orchestrate bằng endpoint sẵn có. JP dùng VOICEVOX native.
2. **Ngưỡng:** **≤2000 buffered · >2000 stream · max 20.000**. Bỏ mốc 120. BE chỉ cần
   `anon_max_chars_buffered=2000`. **Đã verify (31/08):** stream dùng `StreamSpeechRequest`
   không cap 4096 (`schemas.py:106`) → 20k chạy sẵn; buffered ≤2000 < 4096 nên không vướng.
3. **Preview:** dùng `preview_url` do `/v1/voices` cấp (đúng `{engine}/{id}`), **bỏ** fallback
   synth câu cứng; 404 thật → thông điệp "voice chưa có mẫu" (không xoay vô hạn).
4. **error-map:** thêm `invalid_audio_file`/`audio_file_too_large` (400), `preview_not_found` (404),
   `invalid_api_key` (401); **sửa** `asr_unavailable` (503) — ưu tiên khớp **code trước status** để
   không hiện nhầm "overloaded".
5. **Gỡ nút "Thử âm thanh mẫu"** (bỏ `transcribeSample()`/fixture) — nghiệm thu chỉ qua file thật.
6. **Task lâu:** thêm timeout (mặc định đề xuất 150s, cho override) + AbortController (hủy) +
   nút retry + progress giai đoạn; requestId guard chống race + double-run.
7. **Backend đụng tối thiểu, không phá tương thích.** Chỉ config giới hạn + timing VOICEVOX.
   Không đổi hợp đồng OpenAI của endpoint hiện có.

## Skills áp dụng (nhúng theo phase — "dùng skill hợp lý")

| Skill / Agent | Dùng ở | Việc |
|---|---|---|
| `ak:frontend-development` | 1–4 | React/TS: abort/timeout hooks, orchestration, UI state |
| `ak:react-best-practices` | 1–4 | cleanup objectURL/AbortController, tránh re-render, requestId guard |
| `ak:backend-development` | 2, 5 | config giới hạn; phơi mora-timing VOICEVOX không phá contract |
| `ak:docs-seeker` | 2, 4, 5 | doc hiện hành: fetch AbortSignal, XHR timeout, VOICEVOX Core `audio_query` |
| `ak:fix` | 3 | vá defect có root-cause (preview, error-map, race) |
| `ak:ui-ux-pro-max` | 4 | trạng thái "phụ đề gần đúng", progress, empty/disabled gọn |
| `ak:web-testing` | 6, 7 | Playwright test-case + capture ma trận ảnh |
| `ak:test` | 6 | chạy unit + suite |
| subagent `tester` | 6 | **thao tác từng test-case tự động**, tổng hợp pass/fail → report |
| `ak:ai-multimodal` / `agy` CLI | 7 | **vision review**: đọc ảnh kết quả, soi AI-slop/vỡ layout |
| `ak:code-review` | 6 | review diff trước merge (bug/regression/leak objectURL) |
| `ak:git` | mỗi phase | commit conventional, không AI refs |

## Ports (giữ nguyên, tránh đụng)

- Live: nginx **8123** (public) → app **8124** (anon, đang live — **không** kill khi test).
- E2E: backend dev riêng (vd `:8125` anon `--extra asr`) + FE preview **4273** proxy `/v1`; FE dev **5273**.

## Success Criteria (Acceptance tổng)

- [ ] **Subtitle VI/EN:** tạo voice → "Xuất phụ đề" → **SRT** có mốc giờ khớp audio; sub bám text gốc (nhờ prompt); có nhãn "gần đúng"; progress + timeout(150s) + hủy chạy.
- [ ] **Subtitle JP:** voice VOICEVOX → phụ đề từ mora-timing native (không round-trip), chính xác.
- [ ] **Ngưỡng:** ≤2000 buffered (có cache), >2000 stream; nhập tới 20000 chạy; 20001 chặn FE / 400 BE; không treo.
- [ ] **Task lâu:** đoạn dài có progress rõ; **timeout** → lỗi + **retry**; **hủy** dừng request (abort) + UI reset; race đổi input không ghi đè sai; double-click không tạo trùng.
- [ ] **Preview:** mọi voice trong `/v1/voices` nghe thử phát mẫu đúng (200), **không** ra cùng 1 câu cứng; 404 thật báo rõ.
- [ ] **error-map:** 400-audio/413/503-asr/401/404 hiện đúng thông điệp VN/EN (503-asr KHÔNG là "overloaded").
- [ ] **Sample:** không còn nút "Thử âm thanh mẫu"/nhánh fixture; transcribe chỉ qua file thật.
- [ ] **E2E functional:** bộ test-case High pass (sub-agent `tester` thao tác thật); unit logic mới xanh; `ak:code-review` không finding nghiêm trọng (không rò objectURL).
- [ ] **Visual/vision:** vision review ma trận ảnh (khu compose+transcribe × bp × theme × state gồm subtitle/progress/error) → 0 finding major hoặc trần vòng lặp; report `plans/reports/`.

## Validation Log

### Implementation status (2026-08-31)

- Phases 1–5 are implemented. Backend checks passed: `python -m compileall -q app`,
  `pytest -q tests/test_streaming.py -k 'not synth'` (10 passed), and
  `pytest -q tests/test_voicevox.py -k 'not synth'` (5 passed, 3 synth tests deselected).
- A temporary backend on `127.0.0.1:8125` was used only for health/OpenAPI checks;
  the live `:8124` process was untouched. The initial temporary server was stopped.
- Phase 6–7 remain pending because this environment has no `node`/`pnpm`, and the
  workspace policy denies access to frontend dependencies. Vitest, Playwright, and
  fresh visual captures therefore cannot be executed or honestly marked passed.

### E2E follow-up (2026-08-31)

- The NVM-managed Node 22 and pnpm runner were located and used. `pnpm test` passes
  (6 files, 15 tests), `pnpm build` passes, and Playwright functional QA passes 6/6
  against Vite `:5273` proxying the isolated backend `:8125`.
- The visual capture surfaced a real copy defect: the footer claimed every run used mock
  data. It now reflects the actual `VITE_USE_MOCK` adapter. The changed frontend has been
  rebuilt and unit-tested; a final full capture/vision verdict is still required.

### Verification Results (2026-08-31, Full tier — 7 phases)
- Claims checked: 10 chính (paths/symbols/endpoints/schemas). **Verified: 10 · Failed: 0 · Unverified: 0.**
- **VERIFIED:** `anon_max_chars_buffered=1200` (`config.py:64`), `anon_max_chars_stream=20_000` (`config.py:103`), `request_timeout_s=90` + `anon_max_concurrent_per_ip=2` (`config.py:68-70`); `SpeechRequest.input` max_length=4096 (`schemas.py:28`) **chỉ áp buffered**; `StreamSpeechRequest` riêng, `input` **không cap** (`schemas.py:106-120`) → stream nhận 20k không cần sửa; `speech_stream.py:59` áp trần theo `anon_max_chars_stream`; `prompt`→Whisper `initial_prompt` (`transcriptions.py:93-95,176`); `chunkCues` (`lib/subtitle/chunk-cues.ts:42`) + `distributeWords` (`http-transcribe-api.ts:6`, có test) tồn tại; `use-generate.ts` ngưỡng hiện `>120`; `ttsToSrt:false` (`app-config.ts:8`); `transcribeSample()` fixture (`use-transcribe.ts:38-48`); error-map hiện khớp status trước code (`error-map.ts`).
- **Tác động:** P2 backend thu về **1 thay đổi config** (buffered 1200→2000); stream 20k đã sẵn.

### Validation Answers (2026-08-31)
1. **Định dạng phụ đề: CHỈ SRT.** Subtitle-kèm-voice (mới) chỉ xuất `.srt`. *Lưu ý:* khu transcribe-từ-file hiện đã có SRT/VTT/TXT (code đang chạy) — **giữ nguyên**, không gỡ VTT/TXT (SRT là mặc định/chính). Nếu muốn gỡ hẳn VTT/TXT khỏi transcribe, báo lại (đây sẽ là giảm scope đang chạy). → phase 4, 5, 7.
2. **Timeout FE: 150s CHUNG** cho cả synth dài và ASR (không tách). → phase 1 (mặc định 150s), 4.
3. **JP fallback: CHO PHÉP.** Nếu VOICEVOX native (P5) tốn/khó → JP dùng ASR round-trip như VI/EN (nhãn "gần đúng"), đảm bảo JP luôn có sub. → phase 5 (nhánh rẽ = quyết định chính thức, không cần hỏi lại khi cook).

### Whole-Plan Consistency Sweep (2026-08-31)
Re-đọc plan.md + 7 phase: đồng bộ ngưỡng 2000/20k, SRT-only (subtitle mới), timeout 150s chung, JP fallback cho phép, backend đụng tối thiểu (chỉ config buffered), E2E dùng :8125 dev không đụng :8124 live. **0 mâu thuẫn chưa giải quyết.**

### Completion — "làm tiếp" session (2026-08-31)
Codex thực thi P1–P6 (hết limit giữa P7, chưa commit). Session này review + hoàn tất:
- **Verify độc lập:** backend `pytest` streaming 10/10 + voicevox 5/5; frontend `tsc -b` sạch + vitest 15/15; Playwright **9/9** (6 functional + 3 visual-states, self-mocked, KHÔNG đụng :8124 live).
- **Code-review toàn diff** (subagent): 0 Critical/High, 1 Medium + 6 Low → [`reports/code-review-260831-1058-tts-subtitle-remaining.md`](../reports/code-review-260831-1058-tts-subtitle-remaining.md).
- **P7 vision** (multimodal; `agy` bị chặn permission → fallback): **0 major**; sửa 3 defect → [`reports/visual-review-260831-tts-subtitle-phase7.md`](../reports/visual-review-260831-tts-subtitle-phase7.md).
- **Sửa trong session:** (1) i18n `compose.error` "bản mẫu/prototype"→"giọng nói/speech"; (2) i18n `compose.result` "Kết quả mẫu/Sample result"→"Kết quả/Result"; (3) M1: `speech_timing` thêm trần input `anon_max_chars_stream` (KHÔNG reserve_chars để tránh tính phí 2 lần cho phụ đề JP); (4) L1 xoá `}` thừa trong className `audio-drop-zone`; (5) L2 preview `fetch` thêm timeout 20s (chống xoay vô hạn); (6) sửa selector strict-mode trong `visual-states.spec`.
- **Non-issue (không sửa):** thẻ voice rỗng dưới màn desktop full-page = artifact của `content-visibility:auto` (`voice-card.tsx:30`, tối ưu có chủ đích commit 1376844); user cuộn vẫn render bình thường.
- **Còn để user quyết (không chặn):** (a) chuỗi "mẫu/bản mẫu/dữ liệu mẫu" còn lại (`transcribe.sampleData`, `compose.mp3Preview`, `compose.hardLimit`, `compose.fileError`, `compose.emptyHint`) — đúng ở chế độ mock, dễ gây hiểu nhầm ở chế độ thật; (b) M1 budget: timing endpoint chưa trừ hạn ký tự/ngày (đã chặn theo rate+concurrency+trần input) — trừ budget sẽ tính phí 2 lần cho phụ đề JP.

## Open questions

- **(nhỏ, không chặn)** Có gỡ hẳn VTT/TXT khỏi khu transcribe-từ-file không? Mặc định: **giữ** (SRT là chính) — chỉ gỡ nếu user yêu cầu (giảm scope đang chạy).
- **(nhỏ, product-intent)** Gỡ/đổi context-aware chuỗi "mẫu" còn lại (xem Completion §còn để user quyết) cho deployment thật?
- **(nhỏ, chi phí)** Có siết budget ký tự cho `/v1/audio/speech/timing` không (đánh đổi: tính phí 2 lần cho phụ đề JP)?

<!-- slug: tts-subtitle-and-task-robustness -->

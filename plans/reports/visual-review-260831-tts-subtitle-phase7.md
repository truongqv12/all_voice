# Visual review — TTS subtitle / task robustness (P7 final)

Date: 2026-08-31 (finalized — dynamic states + vision verdict)
Reviewer: in-session multimodal review (agy CLI present but blocked by permission classifier on `--dangerously-skip-permissions`; used plan P7's ai-multimodal fallback).

## Evidence
- Static matrix: `pnpm --dir frontend e2e:capture` → 40 PNG under `frontend/e2e/__screenshots__/phase7/` (compose empty/filled/result, transcribe empty/result) × 375/768/1024/1440 × light/dark. Programmatic horizontal-overflow assertion passed.
- Dynamic states (route-intercept, no backend): `visual-states.spec.ts` via `E2E_BASE_URL=http://127.0.0.1:5273 playwright test --config e2e/playwright.config.ts visual-states` → 3/3 pass:
  `tts-progress__375__light.png` (synth in-flight), `tts-error__375__light.png` (503 overloaded), `subtitle-progress__375__light.png` (subtitle generating).
- Direct image inspection: the 3 dynamic states + `tts-result__375__light`, `tts-result__1440__light`, `transcribe-result__375__dark`.

## Findings + fixes
1. **[fixed] i18n `compose.error`** — was "Không thể tạo **bản mẫu**." / "The **prototype** could not generate speech." — wrong demo/prototype wording for TTS. → "Không thể tạo giọng nói. Hãy thử lại." / "Could not generate speech. Try again." (vi/en).
2. **[fixed] i18n `compose.result`** (result-card title) — was "Kết quả **mẫu**" / "**Sample** result" — mislabels real output as a sample (same class as the footer bug fixed earlier). → "Kết quả" / "Result". Verified rendered in re-captured `subtitle-progress`.
3. **[fixed] test bug** `visual-states.spec.ts` — `getByRole('alert')` matched 2 alerts (strict-mode violation) → `.first()`. The error UI itself is correct: amber specific "Dịch vụ đang quá tải" + red retry prompt + "Thử lại" button.

## Non-issues (documented, not changed)
- **Empty voice-cards below the fold on full-page desktop captures** = artifact of `content-visibility: auto` + `contain-intrinsic-size:140px` in `voice-card.tsx:30` (the verified-intentional "optimize voicevox rendering" work, commit 1376844). Off-screen cards defer paint; a real user scrolling sees them render normally. Not a user-facing defect. Consequence: full-page screenshots cannot vision-QA the whole voice list below the fold.

## State clarity verdict (mobile 375 + desktop 1440, light + dark)
- **Progress:** disabled "Đang tạo" + spinner + "Hủy" + progress bar with stage labels — clear.
- **Error:** specific limit reason (amber) + generic retry prompt (red) + "Thử lại" — clear; no overflow.
- **Subtitle generating:** "gần đúng" caveat + chars/line + lines/cue + "Đang tạo phụ đề…" + Hủy — clear.
- **Result / transcribe (light+dark):** no overflow, clipping, contrast, or hierarchy defect; dark theme legible.
- **Timeout:** renders via the same error alert with kind=`timeout`; not separately screenshotted (needs 150s live wait).

## VERDICT
**MAJOR defects: 0.** 3 real defects found and fixed (2 i18n copy, 1 test). 1 non-issue documented.

## Limitation
Dynamic-state captures are mobile/light only (highest overflow risk); static matrix covers 4 breakpoints × 2 themes for idle/filled/result. Full-page desktop captures under-render the voice list due to `content-visibility:auto` (see non-issues).

# Code Review — TTS Subtitle + Task Robustness (plan 260831-0905)

Scope: full uncommitted diff (48 tracked files + 5 untracked). Read-only review.
Verification: `tsc -b` PASS (exit 0); `pnpm test --run` 6 files / 15 tests PASS;
new backend units `test_accent_phrases_to_cues_uses_mora_pause_and_speed` +
`test_stream_forwards_native_speed_to_every_chunk` PASS. i18n en/vi symmetric,
all `limits.*`/subtitle/footer keys present (JSON is flat dotted keys).

Verdict: no Critical/High correctness defects. Robustness, error-map, preview,
subtitle (VI/EN ASR + JP VOICEVOX native), threshold 2000/20k all implemented and
match plan intent. Findings below are Medium/Low.

## Focus-list confirmation (plan vs source)
- P1 timeout/abort/retry/progress/requestId/double-run: PRESENT and correct.
  - `http-client.ts` 150s default; timeout+external signal composed via
    `createRequestAbort`; deadline spans body read (apiJson/apiBlob own the abort,
    dispose after `res.json()/blob()`); http-client.test covers timeout during
    stream body. AbortSignal wired to fetch (fetch path) AND XHR (transcribe path,
    `xhr.abort()` on signal + timeout). Stale `requestId` results discarded.
    Double-run guarded by synchronous `running.current` set before first await.
- P2 threshold: `use-generate.ts` `>2000 → synthStream` else `synth` (no 120);
  `limits.ts` hard=20000; `config.py:64 anon_max_chars_buffered=2000`; buffered
  router still caps at `anon_max_chars_buffered`, stream at `anon_max_chars_stream`.
  Backend OpenAI contract unchanged.
- P3 preview/error-map/sample: `use-voice-preview.ts` fetches real `preview_url`
  (synth-fallback removed), 404→`preview_not_found`; `error-map.ts` matches `code`
  BEFORE `status` (503 `asr_unavailable` → `asr-unavailable`, NOT overloaded), adds
  400 invalid_audio_file/audio_file_too_large, 401 invalid_api_key, 404
  preview_not_found, timeout; sample button + `transcribeSample()`/`onSample`
  removed (tsc confirms no dangling refs). All codes match backend emitters.
- P4/P5 subtitle: `use-generate-subtitle.ts` SRT-only, `prompt`=original text
  forwarded to transcribe, VOICEVOX→`getSpeechTiming` native branch;
  `speech_timing.py` is a SEPARATE `/v1/audio/speech/timing` route (does not touch
  `/v1/audio/speech`), 400 timing_not_supported / 404 unknown_voice / 503
  timing_unavailable; mora math (consonant+vowel, pause_mora, pre/post silence,
  speedScale) verified by unit + hand calc (start=pre/speed, end+=post/speed).

## Medium

### M1 — `/v1/audio/speech/timing` bypasses the daily char budget
File: `app/routers/speech_timing.py:30-37`
The timing route gates with `quota.allow_rate` (rate) + `admit` (2-concurrent) but
never reserves the per-IP daily char budget, unlike `/audio/speech`
(`speech.py`) and `/audio/stream` (`streaming.py`, commit-as-you-yield). It runs
real work: `backend.subtitle_timing` → OpenJTalk full-text analysis + accent
estimation for up to 20 000 chars (schema cap), plus lazy VVM load into RAM.
Failure scenario: an anon client spams `/audio/speech/timing` with 20k JP text;
each call burns non-trivial CPU on the shared 1-worker box without depleting its
daily budget, degrading live synthesis. Bounded by rate-limit + admission, so not
Critical, but it is an asymmetric budget-free CPU path.
Fix: reserve a char cost in the timing route for anon (e.g.
`quota.reserve_chars(ip, len(req.input), settings)` with refund on failure), or
cap timing `input` smaller than the synth path, or require the caller to have just
synthesized (not enforceable statelessly). Simplest: charge the budget.

## Low

### L1 — Stray literal `}` in AudioDropZone className
File: `frontend/src/features/transcribe/audio-drop-zone.tsx:33-38`
The template literal appends `... ${disabled ? '…' : ''}\n      }` — a trailing
`}` char lands in the class string as a garbage token. Harmless (matches no class)
but sloppy; passes tsc/lint because className is an opaque string.
Fix: drop the stray `}` before the closing backtick.

### L2 — Preview fetch has no timeout/abort
File: `frontend/src/features/voice/use-voice-preview.ts:35`
`await fetch(src)` in `playAudioSrc` passes no AbortSignal and no timeout. Toggling
increments `request.current` but cannot cancel the in-flight GET (self-heals only
when it resolves). A hung preview endpoint leaves `loadingId` spinning until the
user toggles another voice — a mild miss vs the plan's "no infinite spin" goal.
404 returns fast, so real-world impact is small.
Fix: route preview through `apiFetch`/`apiBlob` (already carry timeout+abort) or
pass an AbortController tied to `request.current`.

### L3 — Double ownership of result objectURL revocation
Files: `frontend/src/features/compose/use-generate.ts:21-23` (`discard`) and
`frontend/src/features/compose/audio-result-card.tsx:20-26` (unmount effect).
Both revoke `result.audioUrl`. On regenerate/reset/unmount the same blob URL is
revoked twice. `URL.revokeObjectURL` is idempotent so this is harmless today, but
two owners of one lifecycle is fragile — a future change that recreates the URL
between the two revokes could revoke the live one.
Fix: pick a single owner (keep `use-generate.discard`; drop the card effect, or
vice-versa).

### L4 — compose-panel cancel-on-input-change effect depends on unstable `job`
File: `frontend/src/features/compose/compose-panel.tsx:28-34`
`useGenerate()` returns a fresh object each render, so `job` in the dep array makes
the effect run every render. Behavior is correct (early-returns when not
generating) but it is needless churn / a code smell.
Fix: depend on `job.state`, `job.lastParams`, `job.cancel` instead of `job`.

### L5 — char length uses UTF-16 units vs backend code points
Files: `text-editor.tsx:6` (`maxLength=20000`), `use-generate.ts:38`
(`text.length > 2000`) vs backend `len()` (code points, `schemas.py:161`,
`config.py`). Non-BMP input (emoji, rare CJK) counts double on FE, so FE could
block or mis-route text the backend would accept and vice-versa. Negligible for
VI/EN/JP prose. No fix needed unless emoji-heavy input is expected.

### L6 — dead i18n keys / unused string after sample removal
`transcribe.trySample`, `transcribe.sampleData`, `compose.subtitleSoon` remain in
en/vi locales but are no longer referenced. Cosmetic cleanup only.

## Not defects (checked)
- error-map ordering: `switch(code)` runs before `status` fallbacks — 503
  asr_unavailable correctly returns `asr-unavailable`, not `overloaded`. Verified
  + covered by error-map.test additions.
- VOICEVOX streaming timing offset accumulation (`voicevox_backend.py:157-170`):
  offset += last-cue end (full chunk duration incl. pre/post silence) matches
  back-to-back MP3 chunk concatenation in `synth_stream`.
- buffered vs stream timing parity: speed=1.0 buffered uses `synth.tts` (default
  query); timing uses `make_query` (same defaults) → pre/post/mora identical.
- mock adapter implements new `getSpeechTiming` (interface change safe); tsc PASS.
- objectURL leaks: synth/synthStream create URL only after body resolves (no leak
  on abort); stale results `discard`ed; transcribe `replaceUrl` revokes prior.

## Not run
- Playwright e2e (`functional.spec.ts` rewrite, `visual-states.spec.ts` new): not
  executed (no browser launch in this review); plan records 6/6 passing.

## Metrics
- tsc: 0 errors. vitest: 15/15 pass. New backend units: 2/2 pass.
- i18n: en/vi symmetric, 0 missing keys for rendered LimitKind/subtitle/footer.

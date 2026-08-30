# Visual review checkpoint after phase 3

## Round 1

- Capture: 8 screenshots, `tts-core__{375,768,1024,1440}__{light,dark}.png`.
- Evidence: Playwright rejected horizontal overflow before every capture.
- `agy` result: 4 critical overlay findings at 375/768; 2 major voice-sidebar clipping findings at 1024; remaining findings minor.
- Repairs: replaced fixed mobile navigation with non-overlapping mobile nav in normal layout flow; changed the constrained voice sidebar to a single-card column; shortened search placeholder; hid redundant desktop selected-voice chip.
- Next: recapture and repeat the same vision rubric. The gate passes only with no major/critical finding.

## Round 2

- Capture: the same 8 breakpoint × theme renders after the repair; Playwright again rejected horizontal overflow before capture.
- `agy` result: **0 critical and 0 major** findings. The remaining eight notes are minor polish only.
- Verdict: checkpoint after phase 3 **converged in 2 of 4 maximum rounds**. It is safe to continue to phases 4–7.

## Round 3 (post-review repairs)

- Repair scope: injectable voice catalog/selection, model-to-language filter synchronization, audio ownership coordination, explicit MP3 mock-result disclosure, localized sheet close label, Blob download, and embedded `.txt` drop target.
- Capture: same 8 renders; Playwright found no horizontal overflow.
- `agy` result: **0 critical and 0 major** findings. Remaining notes are minor polish only.
- Verdict remains converged, now re-verified after the nonvisual repairs, in 3 of 4 maximum rounds.

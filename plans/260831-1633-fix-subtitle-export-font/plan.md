---
title: "Sửa luồng tạo và xuất phụ đề"
status: completed
priority: P1
created: 2026-08-31
---

# Sửa luồng tạo và xuất phụ đề

## Outcome

Luồng TTS/transcription không còn nội dung mẫu giả; người dùng chọn rõ **theo dòng** hoặc **từng từ**; file SRT/VTT/TXT tải xuống giữ đúng tiếng Việt/Unicode trên trình đọc phổ biến.

## Constraints

- Giữ nguyên API backend và các định dạng SRT/VTT/TXT hiện có.
- Không đụng tới "mẫu giọng" của cloning hoặc fixture chỉ dùng cho test/mock nội bộ.
- Không ghi đè thay đổi đang có ở nhánh `feat/live-usage-stats`.

## Non-goals

- Không thay engine ASR/TTS, thuật toán alignment hay định dạng subtitle mới.
- Không commit, push, mở/merge PR.

## Root causes

- `audio-drop-zone.tsx` bị commit `62072e0` thêm lại nút `mock-sample.mp3`; `compose-panel.tsx` vẫn có quick-fill mẫu.
- `chunk-cues.ts` cho `sentence` gọi lại nhánh `word`, còn `word` vẫn gom nhiều từ nên hai lựa chọn không đúng contract.
- Hai đường download không thêm UTF-8 BOM; màn transcription còn gắn SRT MIME `text/vtt`.

## Phases

| # | Phase | Status | Dependency |
|---|-------|--------|------------|
| 1 | [Gỡ affordance mẫu](./phase-01-remove-default-sample-affordances.md) | Completed | — |
| 2 | [Chế độ line/word + UTF-8](./phase-02-subtitle-modes-and-encoding.md) | Completed | 1 |
| 3 | [Test, build, visual QA](./phase-03-verification-and-visual-qa.md) | Completed | 2 |

## Acceptance criteria

- [x] Không còn nút âm thanh mẫu, quick-fill mẫu hay copy sample trong TTS/transcription production UI.
- [x] `line` tạo cue nhiều từ có wrap; `word` tạo đúng một cue cho mỗi word timestamp.
- [x] Cả TTS subtitle và transcription export đều có bộ chọn line/word.
- [x] File tải xuống bắt đầu bằng UTF-8 BOM, MIME đúng theo format và giữ nguyên Unicode.
- [x] Unit tests, frontend build và browser smoke/visual check đều xanh.

<!-- slug: fix-subtitle-export-font -->

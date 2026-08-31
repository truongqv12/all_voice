# Phase 2: Chế độ line/word và UTF-8

## Context links

- `frontend/src/lib/subtitle/{conventions,chunk-cues}.ts`
- `frontend/src/features/{compose/audio-result-card,compose/use-generate-subtitle,transcribe/subtitle-export-panel}.tsx`
- `frontend/src/lib/download.ts`

## Overview

Priority P1 · Completed. Sửa contract granularity thành `line | word`, đưa bộ chọn vào cả hai luồng và chuẩn hóa download Unicode.

## Key insights / requirements

- `line`: giữ thuật toán gom/wrap hiện tại.
- `word`: mỗi timestamp word tạo một cue, không kéo dài theo min cue khiến cue chồng nhau.
- VOICEVOX line dùng timing native; word dùng ASR round-trip vì accent phrase không phải word.
- Blob download dùng UTF-8 BOM và MIME đúng: SRT `application/x-subrip`, VTT `text/vtt`, TXT `text/plain`.

## Implementation steps

1. Đổi type/default và tách rõ hai nhánh trong `chunkCues`.
2. Cập nhật selector + i18n ở transcription và TTS result card.
3. Điều phối VOICEVOX theo mode, giữ VI/EN flow hiện tại.
4. Dùng chung helper download text trong `download.ts`, không lặp Blob logic.
5. Thêm regression tests cho line, word và bytes BOM/Unicode.

## Todo / success criteria

- [x] Hai mode cho output khác nhau và đúng timestamp.
- [x] Preview thay đổi theo mode; file Unicode mở không lỗi dấu.

## Risks / security

Word mode tạo nhiều cue/file lớn hơn; vẫn bị chặn bởi giới hạn input hiện có. Không đưa nội dung text ra ngoài flow ASR hiện hành.

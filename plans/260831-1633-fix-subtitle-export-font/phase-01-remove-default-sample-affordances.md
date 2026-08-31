# Phase 1: Gỡ affordance mẫu

## Context links

- `frontend/src/features/compose/compose-panel.tsx`
- `frontend/src/features/transcribe/audio-drop-zone.tsx`
- `frontend/src/i18n/locales/{vi,en}.json`

## Overview

Priority P1 · Completed. Gỡ nội dung mẫu giả khỏi hai luồng tạo giọng và transcription, giữ mock/test fixture nội bộ và mẫu giọng cloning.

## Requirements and architecture

- TTS chỉ nhận text người dùng hoặc file text; transcription chỉ nhận file người dùng.
- Xóa key i18n không còn caller để tránh sample affordance quay lại ngoài ý muốn.

## Implementation steps

1. Xóa quick-fill buttons khỏi `ComposePanel`.
2. Xóa nút fetch `mock-sample.mp3` khỏi `AudioDropZone`.
3. Xóa copy/key sample không còn dùng trong phạm vi TTS/transcription.
4. Grep caller để xác nhận không còn dangling key.

## Todo / success criteria

- [x] Không còn affordance mẫu trên `/` và `/transcribe`.
- [x] Clone sample và dev mock adapter không thay đổi.

## Risk and security

Rủi ro thấp; không thay API hay dữ liệu. Không fetch asset ngầm từ thao tác người dùng nữa.

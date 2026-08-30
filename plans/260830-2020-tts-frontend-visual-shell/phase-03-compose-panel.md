---
title: "Phase 3: Compose Panel + mock generate"
status: done
---

# Phase 3: Compose Panel + mock generate flow

## Overview
Dựng khu **soạn & tạo**: editor + upload `.txt` + char counter, cụm controls (model/style/speed/format), nút Tạo, progress, và audio result card. Nối **luồng tạo giả lập** end-to-end (buffered vs stream theo độ dài) → player + Download + Tạo lại.

## Requirements
- Functional: nhập text hoặc thả `.txt` → nạp editor; counter live + cảnh báo giới hạn (soft 1200 / hard 20000, theo tier anon mock); controls phản ánh `styles` của giọng đang chọn; speed 0.25–4.0; format mặc định MP3; Tạo → progress → player nghe + Download + Tạo lại.
- Non-functional: progress **thật giả lập** (không spinner trần); nút đổi nhãn khi tạo; disable hợp lý; mobile-first (controls xếp gọn).

## Architecture
- `useGenerate`: chọn đường theo độ dài — `synth` (buffered, progress indeterminate→done) vs `synthStream` (stream, progress theo % chunk giả lập ~3s). Mock trả URL sample mp3. Quản state `idle|generating|success|error`.
- `useAudioPlayer`: điều khiển `<audio>` kết quả (play/seek/time), tách khỏi audio preview (phase 2).
- `CharCounter`: đọc giới hạn từ config tier (mock); >1200 → badge "chuyển stream-mode"; >20000 → chặn Tạo + gợi ý.
- `SynthControls`: `ModelSelect` (đồng bộ với ngôn ngữ đang lọc), `StyleSelect` (động theo `selectedVoice.styles`), `SpeedSlider`, `FormatSelect`.
- `FileDropZone`: kéo-thả **đè** editor (không phải bước riêng); chỉ `.txt` giai đoạn này; báo lỗi định dạng inline.
- Kết quả tải về: tạo `Blob`/objectURL cho Download (đặt tên file theo giọng + thời gian).

## Related Code Files
- Create: `frontend/src/features/compose/compose-panel.tsx`, `text-editor.tsx`, `char-counter.tsx`, `file-drop-zone.tsx`, `synth-controls.tsx`, `model-select.tsx`, `style-select.tsx`, `speed-slider.tsx`, `format-select.tsx`, `generate-button.tsx`, `progress-status.tsx`, `audio-result-card.tsx`
- Create: `frontend/src/features/compose/use-generate.ts`, `use-audio-player.ts`
- Create: `frontend/src/lib/limits.ts` (hằng giới hạn tier mock), `frontend/src/lib/download.ts`
- Modify: `frontend/src/features/tts/tts-page.tsx` (mount ComposePanel slot trái), `frontend/src/api/mock-tts-api.ts` (synth/synthStream giả lập progress), `frontend/src/i18n/locales/*`

## Implementation Steps
1. `TextEditor` auto-grow + placeholder hướng dẫn; `CharCounter` màu ok/warn/over.
2. `FileDropZone` đè editor: đọc `.txt` → set value; lỗi định dạng → inline.
3. `SynthControls`: ModelSelect ↔ ngôn ngữ; StyleSelect động theo giọng; SpeedSlider 0.25–4.0 (bước 0.05, nhãn 1.0x); FormatSelect (MP3 mặc định).
4. `mock synth/synthStream`: phát progress qua callback/AsyncIterator; buffered = pulse→done, stream = %.
5. `GenerateButton`: nhãn "Tạo giọng nói"→"Đang tạo…"→✓; disable khi rỗng/quá hạn/đang tạo.
6. `ProgressStatus`: bar % (stream) / animate (buffered) + nhãn; reduced-motion an toàn.
7. `AudioResultCard`: `<audio controls>` + Download + Tạo lại; xuất hiện inline dưới nút. Kèm affordance **"Xuất phụ đề .srt (thử nghiệm)"** đánh dấu rõ *sắp có* — mock/disabled + tooltip trỏ sang khu Speech-to-Text; TTS→SRT verbatim là follow-on backend (xem `plans/reports/research-260830-srt-subtitle-export.md`), **không** hiện thực ở plan này.
8. Nối `useGenerate`+`useAudioPlayer`; ráp `ComposePanel` với `SelectedVoiceChip` (phase 2) ở đầu.

## Success Criteria
- [ ] Nhập/thả `.txt` nạp editor; counter cảnh báo đúng ngưỡng; >20k chặn Tạo + gợi ý.
- [ ] Controls phản ánh giọng đang chọn (styles đổi theo giọng); speed/format đổi được.
- [ ] Tạo → progress (buffered vs stream) → player phát + Download tải file + Tạo lại.
- [ ] Nút đổi nhãn theo trạng thái; disable hợp lý; audio result tách biệt preview.
- [ ] Mobile: controls + editor + result xếp gọn, thao tác tốt bằng ngón tay (≥44px).

## Risk Assessment
- **Text dài chặn UI** khi giả lập. Mitigation: progress qua async, không block main thread.
- **Preview vs result audio đá nhau**. Mitigation: 2 instance tách biệt; bắt đầu 1 loại thì dừng loại kia.
- **Speed slider khó chạm mobile**. Mitigation: Radix Slider hit-area ≥44px, nhãn giá trị rõ; tabular-nums.
- **Giới hạn tier hard-code lệch backend thật**. Signal: khi tích hợp thấy số khác. Response: đặt tất cả ngưỡng trong `lib/limits.ts` để đổi 1 chỗ.

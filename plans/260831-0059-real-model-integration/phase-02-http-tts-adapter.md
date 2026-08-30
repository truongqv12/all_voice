---
phase: 2
title: "http-tts-adapter (voices / preview / synth / stream)"
status: pending
priority: P1
effort: "1-1.5d"
dependencies: [1]
---

# Phase 2: http-tts-adapter

## Overview

Điền `http-tts-api.ts` implement đủ interface `TtsApi` bằng endpoint thật: `GET /v1/voices`, `preview_url`, `POST /v1/audio/speech` (buffered), `POST /v1/audio/stream` (chunked MP3, progress indeterminate). Map `model→engine`; suy ra `model` khi synth từ giọng đang chọn (cache voices trong adapter — **không đổi contract component**).

Skills: `ak:frontend-development`, `ak:react-best-practices` (cleanup `URL.revokeObjectURL`).

## Requirements

- Functional:
  - `listVoices()`: `GET /v1/voices` → map mỗi item `{id,name,model,language,styles,preview_url}` sang `Voice{id,name,language,engine:model,gender:'neutral',styles,description:'',previewUrl}`. Cache `id→{engine,styles,previewUrl}` trong module để `synth`/`getPreviewUrl` tra cứu.
  - `getPreviewUrl(voice)`: trả `voice.previewUrl` (nếu có) hoặc `${BASE}/voices/${engine}/${id}/preview`. Public, không key.
  - `synth(params)`: `POST /v1/audio/speech` JSON `{model, input:text, voice:voiceId, response_format:format, speed, style?}` → nhận **Blob** (`audio/*`) → `URL.createObjectURL` = `audioUrl`; `filename = all-voice-${voiceId}.${format}`; `previewOnly:false`. `model` = engine tra từ cache; `style` chỉ gửi khi giọng có styles.
  - `synthStream(params, onProgress)`: `POST /v1/audio/stream` JSON `{model,input,voice,style?}` → đọc `res.body` ReadableStream, gom chunks → `Blob(type audio/mpeg)` → objectURL. Progress **indeterminate** (không có total): gọi `onProgress` theo cột mốc byte hoặc để UI hiện indeterminate; trả `SynthResult{previewOnly:false}`.
  - Lỗi: bắt `ApiError` → ném tiếp cho `use-generate`; `use-generate` gọi `mapError` → set `kind` cho `LimitStates` (**[F1]** error-driven, 429→rate/quota, 400 input_too_long→too-long, server_overloaded→overloaded); non-limit → state 'error' generic.
- Non-functional: revoke objectURL cũ khi tạo mới / unmount (tránh rò rỉ); không chặn UI khi stream dài; giữ single-instance preview (đã có coordinator).

## Architecture

- **Suy ra `model`:** `SynthParams` chỉ có `voiceId`; adapter giữ `voiceCache: Map<id, {engine, styles, previewUrl}>` nạp ở `listVoices()`. `synth`/`synthStream` tra `engine` từ cache; nếu miss (reload trực tiếp) → gọi `listVoices()` lười 1 lần rồi tra lại; fallback `model` bỏ trống để BE dùng default. **Không đổi interface `TtsApi`/`SynthParams`.**
- **Style hợp lệ:** chỉ đính `style` vào payload khi `styles` của giọng chứa giá trị đang chọn; tránh 400 "invalid style".
- **Streaming reader:**
  ```ts
  const res = await apiFetch('/audio/stream', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload)})
  if (!res.ok) throw await toApiError(res)
  const reader = res.body!.getReader(); const chunks: Uint8Array[] = []; let received = 0
  onProgress(0) // indeterminate marker (UI dựa cờ, không phải %)
  for (;;) { const {done, value} = await reader.read(); if (done) break; chunks.push(value); received += value.length; onProgress(received) }
  const blob = new Blob(chunks, {type:'audio/mpeg'})
  return { audioUrl: URL.createObjectURL(blob), filename: `all-voice-${voiceId}.mp3`, previewOnly:false }
  ```
  → **progress-status** hiển thị indeterminate (xem "UI touch" dưới).
- **UI touch (nhỏ, thuộc scope streaming):**
  - `use-generate.ts`: nhánh >1200 đặt cờ indeterminate thay vì `progress:0..100`.
  - `progress-status.tsx`: thêm nhánh render **thanh indeterminate** (animation, tôn trọng `prefers-reduced-motion`) khi ở stream-mode.
  - `audio-result-card.tsx`: revoke objectURL khi thay/gỡ; **ẩn affordance TTS→SRT** (chuyển qua phase 4 nếu affordance nằm chung file — ghi rõ ở đây để không quên).

## Related Code Files

- Modify: `frontend/src/api/http-tts-api.ts` (implement đầy đủ)
- Modify: `frontend/src/api/types.ts` (đảm bảo `previewUrl?` đã thêm ở phase 1)
- Modify: `frontend/src/features/compose/use-generate.ts` (cờ indeterminate cho stream)
- Modify: `frontend/src/features/compose/progress-status.tsx` (render indeterminate)
- Modify: `frontend/src/features/compose/audio-result-card.tsx` (revoke objectURL)
- Modify: `frontend/src/features/voice/use-voice-preview.ts` (nếu cần dùng `previewUrl` trực tiếp)

## Implementation Steps

1. Implement `listVoices()` + `voiceCache`.
2. Implement `getPreviewUrl()` từ cache/`previewUrl`.
3. Implement `synth()` (blob→objectURL, model từ cache, style có điều kiện).
4. Implement `synthStream()` (reader→blob, indeterminate).
5. Sửa `use-generate` + `progress-status` cho indeterminate; revoke objectURL ở result-card.
6. Chạy thật với backend (`uvicorn` :8124 + `npm run dev` proxy): nghe thử, synth ngắn, synth dài (>1200), kiểm Download đúng format.
7. Ép lỗi (text quá dài ở tier anon / spam để 429) xem có ném `ApiError` đúng (limit-state sẽ nối ở phase khác đã có map).

## Success Criteria

- [ ] Voices thật render; lọc theo ngôn ngữ/engine + search chạy; preview phát audio thật.
- [ ] Synth ngắn: audio thật, Download đúng đuôi (`mp3/wav/ogg` map `response_format`), `model` đúng engine giọng.
- [ ] Synth dài (>1200): stream chạy, progress indeterminate, ra player + Download, UI không treo.
- [ ] Style chỉ gửi khi hợp lệ; không dính 400 "invalid style".
- [ ] Không rò rỉ objectURL (revoke khi tạo mới/unmount) — kiểm bằng devtools/`ak:code-review` phase 6.
- [ ] `npm run build` xanh.

## Risk Assessment

- **[Validation F2 — RESOLVED]** BE không nhận `ogg` (chỉ mp3/opus/aac/flac/wav/pcm). **QĐ: `AudioFormat` = `'mp3'|'wav'`** — bỏ `ogg` khỏi `format-select` (thực thi ở phase 4) + thu hẹp type ở `types.ts` (phase 1). `synth`/`synthStream` chỉ gửi `response_format ∈ {mp3,wav}`.
- **Rủi ro:** cache miss khi user vào thẳng compose (không qua voice list). **Tín hiệu:** synth thiếu model. **Ứng phó:** lazy `listVoices()` trong synth nếu cache rỗng; fallback default model.
- **Rủi ro:** stream giữ kết nối lâu, mobile ngắt. **Tín hiệu:** reader lỗi giữa chừng. **Ứng phó:** try/catch reader → ApiError('overloaded'/'generic'); nút "Tạo lại".
- **Rủi ro:** anon buffered ≤1200 khớp `textLimits.soft=1200` — nếu BE đổi ngưỡng thì lệch. **Tín hiệu:** 400 input_too_long ở ~1200. **Ứng phó:** map 400→too_long state; ngưỡng FE là hằng, chỉnh nếu BE đổi.

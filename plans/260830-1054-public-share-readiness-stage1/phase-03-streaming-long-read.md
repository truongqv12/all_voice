---
title: "Phase 3: Streaming đọc file dài"
status: done
---

# Phase 3: Streaming đọc file dài

Priority: P1 · Effort: ~2 ngày · Phụ thuộc: P1 (P2 tùy chọn)

## Overview

Tính năng chủ lực: **đọc cả file txt dài → stream audio**. Endpoint mới nhận văn
bản dài, **tách câu**, synth **từng câu dưới semaphore**, **stream mp3** chảy dần;
**check budget + dừng ở câu kế khi client ngắt** (câu đang synth không hủy được — #3). Đây là cách né CF 524 (byte chảy
liên tục) và giữ RAM phẳng (yield từng câu, không buffer cả file).

## Requirements

- Functional:
  - `POST /v1/audio/stream` (phần mở rộng all-voice, **không đụng** `/v1/audio/speech`
    chuẩn OpenAI). Body JSON `{model, voice, input, style?}`; luôn trả `audio/mpeg`.
  - Tách `input` thành câu; synth tuần tự; `StreamingResponse` yield mp3 từng câu.
  - Mỗi câu: `await request.is_disconnected()` → dừng nếu client đóng; `reserve_chars`
    theo độ dài câu → hết budget thì kết thúc stream sạch sẽ.
  - Cap tổng ký tự theo tier (ANON `anon_max_chars_stream` ~20k); vượt → 400.
- Non-functional: mỗi câu **nhả semaphore** giữa các lần → TTS/ASR người khác xen
  vào được (công bằng); header chống buffering để stream chảy ngay.

## Architecture

- **Tách câu (không NLP dep):** `re` split theo `. ! ? … \n` (giữ dấu câu); gộp
  mảnh quá ngắn; **cắt nhỏ câu quá dài** (> ~400 ký tự) theo `, ; :`/khoảng trắng
  để mỗi lần synth bị chặn thời lượng (mỗi chunk < ~15-20s audio → luôn dưới CF).
- **Generator:** `synth_stream(backend, voice, chunks, fmt, ident, request)` —
  async generator. Vòng lặp: nếu `await request.is_disconnected()` → break (log);
  **[#4] `reserve_chars(ip, len(chunk))` NGAY TRƯỚC câu đó** (commit theo từng câu
  đã yield, không reserve cả bài trước → không trừ oan khi ngắt giữa chừng) — fail
  → break sạch; `async with admit(ident.ip, tier): pcm = await
  anyio.to_thread.run_sync(backend.synthesize, chunk, voice, 1.0, opts)`;
  `yield encode(pcm, sr, "mp3")`. **Nhả `admit` sau mỗi câu**. **[#12]
  `finally`/`GeneratorExit`:** client ngắt phải nhả `admit` + giảm stream-counter
  (không rò slot). **[#3] Cắt không tức thì:** câu đang synth chạy xong mới dừng
  (thread `to_thread` không hủy được) — chunk ≤ ~400 ký tự để phần phí bị chặn.
- **[#8] Cap kết nối stream/IP:** ngoài concurrency từng-câu (nhả giữa câu), đếm
  **số stream mở/IP** (`anon_max_streams_per_ip`), giữ **suốt vòng đời connection**,
  tăng lúc mở / giảm trong `finally`. Vượt → 429 lúc mở. Mid-stream `Overloaded` khi
  re-acquire `admit` → kết thúc stream **sạch** (không 500).
- **Nối mp3 (⚠️ CẦN kiểm chứng — #14):** mỗi `encode(pcm, sr, "mp3")` tạo **1
  container MP3 đầy đủ** (đầu/đuôi + Xing/Info header + encoder delay/padding), nên
  nối nhiều file MP3 độc lập = bài toán "gapless MP3": browser `<audio>` có thể
  vấp/gap/sai duration. **Trước khi chốt:** chạy **spike** phát thử chuỗi nối trên
  browser đích; vấp → chuyển **1 encoder MP3 streaming liền** (1 container `av` feed
  frame-by-frame xuyên câu) NGAY, không để "tối ưu tương lai".
- **Chỉ mp3:** format khác → 400 (mp3 là format stream ổn định nhất trên browser).
- **Response headers:** `Cache-Control: no-cache`, `X-Accel-Buffering: no` (kèm
  `proxy_buffering off` ở nginx — Phase 4) để không bị đệm → tránh CF 524.

## Related Code Files

- Create: `app/streaming.py` — `sentence_split(text, max_len)` + `synth_stream(...)` async generator.
- Create: `app/routers/speech_stream.py` — `POST /v1/audio/stream`; gate tier + cap tổng ký tự + **[#8]** cap `anon_max_streams_per_ip` (giữ suốt connection) + trả `StreamingResponse`.
- Create: `app/schemas.py` (bổ sung) — `StreamSpeechRequest {model, voice, input, style?}` (input cho phép dài; validate tổng ở router theo tier).
- Modify: `app/main.py` — `app.include_router(speech_stream.router, prefix="/v1")`.
- Reuse: `app/audio/encoder.py::encode` (mp3 per-câu), `app/limits.py::admit`, `app/quota.py`, `app/client_identity.py`.
- Create: `tests/test_streaming.py` — `sentence_split` (tất định), stream nhiều câu decode được, ngắt giữa chừng dừng synth (marker phù hợp; phần synth thật gắn `synth`).

## Implementation Steps

1. `streaming.py::sentence_split`: regex tách câu + gộp mảnh ngắn + cắt câu quá dài. Unit test thuần, tất định.
2. `schemas.py`: `StreamSpeechRequest` (không đặt `max_length` cứng ở schema; router validate theo tier để giữ linh hoạt).
3. `streaming.py::synth_stream`: async generator theo Architecture; **[#4]** reserve
   ký tự **theo từng câu ngay trước synth** (không reserve cả bài); **[#12]** nhả
   `admit` + giảm stream-counter trong `finally`/`GeneratorExit`; log số câu, ký tự
   đã stream, lý do dừng (done/disconnect/budget/overload).
4. `routers/speech_stream.py`: `ident = Depends(resolve_tier)`; resolve backend+voice
   (`registry.resolve` + `backend.resolve_voice` như speech.py); cap tổng ký tự
   (`anon_max_chars_stream`); **[#8]** kiểm + tăng `anon_max_streams_per_ip` lúc mở
   (vượt → 429), giảm trong `finally`; `allow_rate` một lần;
   `StreamingResponse(synth_stream(...), media_type="audio/mpeg", headers=...)`.
5. **[#14]** Spike phát thử chuỗi mp3 nối trên browser đích; vấp → đổi sang 1 container
   mp3 streaming liền (quyết trong phase này).
6. `main.py`: include router.
7. Test `test_streaming.py`: (a) `sentence_split` cho chuỗi mẫu ra đúng số câu; (b) [synth] stream 3 câu → nối bytes decode ra audio > 0s; (c) giả `is_disconnected=True` sau câu 1 → generator dừng, không synth câu 2; (d) **[#8]** vượt `anon_max_streams_per_ip` → 429; (e) **[#4]** ngắt sau câu 1 → chỉ bị trừ budget của câu 1.

## Todo

- [x] `streaming.py`: `sentence_split` (regex, cắt câu dài)
- [x] `schemas.py`: `StreamSpeechRequest`
- [x] `streaming.py`: `synth_stream` (disconnect + **[#4]** reserve/câu + nhả semaphore/câu + **[#12]** finally/GeneratorExit)
- [x] `routers/speech_stream.py`: `POST /v1/audio/stream` + cap tổng + **[#8]** cap stream/IP + gate
- [x] [#14] spike phát thử mp3 nối trên browser (hoặc encoder streaming liền)
- [x] `main.py`: include router stream
- [x] `tests/test_streaming.py`: split + stream + ngắt giữa chừng + **[#8]** cap stream/IP + **[#4]** trừ đúng câu đã yield

## Success Criteria

- [x] `POST /v1/audio/stream` văn bản nhiều câu → nhận mp3 chảy dần, phát được.
- [x] Đóng client giữa chừng → server ngừng synth câu tiếp (log disconnect).
- [x] Hết budget giữa chừng → stream kết thúc sạch (không 500).
- [x] Vượt `anon_max_chars_stream` → 400.
- [x] Giữa các câu, request khác vẫn được phục vụ (semaphore được nhả).
- [x] [#14] Chuỗi mp3 nối phát **gapless** trên browser đích (spike xác nhận), hoặc đã đổi sang container streaming liền.
- [x] [#8] Vượt `anon_max_streams_per_ip` → 429 lúc mở; mid-stream overload → kết thúc sạch (không 500).
- [x] [#4] Ngắt giữa chừng → chỉ trừ budget các câu **đã yield** (không trừ cả bài).
- [x] `pytest -q -m "not synth"` xanh (phần split + ngắt kết nối).

## Risk Assessment

- **Nối mp3 per-câu lỗi phát (#14):** *Tín hiệu:* browser kén vấp/gap/sai duration.
  *Xử lý:* **spike kiểm chứng TRƯỚC khi chốt** (không mặc định "pattern phổ biến,
  chấp nhận"); lỗi → 1 container mp3 liền mạch (encoder streaming) — quyết ngay
  trong Phase 3, không defer.
- **[#8] Kết nối stream treo/lạm dụng:** *Tín hiệu:* nhiều stream mở/IP, request thật
  bị `Overloaded`. *Xử lý:* cap `anon_max_streams_per_ip` giữ suốt connection; mid-stream
  overload → kết thúc sạch.
- **File cực dài giữ kết nối rất lâu → CF 524 hiếm gặp:** *Tín hiệu:* 524 trên
  stream dài. *Xử lý:* cap `anon_max_chars_stream`; nếu vẫn cần dài hơn → async-job
  (giai đoạn sau), đúng khuyến nghị chính thức của Cloudflare.
- **Câu quá dài → 1 chunk synth lâu > vài chục giây:** *Tín hiệu:* khoảng lặng dài
  giữa chunk. *Xử lý:* `sentence_split` cắt câu > ~400 ký tự để chunk luôn ngắn.

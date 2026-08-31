---
phase: 2
title: "Giới hạn & ngưỡng 2000/20k (FE + BE)"
status: completed
priority: P1
effort: "0.5-1d"
dependencies: [1]
---

# Phase 2: Giới hạn & ngưỡng 2000/20k

## Overview
Chốt hành vi text cỡ vừa/dài: **≤2000 ký tự → buffered** (nhanh + `result_cache`),
**>2000 → stream** (progress), **tối đa 20.000**. Bỏ mốc 120. Đồng bộ giới hạn FE↔BE.

## Requirements
- Functional (FE):
  - `use-generate.ts`: ngưỡng `text.length > 2000 → synthStream`, else `synth` (bỏ `> 120`).
  - Hạn cứng ô nhập = **20000** (đã có `textLimits.hard=20000` — xác nhận + hiện đếm/cảnh báo khi gần hạn); >20000 chặn ở FE, không gửi.
- Functional (BE — đụng tối thiểu, không phá contract):
  - `config.py`: `anon_max_chars_buffered` **1200 → 2000** (`config.py:64`; giữ default có thể override qua env). **Đây là thay đổi BE DUY NHẤT cần cho phase này.**
  - **Đã verify (31/08): stream KHÔNG cần sửa schema.** `/v1/audio/stream` dùng `StreamSpeechRequest` riêng (`schemas.py:106`) — `input` **không có** max_length (docstring nói rõ "KHÔNG bị chặn 4096"), router áp trần `anon_max_chars_stream=20_000` (`speech_stream.py:59`, `config.py:103`). ⇒ 20k đã chạy trên stream; chỉ buffered (`SpeechRequest.input` max_length=4096, `schemas.py:28`) bị chặn 4096 — nhưng ngưỡng buffered ≤2000 < 4096 nên **không vướng**.
  - Giữ 400 `input_too_long` cho phần vượt hạn tier (không đổi mã lỗi).
- Non-functional: `.env.example`/docs cập nhật giới hạn mới; thông điệp FE khớp ngưỡng BE (không để "gửi rồi mới 400").

## Architecture
- Nguồn sự thật giới hạn: BE config → FE `lib/limits.ts` phản chiếu (buffered≤2000, max 20k). Nếu chênh, ưu tiên chặn ở FE trước để tránh round-trip lỗi.
- Đường tải: 10k > 2000 → stream (CPU tuần tự, per-IP 2, queue 20, chờ-slot 90s→429; xem plan §load).

## Related Code Files
- Modify: `frontend/src/features/compose/use-generate.ts` (ngưỡng 2000)
- Modify: `frontend/src/lib/limits.ts` (buffered 2000, hard 20000 — xác nhận/chỉnh)
- Modify: `app/config.py` (`anon_max_chars_buffered=2000`)
- Verify/Modify: `app/schemas.py`, `app/routers/speech_stream.py` (input length đường stream tới 20k)
- Modify: `.env.example`, `docs/` liên quan (nếu ghi giới hạn)

## Implementation Steps
1. BE: nâng `anon_max_chars_buffered` 1200→2000 (`config.py:64`); chạy `uv run pytest -q` (không vỡ test hiện có). (Stream đã verify — không sửa schema.)
2. FE: đổi ngưỡng `use-generate.ts` sang 2000; xác nhận hard 20000 + cảnh báo gần hạn; đồng bộ thông điệp.
3. Test biên thủ công qua curl/httpx: 2000/2001/20000/20001 (buffered anon >2000→400; stream nhận tới 20000).

## Success Criteria
- [ ] Nhập 2000 → buffered (có cache khi lặp); 2001 → stream; không đơ.
- [ ] Nhập 20000 → chạy (stream); 20001 → chặn FE / API trả **400 `input_too_long`**.
- [ ] BE buffered anon chấp nhận tới 2000 (không còn 400 ở 1500–2000).
- [ ] `uv run pytest -q` xanh; contract OpenAI endpoint không đổi.

## Risk Assessment
- ~~Rủi ro stream bị schema 4096 chặn~~ — **ĐÃ VERIFY LOẠI BỎ (31/08):** `StreamSpeechRequest.input` không có max_length (`schemas.py:106-120`); 20k chạy sẵn. Không còn rủi ro này.
- **Rủi ro:** nâng buffered 2000 làm buffered synth lâu hơn → cảm giác treo. **Tín hiệu:** ≤2000 chờ lâu. **Ứng phó:** đã có progress/timeout P1; cân nhắc hạ ngưỡng buffered nếu đo thấy chậm (mốc dev chọn, ≤2000).
- **Rủi ro:** đụng backend làm hỏng tương thích. **Ứng phó:** chỉ đổi config/giới hạn; chạy full pytest; không sửa logic synth.

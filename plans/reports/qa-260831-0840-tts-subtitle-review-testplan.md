---
title: "Rà soát QA & Bộ test-case đầy đủ — TTS / Subtitle / Upload / Task lâu (all_voice)"
type: qa-review
status: reference
created: 2026-08-31
related_plan: 260831-0059-real-model-integration
sources:
  - QA_REPORT.md
  - app/routers/{speech,speech_stream,transcriptions,voices}.py
  - app/{schemas,config,limits,quota,result_cache,previews}.py
  - app/asr/{transcriber,subtitles}.py
  - frontend/src/features/{compose,transcribe,voice}/*
  - frontend/src/api/*
  - plans/260831-0059-real-model-integration/plan.md
  - plans/reports/research-260830-srt-subtitle-export.md
---

# Rà soát QA & Bộ test-case đầy đủ

> Phương pháp: đọc source thật (BE + FE), đối chiếu `QA_REPORT.md` với plan
> `260831-0059-real-model-integration` và research `research-260830-srt-subtitle-export.md`.
> Mọi kết luận có evidence `file:line`. Chỗ nào chưa đủ dữ liệu ghi rõ **"CHƯA ĐỦ DỮ LIỆU"**.
> Không viết code. Bộ test-case bên dưới để QA/dev chạy lại trực tiếp.

---

## 1. Tóm tắt phát hiện từ QA_REPORT.md

QA_REPORT gồm 3 lớp nội dung: (a) sửa E2E cũ, (b) rà 3 tính năng chính qua API thật, (c) các
sửa lỗi FE buổi chiều. Tóm tắt tình trạng theo báo cáo:

| # | Ghi nhận trong QA_REPORT | Báo cáo tự đánh giá | Kiểm chứng lại (report này) |
|---|---|---|---|
| 1 | Preview/Nghe thử: BE trả `404 No preview for voice '001'` | ❌ Đang lỗi → "sửa" bằng fallback synth câu cứng | **XÁC NHẬN lỗi**; "fix" là **che lỗi** (xem §3). Root cause: **sai voice-id/model**, không phải thiếu file mẫu |
| 2 | Stream audio text dài (x20 câu) | ⚠️ Chạy nhưng chậm (~35s) | **XÁC NHẬN**: BE synchronous, chậm do CPU; **không treo** — quá giới hạn thì **400/429**, không hang |
| 3 | Transcribe (audio→sub) qua API | ✅ Tốt (10.6s, segments+words chuẩn) | **XÁC NHẬN** path API thật tốt. NHƯNG nút **"Thử với âm thanh mẫu" là GIẢ** (fixture, không gọi BE) |
| 4 | Hạ threshold stream `1200→120` (TC4) | "khắc phục treo server" | **XÁC NHẬN** đổi code; lý do "treo" **không chính xác** — thực chất né buffered chậm (xem §3) |
| 5 | Xoá nút "Xuất .srt" TTS (TC6), gỡ test | do `ttsToSrt=false` | **XÁC NHẬN**; đây là **non-goal có chủ đích** của plan, KHÔNG phải bug — nhưng tính năng vẫn **chưa làm** |
| 6 | Sample transcribe đẩy `'mock-audio-content'` → 400 | "fix" bằng simulate progress giả | **XÁC NHẬN**: nút sample **giả lập UI**, không kiểm được BE thật |
| 7 | TC7/TC8/TC10/TC11/TC12/TC15: sửa assert, khôi phục JWT | tests 14/14 pass | JWT đính kèm **có thật** (`http-client.ts:17-18`); nhiều fix chỉ chỉnh assert — **không tăng độ phủ hành vi lỗi** |

**Chức năng ĐÃ ỔN (có evidence):**
- Transcribe từ file thật: `POST /v1/audio/transcriptions` + export SRT/VTT/TXT client-side từ `result.segments` (thật, không fixture).
- Stream TTS: `POST /v1/audio/stream` chạy, phát hiện client disconnect, dừng sạch, refund theo chunk.
- JWT `Authorization: Bearer` đính kèm từ `localStorage`.
- Validation file upload phía FE (transcribe): chặn định dạng + size 25MB **trước khi** upload.

**Chức năng CHƯA ỔN / che lỗi:**
- Preview nghe thử: 404 bị **fallback synth câu cứng** che (root cause chưa fix).
- Nút "Thử âm thanh mẫu" (transcribe): **giả lập fixture**, không chạm BE.
- Threshold stream hạ xuống 120 để né buffered chậm — **lệch acceptance plan** (buffered ≤1200).

**Chức năng CHƯA LÀM (đúng thiết kế, cần biết rõ):**
- **TTS kèm subtitle (TTS→SRT)**: **non-goal** của plan (`plan.md:25`); research xác nhận **không có aligner nhẹ torch-free hôm nay** cho VieNeu/Kokoro. Đã ẩn (`ttsToSrt=false`).

**CHƯA ĐỦ DỮ LIỆU trong QA_REPORT (không kết luận được nếu chỉ đọc báo cáo):**
- Không có test nào cho: F5/refresh khi đang chạy, cancel/abort task, timeout mạng, đổi input giữa chừng, cancel file picker, đổi/xoá file, double-click, empty text/empty file, các mã lỗi 401/413/503-asr, task xong nhưng rỗng output. → Đây chính là khoảng trống bộ test này lấp.

---

## 2. Danh sách chức năng cần rà soát lại

| Nhóm | Chức năng | Lý do rà lại |
|---|---|---|
| A | Tạo voice từ **text** (buffered ≤120 / stream >120) | Ranh giới threshold đổi 1200→120; hành vi biên chưa test |
| B | Tạo voice từ **file .txt** | FE đọc client-side thành text; chưa test file rỗng/sai/huỷ |
| C | Tạo voice **text/file lớn** (task 2–3 phút) | Chậm CPU; không có progress %, không timeout, không cancel |
| D | Tạo voice **kèm subtitle** | Chưa làm; cần chốt BE có đáp ứng được không |
| E | Tạo **subtitle từ file** (transcribe) | Path thật OK; nút sample GIẢ; edge-case file chưa phủ |
| F | **Upload file** (cả 2 khu) | Cancel picker, đổi/xoá file, wrong type, quá lớn, rỗng |
| G | **Progress / loading / timeout** | Không có % thật khi synth/ASR; fetch không timeout |
| H | **Refresh / F5 / thoát** khi đang chạy | Không persist; request mồ côi; có `result_cache` chưa tận dụng |
| I | **Validation input** | Empty text/file, giới hạn ký tự client vs server |
| J | **Error handling** | error-map thiếu mã 400 audio / 503 asr; 404 preview |
| K | **Retry / recovery** | Không có nút retry; không resume |
| L | **Edge cases** | Đồng âm/ký tự lạ, đa request, output rỗng |
| M | **UX states** | Empty/loading/success/error/disabled nhất quán |

---

## 3. Gap analysis — QA hiện tại vs hành vi thực tế cần test

### GAP-1 — Preview "sửa" bằng cách che lỗi
- **QA nói:** đã sửa 404 preview.
- **Thực tế code:** `use-voice-preview.ts:55-67` bắt lỗi playback → synth câu cứng `"Xin chào, đây là giọng đọc thử của tôi."` (VN) / `"Hello, this is a sample of my voice."` (EN).
- **Backend:** 404 `preview_not_found` **chỉ khi voice không tồn tại** (`voices.py:60-63`); preview là **synth on-demand**, cache theo hash passage (`previews.py:180-200`) — nghĩa là preview **có sẵn** cho mọi voice hợp lệ.
- **Kết luận:** root cause thật = **FE gọi preview với `{engine}/{id}` sai** (`getPreviewUrl` tự dựng URL khi thiếu `preview_url`: `http-tts-api.ts:117-119`). Fallback synth **che mismatch**, tốn thêm 1 lượt synth/CPU, và làm mọi voice "nghe thử" ra **cùng 1 câu cứng** thay vì passage mẫu đúng ngôn ngữ. **Cần test:** mọi voice trong `/v1/voices` → preview trả 200 bằng chính `preview_url` BE cấp.

### GAP-2 — Câu chuyện "treo server khi >1200" không chính xác
- **QA nói:** text >1200 làm treo Uvicorn → hạ threshold 120.
- **Backend:** anon buffered `/audio/speech` **>1200 char → 400 `input_too_long`** (`speech_stream`/`speech.py:80-90`, `config.py:64`); stream nhận tới **20000** (`config.py:103`); quá tải slot → **429 Overloaded** (`limits.py:73-87`, timeout chờ slot 90s). ⇒ **BE không hang, nó từ chối bằng 400/429.**
- **Thực tế:** vấn đề thật là **buffered synth chậm** (một request block ~tuỳ độ dài, ~35s cho đoạn dài). Hạ 120 đẩy hầu hết sang stream (progressive + disconnect-safe) — **giảm cảm giác treo** nhưng **lệch acceptance** plan (`buffered ≤1200`) và **không giải quyết**: không có % thật, không timeout, không cancel.
- **Cần test:** biên 120/121/1200/1201/4096/20000/20001 ký tự, cả anon và có key; đo TTFB + tổng thời gian; xác nhận không hang, có phản hồi lỗi rõ.

### GAP-3 — Nút "Thử âm thanh mẫu" là giả
- `use-transcribe.ts:38-48` `transcribeSample()` trả `transcriptFixture` + progress giả (20/48/100, 18/56/100), **không gọi BE**. ⇒ demo đẹp nhưng **không kiểm được** đường transcribe thật, dễ ngộ nhận "đã chạy".
- **QUYẾT ĐỊNH (user, 31/08): GỠ HẲN nút sample** — bỏ nhánh fixture `transcribeSample()`, chỉ giữ **upload file thật**. Nghiệm thu transcribe chỉ qua file thật (nhóm E).

### GAP-4 — TTS kèm subtitle: chưa làm (đúng thiết kế) nhưng là nhu cầu người dùng
- BE **không** trả timing cho audio TTS (`base.py:28-35` chỉ `pcm+sample_rate`); **không** endpoint nào ghép audio+sub 1 call. FE ẩn nút (`audio-result-card.tsx:61`, `ttsToSrt=false`).
- Research: chỉ **VOICEVOX** có mora-timing native (đang bị vứt); VieNeu/Kokoro **không có aligner nhẹ**. ⇒ Đây là **gap backend**, không phải bug FE. §5 nhóm D + §8 cần chốt hướng.

### GAP-5 — Không có timeout / cancel / retry / resume (cả stack)
- FE: `fetch` **không timeout** (`http-client.ts`), **không AbortController**, **không nút retry**, **không persist** task (chỉ token/theme/lang). ⇒ BE chậm/mạng rớt → **UI treo vô hạn**.
- BE: có `result_cache` cho **buffered speech** (hash nội dung, `result_cache.py:39-44`) — **có thể** dùng để resume-after-refresh cho request giống hệt, nhưng **FE chưa tận dụng**; stream + transcription **không** cache.

### GAP-6 — error-map thiếu mã lỗi
- `error-map.ts`: map 413→asr-too-long, 429→rate, 402→quota, 503→overloaded, code `input_too_long/rate_limit_exceeded/quota_exceeded/server_overloaded`.
- **Thiếu/sai:** `invalid_audio_file` (400) và `audio_file_too_large` (400) **không map** → alert generic; `asr_unavailable` (503) **bị gán "overloaded"** (sai thông điệp — thực ra thiếu extra ASR); `preview_not_found` (404) không map (đang bị fallback nuốt); `invalid_api_key` (401) không map.

### GAP-7 — Race đổi input/model khi đang chạy
- Không có `requestId`/guard ổn định; đổi text/model/voice giữa chừng → response cũ có thể ghi đè kết quả mới (scout FE #11). **Cần test.**

---

## 4. Ma trận chức năng & trạng thái backend/frontend

Ký hiệu: ✅ đáp ứng · ⚠️ một phần / lệch · ❌ chưa · ❔ chưa đủ dữ liệu.

| Chức năng | Backend | Frontend | Tổng | Ghi chú evidence |
|---|---|---|---|---|
| TTS text ngắn (≤120) | ✅ `/audio/speech` buffered (anon ≤1200) | ✅ `synth()` | ✅ | `speech.py:32`, `use-generate.ts:11` |
| TTS text cỡ vừa/dài | ✅ buffered ngắn + stream dài | ⚠️ hiện `>120 stream` | 🔜 chốt §8: **≤2000 buffered · >2000 stream · max 20k** + progress/timeout | plan cũ `≤1200 buffered`; QĐ mới §8 |
| TTS + subtitle | ❌ không timing 1-call | ❌ đang ẩn `ttsToSrt=false` | 🔜 chốt: **build qua ASR round-trip (VI/EN) + VOICEVOX native (JP)** (§8) | `base.py:28-35`; QĐ §8 |
| Timestamp cho audio TTS | ❌ | ❌ | ❌ | không forced-alignment |
| Subtitle từ file (ASR) | ✅ `/audio/transcriptions` srt/vtt/verbose_json+words | ✅ upload thật + chunk client | ✅ | `transcriptions.py:51`, `subtitle-export-panel.tsx:16` |
| Nút "sample" transcribe | — | ❌ fixture giả | ❌ giả | `use-transcribe.ts:38-48` |
| Preview nghe thử | ✅ on-demand, 404 nếu voice sai | ⚠️ fallback synth che 404 | ⚠️ che lỗi | `voices.py:59-63`, `use-voice-preview.ts:55-67` |
| Validation file (ASR) | ✅ empty/25MiB/corrupt→400; >300s→413 | ✅ .mp3/.wav/.m4a, 25MB trước upload | ✅ | `transcriptions.py:135-160`, `use-transcribe.ts:9,25-26` |
| Validation file (TTS .txt) | — (đọc client) | ⚠️ chỉ chặn đuôi .txt; không precheck rỗng/encoding | ⚠️ | `file-drop-zone.tsx:6` |
| Progress % thật | ❌ không job/progress API (synchronous) | ⚠️ stream=bytes(KB); ASR=upload% rồi 0% | ⚠️ | `speech.py:118`, `http-transcribe-api.ts:108-109` |
| Timeout request | ⚠️ chờ-slot 90s→429; **không** timeout tổng synth | ❌ fetch không timeout | ❌ FE treo vô hạn | `limits.py:83-87`, `http-client.ts` |
| Cancel / abort | ✅ stream phát hiện disconnect, dừng+refund | ❌ không AbortController | ⚠️ chỉ hủy được bằng đóng tab | `streaming.py:127-129` |
| Retry | — | ❌ không nút retry | ❌ | scout FE #3 |
| Resume sau F5 | ⚠️ `result_cache` **buffered speech** (hash) | ❌ không persist task | ⚠️ chưa tận dụng | `result_cache.py:39-44` |
| Concurrency / overload | ✅ per-IP 2, queue 20, 429 | ✅ map 429→overloaded/rate | ✅ | `config.py:68-70`, `error-map.ts` |
| Error envelope/codes | ✅ `{error:{message,type,code}}` 11+ code | ⚠️ map thiếu 400-audio/503-asr/404/401 | ⚠️ | `schemas.py:284-294`, `error-map.ts` |
| Auth JWT | ✅ anon + Bearer | ✅ đính kèm từ localStorage | ✅ | `auth.py`, `http-client.ts:17-18` |

### 4b. Phân loại khả năng backend cho phần chưa chắc/chưa làm

| Tính năng | Phân loại BE | Nếu chưa đáp ứng, cần thêm gì |
|---|---|---|
| TTS→subtitle (verbatim) | **Chưa đáp ứng** | (1) BE trả timing cùng audio (endpoint mới hoặc field), **hoặc** (2) VOICEVOX: giữ `audio_query.accent_phrases` mora-timing (rẻ, native, chỉ JP), **hoặc** (3) forced-alignment (MFA/WhisperX/stable-ts — nặng, +torch), **hoặc** (4) fallback ASR round-trip (không verbatim). Cần: **subtitle output format** kèm audio + **error code** khi engine không hỗ trợ |
| Progress cho task lâu | **Chưa đáp ứng** | **Task/job status API** (id + poll) hoặc **progress event** (SSE/WebSocket). Hiện synchronous, chỉ stream mới có tín hiệu chunk |
| Timeout tổng cho synth | **Một phần** | Có timeout **chờ-slot** 90s; **thiếu** timeout **tổng thời gian synth**. Cần cap + **error code** rõ khi vượt |
| Resume sau refresh | **Một phần** | `result_cache` buffered-speech đã có (hash nội dung). Cần: **áp cho stream/ASR** (idempotency key) + FE lưu "last job" để tái gọi/tái hiện |
| Cancel phía server | **Một phần** | Stream tự dừng khi disconnect; buffered **chạy đến hết** dù client rời. Cần **hủy job buffered** khi disconnect (hoặc chuyển buffered→stream) |
| File validation (ASR) | **Đáp ứng** | Đủ: empty/size/corrupt/duration. (Tùy chọn: whitelist mime rõ ràng) |
| Error codes rõ ràng | **Đáp ứng** | Có 11+ code; FE cần **map đủ** (400-audio, 503-asr, 404-preview, 401) |
| Preview | **Đáp ứng** | On-demand + cache. FE chỉ cần **dùng `preview_url` BE cấp**, bỏ tự-dựng URL & bỏ fallback che lỗi |

---

## 5. Bộ test-case đề xuất

> Quy ước: **Ưu tiên** H/M/L. **Env**: BE `127.0.0.1:8124` (anon bật, `--extra asr` để test transcribe), FE preview/serve proxy `/v1`. "Anon" = không key; "Trusted" = có `Authorization: Bearer`.

### Nhóm A — Tạo voice từ TEXT

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú BE/FE |
|---|---|---|---|---|---|---|---|
| VT-01 | Text ngắn (≤120) buffered | Xác nhận đường buffered | Trang TTS, chọn voice VieNeu | Nhập ~50 ký tự → Tạo | Gọi `/audio/speech`; có `<audio>`+objectURL; nút Download đúng format | H | FE `synth()` khi ≤120 |
| VT-02 | Text 121–1200 stream | Xác nhận route sang stream sớm | như trên | Nhập ~300 ký tự → Tạo | Gọi `/audio/stream`; progress hiện KB; phát được; Download | H | Lệch plan (đáng lẽ buffered) — ghi nhận |
| VT-03 | Chọn đúng engine theo voice | model gửi khớp voice | có voice Kokoro/VOICEVOX | Chọn voice EN/JP → Tạo | `model` gửi = engine của voice (kokoro/voicevox), không mặc định vieneu | H | `http-tts-api.ts:125,153` |
| VT-04 | Format output (mp3/wav) | Đúng định dạng tải về | — | Đổi format → Tạo → Download | File tải đúng đuôi/định dạng; phát được | M | plan chốt mp3+wav |
| VT-05 | Style chỉ hiện khi có styles | Ẩn control BE thiếu | voice có/không styles | So sánh 2 voice | Voice không styles → không có style-select | M | |
| VT-06 | Speed ẩn với VieNeu | no-op không phơi | voice VieNeu | Mở panel | Không có slider speed cho VieNeu | L | plan non-goal speed VieNeu |

### Nhóm B — Tạo voice từ FILE (.txt)

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| VF-01 | Upload .txt hợp lệ | Nạp nội dung vào editor | file .txt ~200 ký tự | Kéo/thả hoặc chọn file | Nội dung đổ vào textarea; char-counter cập nhật; Tạo chạy như text | H | `file-drop-zone.tsx:6` đọc `file.text()` |
| VF-02 | File sai định dạng (.pdf/.docx) | Chặn định dạng | file .pdf | Thả .pdf | Bị từ chối, có thông báo; không nạp rác | H | Chỉ chặn đuôi `.txt` |
| VF-03 | File .txt rỗng | Không cho tạo với rỗng | file rỗng 0 byte | Thả → Tạo | Textarea rỗng → nút Tạo **disabled**; không gọi API | H | guard `!text.trim()` |
| VF-04 | File .txt cực lớn (>20000 ký tự) | Giới hạn client | file ~50k ký tự | Thả | Cắt/chặn theo `textLimits.hard=20000`; báo rõ | M | `lib/limits.ts:1` |
| VF-05 | Encoding khác (UTF-8 có dấu, CRLF) | Không vỡ ký tự | file UTF-8 tiếng Việt | Thả → Tạo | Ký tự dấu đúng; xuống dòng xử lý ổn | M | CHƯA ĐỦ DỮ LIỆU về normalize — cần quan sát |

### Nhóm C — Tạo voice từ TEXT/FILE LỚN (task lâu)

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| VL-01 | Đo thời gian đoạn dài | Xác định độ trễ thật | text ~3000–5000 ký tự | Tạo, bấm giờ | TTFB nhanh (stream), tổng có thể 30–120s+; UI hiện tiến trình KB, **không đơ toàn trang** | H | synchronous CPU |
| VL-02 | Ngưỡng buffered↔stream = 2000 | Đúng đường xử lý | anon | Nhập 2000 rồi 2001 ký tự | **2000 → buffered** (có cache); **2001 → stream** (progress); không đơ | H | QĐ §8; nâng BE `anon_max_chars_buffered` 1200→2000 |
| VL-03 | Hạn tối đa 20.000 | Chặn đúng max | anon | Nhập 20000 rồi 20001 ký tự | 20000 chấp nhận (stream); 20001 **chặn ở FE**; qua API → **400 `input_too_long`** | H | `config.py:103`; verify schema stream không dính max 4096 |
| VL-04 | Quá tải đồng thời (per-IP 2) | Xác nhận 429 không hang | 3 tab cùng IP | Bấm Tạo đồng thời cả 3 | Request thứ 3 nhận **429 Overloaded**, hiện state, không treo | H | `config.py:68`, `limits.py:73` |
| VL-05 | Chờ-slot timeout 90s | Không chờ vô hạn phía BE | ép nghẽn slot | Giữ slot đầy >90s | Trả **429** "Timed out waiting for slot" | M | `limits.py:83-87` |

### Nhóm D — Tạo voice KÈM SUBTITLE (đã chốt: ASR round-trip cho VI/EN, VOICEVOX native cho JP)

> Thiết kế đã chốt (§8): VI/EN → sinh audio rồi đưa qua `/v1/audio/transcriptions` (kèm `prompt`=text gốc) để lấy mốc giờ → sub. JP → mora-timing VOICEVOX. Chấp nhận "gần đúng" (không verbatim tuyệt đối). Các case dưới để nghiệm thu **khi tính năng được build**.

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| VS-01 | Bật tính năng TTS→SRT | Nút xuất phụ đề xuất hiện | feature bật | Tạo voice VI/EN → xem result-card | Có nút "Xuất phụ đề" (SRT/VTT); trạng thái mặc định đúng | H | thay `ttsToSrt=false` |
| VS-02 | VI/EN qua Whisper round-trip | Sinh sub có mốc giờ | voice VieNeu/Kokoro, `--extra asr` | Tạo voice → Xuất phụ đề | Audio → transcribe (prompt=text gốc) → SRT có mốc giờ; sub **bám text gốc** nhờ prompt | H | tận dụng `prompt` (`transcriptions.py`) |
| VS-03 | JP qua VOICEVOX native | Không dùng round-trip | voice VOICEVOX | Tạo voice JP → Xuất phụ đề | Sub từ mora-timing (accent-phrase), chính xác; không gọi ASR | M | research §2a |
| VS-04 | Mức lệch "gần đúng" | Đặt kỳ vọng đúng | text có đồng âm/tên riêng/số/`[cười]` | Tạo → Xuất phụ đề | Sub có thể lệch; UI **cảnh báo "phụ đề gần đúng"**; không quảng cáo verbatim | H | trade-off đã chốt |
| VS-05 | Task lâu khi tạo sub | Gấp đôi CPU không treo | text dài | Tạo voice + sub | Progress "đang tạo phụ đề…"; có **timeout + hủy/retry**; không đơ | H | 2× CPU (synth+ASR) |
| VS-06 | Sub khớp với audio phát | Đồng bộ | có audio+sub | Phát audio, xem sub | Mốc giờ khớp audio thật (không lệch trôi) | M | |

### Nhóm E — Tạo SUBTITLE từ FILE (transcribe)

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| SF-01 | Upload audio hợp lệ → transcript | Happy-path thật | `--extra asr`, file .mp3 ~30s | Thả file → chờ | `/audio/transcriptions` verbose_json; hiện segments+timestamps; **không dùng fixture** | H | `use-transcribe.ts`, `subtitle-export-panel.tsx:16` |
| SF-02 | Xuất SRT/VTT/TXT | Export đúng chuẩn | có transcript thật (SF-01) | Bấm xuất từng format | File tải đúng cú pháp cue; đổi options (chars/line, lines/cue) đổi output | H | `to-srt/to-vtt/to-txt` |
| SF-03 | Đã GỠ nút "sample" | Xác nhận bỏ demo giả | — | Vào khu transcribe | **Không** còn nút "Thử âm thanh mẫu"; không còn nhánh `transcribeSample()`/fixture; chỉ còn upload file thật | H | Quyết định gỡ (`use-transcribe.ts:38-48`) |
| SF-04 | File rỗng | Chặn rỗng | file 0 byte .mp3 | Thả | FE hoặc BE báo lỗi rõ (**400 invalid_audio_file**); không treo | H | `transcriptions.py:135` |
| SF-05 | File sai định dạng (.exe/.txt) | Chặn định dạng | file .txt đổi tên .mp3? | Thả .txt và .mp3-giả | FE chặn theo regex `.mp3/.wav/.m4a`; nếu lọt → BE **400 invalid_audio_file** | H | `use-transcribe.ts:9,25` |
| SF-06 | File >25MB | Chặn size | file 30MB | Thả | FE chặn **trước upload** (`size>25MB`); nếu qua API → **400 audio_file_too_large** | H | `use-transcribe.ts:26`, `transcriptions.py:137` |
| SF-07 | Audio quá dài (>300s anon) | Chặn duration | file 6 phút, anon | Thả → upload | BE **413 audio_too_long** (probe header trước khi tốn CPU); FE hiện state | H | `config.py:99`, `transcriptions.py:154` |
| SF-08 | ASR chưa cài extra | Lỗi rõ ràng | BE **không** `--extra asr` | Upload file | **503 asr_unavailable**; FE **không** được hiển thị nhầm "overloaded" | H | `transcriptions.py:180-183`; **error-map thiếu** |
| SF-09 | File audio hỏng/corrupt | Không crash | file mp3 cắt dở | Thả → upload | **400 invalid_audio_file**; UI báo lỗi, không văng | M | `transcriptions.py:150-153` |
| SF-10 | Hủy giữa chừng transcribe | Cancel | file lớn đang ASR | Bấm/đóng khi đang chạy | **CHƯA ĐỦ**: FE không có abort (`xhr.abort()` vắng) → chỉ đóng tab mới dừng | M | Gap → RR/§7 |

### Nhóm F — Upload file (chung 2 khu)

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| UP-01 | Mở picker rồi Cancel | Không lỗi khi bỏ chọn | — | Mở chọn file → Cancel | `files[0]=undefined` → không làm gì, giữ nguyên state | H | `file-drop-zone.tsx:6`, `audio-drop-zone.tsx:12` |
| UP-02 | Chọn nhầm rồi đổi file | Ghi đè đúng | 2 file | Chọn file A rồi chọn lại file B | State theo file B; không lẫn nội dung A | H | |
| UP-03 | Xoá file đã chọn | Reset sạch | file đã nạp | Xoá/clear | (TTS) chưa có "remove" UI → CHƯA ĐỦ: cần xác định cách xoá | M | scout FE #12 |
| UP-04 | Thả nhiều file cùng lúc | Chỉ nhận 1 | 2+ file | Kéo-thả nhiều | Chỉ xử lý file đầu; không crash | M | `files?.[0]` |
| UP-05 | Kéo-thả vs input click | 2 đường vào giống nhau | — | Test cả drag-drop và click | Cùng validation, cùng kết quả | M | |
| UP-06 | File tên rất dài/ký tự lạ | Không vỡ UI | file tên unicode dài | Thả | Hiển thị an toàn (break-word), không tràn | L | |

### Nhóm G — Progress / Loading / Timeout

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| PG-01 | Progress stream TTS | Có phản hồi khi chạy | text >120 | Tạo | Hiện KB nhận được (không phải %); có spinner "chuẩn bị" trước byte đầu | H | `progress-status.tsx:4` |
| PG-02 | Progress ASR 2 giai đoạn | Upload% rồi xử lý | file lớn | Upload | Giai đoạn upload có %; giai đoạn transcribe **0% (indeterminate)** — cần rõ "đang xử lý", không đứng hình như treo | H | `http-transcribe-api.ts:108-109` |
| PG-03 | Không có timeout fetch | Phát hiện treo vô hạn | BE giả chậm (throttle) | Tạo và chờ | **THIẾU**: nếu BE không phản hồi, UI **treo mãi** (không timeout, không hủy) | H | `http-client.ts` không timeout |
| PG-04 | Loading khoá nút | Chống double-run | — | Trong lúc chạy | Nút Tạo **disabled** khi `generating`; không bấm lại được | H | `compose-panel.tsx:24` |
| PG-05 | Spinner preview | Không xoay mãi | voice lỗi preview | Bấm nghe thử voice 404 | Hiện fallback (câu cứng) — **đánh dấu là che lỗi**; test kỳ vọng nên là 200 preview thật | M | GAP-1 |
| PG-06 | Đóng tab khi stream | Dừng sạch phía BE | đang stream | Đóng tab | BE phát hiện disconnect, dừng + refund; log "disconnect" | M | `streaming.py:127-129` |

### Nhóm H — Refresh / F5 / Thoát khi đang xử lý

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| RF-01 | F5 giữa lúc synth | Mất/khôi phục state | đang tạo voice | F5 | **Hiện tại: mất hết state**, về idle; request mồ côi (BE vẫn chạy tới hết nếu buffered) | H | không persist |
| RF-02 | F5 rồi tạo lại y hệt | Tận dụng result_cache | buffered speech giống hệt | F5 → nhập lại text/voice/format y hệt → Tạo | BE trả từ **result_cache** (nhanh, không synth lại) | M | `result_cache.py:39-44` (buffered only) |
| RF-03 | F5 giữa lúc transcribe | Mất state | đang ASR | F5 | Mất transcript đang chạy; **không** cache ASR để khôi phục | H | ASR không cache |
| RF-04 | Back/Forward trình duyệt | SPA không vỡ | đang chạy | Bấm Back | State in-memory mất; route đổi an toàn (SPA fallback) | M | |
| RF-05 | Chuyển tab TTS↔Transcribe khi chạy | Không rò kết quả chéo | đang chạy | Đổi feature-nav | Request cũ không ghi kết quả sang khu mới; không crash | H | scout FE #11 |
| RF-06 | Đóng tab khi buffered synth | BE có hủy không | đang buffered (ép ≤120 dài) | Đóng tab | **CHƯA ĐỦ/Gap**: buffered **chạy đến hết** dù client rời (không hủy) | M | `speech.py` không cancel |

### Nhóm I — Validation input

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| VA-01 | Empty text + Tạo | Chặn rỗng | text rỗng | Bấm Tạo | Nút **disabled** (`!text.trim()`); không gọi API | H | `compose-panel.tsx:24` |
| VA-02 | Chỉ khoảng trắng/emoji | Chặn vô nghĩa | text "   " / chỉ emoji | Bấm Tạo | disabled hoặc báo hợp lệ hoá; không gửi rác | M | |
| VA-03 | No file + Transcribe | Không xử lý khi thiếu file | chưa chọn file | Bấm khu transcribe | Hiện drop-zone; không có "transcribe" chạy nếu chưa có file (trừ nút sample fixture) | H | `audio-drop-zone.tsx:12` |
| VA-04 | Ký tự sát giới hạn (19999/20000) | Biên client | — | Nhập đúng biên | 20000 chấp nhận; vượt bị chặn/cắt, báo rõ | M | `lib/limits.ts` |
| VA-05 | Text có `[cười]`, chuyển ngữ Việt-Anh | Cue inline không lỗi | — | Nhập cue + Tạo | Gửi nguyên input; BE xử lý cue; không lỗi FE | L | README cue inline |
| VA-06 | Giới hạn client vs server khớp | Không lệch UX | — | So sánh chặn FE (20000) vs BE (anon buffered 1200 / stream 20000) | Thông điệp nhất quán; không để user gửi rồi mới 400 | M | GAP-2 |

### Nhóm J — Error handling

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| EH-01 | 429 rate/overload | Hiện state đúng | intercept 429 | Ép/route 429 | LimitState "quá tải/giới hạn" VN/EN đúng | H | `error-map.ts` |
| EH-02 | 400 input_too_long | Thông điệp "quá dài" | intercept/ép | Gửi text quá dài (API) | Map `too-long`, state đúng | H | code map |
| EH-03 | 413 audio_too_long | ASR quá dài | file >300s | Upload | Map `asr-too-long`, state đúng | H | 413 |
| EH-04 | 503 asr_unavailable | **Đừng** nhầm "overloaded" | BE không extra asr | Upload | **BUG kỳ vọng**: hiện map sai → thông điệp phải là "ASR chưa sẵn sàng", không "overloaded" | H | GAP-6 |
| EH-05 | 400 invalid_audio_file | Không nuốt lỗi | file corrupt | Upload | **BUG kỳ vọng**: chưa map → alert generic; cần thông điệp "file âm thanh không hợp lệ" | H | GAP-6 |
| EH-06 | 400 audio_file_too_large (API) | Map size lỗi | qua API >25MiB | Gọi trực tiếp | Chưa map → generic; cần thông điệp "file quá lớn" | M | GAP-6 |
| EH-07 | 401 invalid_api_key | Key sai (nếu tắt anon) | anon off + key sai | Gọi | 401 map rõ "khoá không hợp lệ" | M | anon thường bật |
| EH-08 | 500 internal_error | Không lộ traceback FE | ép 500 | Gọi | Hiện alert generic an toàn; không lộ chi tiết; log BE có traceback | M | `main.py:222` |

### Nhóm K — Retry / Recovery

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| RR-01 | Retry sau lỗi mạng | Cho thử lại | ngắt mạng giữa chừng | Tạo → cắt mạng → lỗi | **THIẾU**: không có nút Retry; user phải làm lại từ đầu | H | scout FE #3 |
| RR-02 | Recovery sau 429 | Hướng dẫn chờ | nhận 429 | Sau 429 | State gợi ý thử lại sau; không kẹt | M | |
| RR-03 | Resume buffered sau F5 | Tái dùng cache | RF-02 | Lặp request y hệt | result_cache trả nhanh (proxy resume) | M | buffered only |
| RR-04 | Idempotency stream/ASR | Tránh tính phí 2 lần | lặp request | Gửi lại | **CHƯA ĐỦ**: stream/ASR không cache/idempotent → tốn CPU lại | L | cần key idempotency |

### Nhóm L — Edge cases

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| EC-01 | Double/triple click Tạo | Không tạo trùng | — | Bấm nhanh 3 lần | Chỉ 1 request (nút disabled sau click đầu) | H | `compose-panel.tsx:24` |
| EC-02 | Đổi input khi đang chạy | Không ghi đè sai | đang synth | Sửa text/đổi voice giữa chừng | **BUG kỳ vọng (race)**: response cũ có thể ghi đè kết quả — cần guard requestId | H | scout FE #11 |
| EC-03 | Task xong nhưng output rỗng | Không giả "thành công" | voice/edge trả 0 byte | Tạo | Nếu audio rỗng → báo lỗi, **không** hiện player rỗng "thành công" | H | cần kiểm |
| EC-04 | Voice preview khác nhau ra cùng câu | Phát hiện fallback | nhiều voice lỗi preview | Nghe thử nhiều voice | Nếu tất cả ra cùng "Xin chào..." → xác nhận đang fallback che lỗi | M | GAP-1 |
| EC-05 | Ký tự đặc biệt/đồng âm (transcribe) | Verbatim lệch | audio TTS đưa lại ASR | (nếu làm TTS→SRT qua ASR) | Ghi nhận sub có thể **không verbatim** | L | research §2c |
| EC-06 | Nhiều tab cùng thao tác | Không lẫn state/quota | 2 tab | Chạy song song | Quota theo IP dùng chung; state tab độc lập | M | quota per-IP |

### Nhóm M — UX states

| ID | Tên | Mục tiêu | Tiền điều kiện | Bước | Kết quả mong đợi | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| UX-01 | Empty state | Rõ ràng khi trống | mới vào | Xem 2 khu | Empty-state có hướng dẫn; filter rỗng hiện "Không có giọng khớp" + "Đặt lại bộ lọc" | M | QA_REPORT TC7 |
| UX-02 | Loading state | Không mơ hồ | đang chạy | Quan sát | Spinner/tiến trình rõ; nút disabled; không nhấp nháy | H | |
| UX-03 | Success state | Kết quả rõ | xong | Quan sát | Player + Download hiện; không rò objectURL (revoke) | H | plan lưu ý objectURL |
| UX-04 | Error state | Thân thiện VN/EN | có lỗi | Quan sát | Alert lỗi rõ, có hành động tiếp theo (retry/chờ) | H | RR-01 thiếu retry |
| UX-05 | i18n/theme khi đang chạy | Không vỡ khi đổi | đang chạy | Đổi VN↔EN, light↔dark | Chuỗi đổi đúng, không FOUC, không mất tiến trình | L | QA_REPORT TC10/TC15 |

---

## 6. Các edge case BẮT BUỘC phải test (ưu tiên cao nhất)

1. **Preview trả cùng 1 câu cho mọi voice lỗi** (EC-04, GAP-1) — phát hiện fallback che lỗi; nghiệm thu đúng phải là preview 200 từ `preview_url` BE.
2. **Text lớn: 120/121/1200/1201/20000/20001 ký tự** (VL-02/03, VT-02) — xác nhận **400/429, không hang**; đo thời gian thật.
3. **Quá tải per-IP (2) và chờ-slot 90s** (VL-04/05) — 429 rõ, không treo.
4. **F5/đóng tab khi đang chạy** (RF-01/03/05/06) — mất state; buffered không hủy; không rò kết quả chéo.
5. **Race đổi input/model giữa chừng** (EC-02) — response cũ ghi đè kết quả mới.
6. **Cancel picker / đổi file / file rỗng / sai định dạng** (UP-01/02, VF-02/03, SF-04/05) — không crash, báo rõ.
7. **ASR: file >25MB, >300s, corrupt, chưa cài extra** (SF-06/07/08/09) — đúng 400/413/503; **503 không được nhầm "overloaded"**.
8. **Không có timeout fetch** (PG-03) — mô phỏng BE chậm → UI treo vô hạn (defect).
9. **Không có nút retry sau lỗi** (RR-01) — user kẹt.
10. **Đã gỡ nút "sample" transcribe** (SF-03) — kiểm tra đã loại bỏ nhánh fixture; nghiệm thu chỉ qua file thật.
11. **Task xong output rỗng** (EC-03) — không được hiện "thành công" giả.
12. **TTS + subtitle 1 call** (VS-03) — xác nhận backend chưa đáp ứng.

---

## 7. Đề xuất cải thiện UX khi xử lý task lâu

Ưu tiên theo tác động (không phải code — đề xuất để plan hoá):

1. **Thêm timeout + AbortController phía FE** (H): mọi `fetch`/XHR có timeout hợp lý (vd 120–180s), user **hủy được**; hết timeout → state lỗi + **nút Retry**. (Lấp GAP-5, PG-03, RR-01, SF-10.)
2. **Progress "đang xử lý" rõ ràng cho giai đoạn ASR/synth** (H): thay 0%-indeterminate bằng nhãn "Đang nhận dạng…/Đang tổng hợp…" + spinner + thời lượng đã trôi; đặt kỳ vọng ("có thể mất 1–3 phút với đoạn dài").
3. **Dùng `preview_url` BE cấp, bỏ fallback che lỗi** (H): sửa `getPreviewUrl` dùng đúng URL BE; nếu 404 → thông báo "voice này chưa có mẫu" thay vì synth câu cứng. (Lấp GAP-1.)
4. **Map đủ error code** (H): 400 audio, 413, 503-asr (thông điệp "ASR chưa cài"), 404 preview, 401. (Lấp GAP-6.)
5. **Resume nhẹ sau F5** (M): FE lưu "last successful job" (text/voice/format) vào `sessionStorage`; sau F5 gợi ý "khôi phục kết quả gần nhất" — tận dụng `result_cache` buffered của BE (RF-02/RR-03).
6. **Guard requestId chống race** (M): gắn id mỗi request, chỉ nhận response khớp id hiện tại (EC-02).
7. **Chống double-run toàn diện** (M): đảm bảo mọi nút hành động disabled khi đang chạy (đã có ở compose; kiểm transcribe/sample).
8. **Đồng bộ giới hạn client↔server** (M): FE chặn theo đúng ngưỡng anon (buffered/stream) để không "gửi rồi mới 400" (VA-06).
9. **(Tùy hướng sản phẩm) TTS→SRT**: nếu cần, chốt hướng BE (VOICEVOX mora-timing native trước; VieNeu/Kokoro dùng ASR round-trip "gần đúng" hoặc để lại). (§8.)

---

## 8. Quyết định đã chốt & câu hỏi còn lại

### Quyết định đã chốt (user, 31/08)

1. **TTS→SRT (subtitle kèm voice): LÀM theo hướng "gần đúng" (ASR round-trip).**
   - **VI/EN:** sinh audio → đưa qua Whisper (`/v1/audio/transcriptions`) để lấy mốc giờ → sinh sub. **Kèm `prompt`=text gốc** để Whisper bám đúng chữ hơn (giảm lệch). Chấp nhận sub **không verbatim tuyệt đối**.
   - **JP:** làm **riêng** qua **VOICEVOX mora-timing native** (không dùng round-trip).
   - Trade-off đã hiểu: **gấp đôi CPU/độ trễ**; sub có thể lệch (đồng âm/tên riêng/số/cue). → cần state "đang tạo phụ đề…" + timeout.
2. **Giới hạn text & ngưỡng buffered/stream:**
   - **≤ 2000 ký tự → buffered** (nhanh + `result_cache`); **> 2000 → stream** (progress). Bỏ mốc 120.
   - **Hạn cứng tối đa = 20.000 ký tự** (khớp `anon_max_chars_stream=20000`).
   - **Cần chỉnh BE:** nâng `anon_max_chars_buffered` 1200→2000 (`config.py:64`); **verify** đường stream không bị `SpeechRequest.input` max_length=4096 chặn (`schemas.py:28`) — nếu dính thì phải nới schema stream để cho tới 20k.
   - **Bắt buộc kèm:** progress rõ + **timeout** + **nút hủy/retry** (gốc của "cảm giác treo").
   - *Lưu ý tải (đã đính chính):* max 20k ⇒ **10k VẪN cho phép** (đi stream). CPU chạy **tuần tự** (1 worker); per-IP đồng thời 2, hàng đợi 20, chờ-slot 90s→429 (`config.py:68-70`). 2 user gửi 10k lệch vài giây → người sau **xếp hàng ≤90s**, quá thì **429 (không treo)**. Cho phép 20k = **chấp nhận** request dài chiếm CPU lâu; stream giúp giải phóng CPU khi user đóng tab.
3. **Nút "Thử âm thanh mẫu": GỠ HẲN** (bỏ nhánh fixture `transcribeSample`); chỉ giữ upload file thật.

### Câu hỏi còn lại
- **Target tiêu thụ subtitle:** file tải về (SRT ưu tiên) hay nhúng `<track>` web (VTT)? (Ảnh hưởng default export.)
- **Ngưỡng timeout FE mong muốn** cho (a) synth dài, (b) ASR file lớn? (mặc định đề xuất 120–180s.)
4. **Cancel buffered phía server:** có cần hủy job buffered khi client rời (hiện chạy tới hết) hay chấp nhận (đã refund/ cache)?
5. **Target tiêu thụ subtitle:** file tải về (SRT ưu tiên) hay nhúng `<track>` web (VTT)? Ảnh hưởng default export.
6. **Ngưỡng timeout FE mong muốn:** bao nhiêu giây thì báo lỗi/cho retry cho (a) synth dài, (b) ASR file lớn?
7. **`result_cache`/idempotency cho stream & ASR:** có mở rộng để tránh tính phí/CPU lặp khi user thử lại không?

---

### Phụ lục — Lệnh chạy nhanh (tham chiếu)

- BE anon + ASR: `ANON_ENABLED=true WORKERS=1 uv run uvicorn app.main:app --port 8124` (cần `uv sync --extra asr` cho nhóm E).
- FE: build/preview proxy `/v1` → `127.0.0.1:8124` (dev `VITE_API_PROXY_TARGET`).
- Mock offline (chỉ visual, KHÔNG dùng nghiệm thu chức năng): `VITE_USE_MOCK=1`.
- Đường lỗi trực tiếp (không cần UI): gọi `curl`/httpx vào `/v1/audio/{speech,stream,transcriptions}` để ép biên 400/413/429/503.

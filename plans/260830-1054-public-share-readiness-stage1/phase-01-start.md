---
title: "Phase 1: Tầng ẩn danh + gate bảo vệ"
status: done
---

# Phase 1: Tầng ẩn danh + gate bảo vệ

Priority: P1 · Effort: ~2 ngày · Phụ thuộc: — (nền cho P2/P3)

## Overview

Cho phép TTS/ASR chạy **không cần key** (tầng anon) và thay lớp bảo vệ mà key
đang gánh bằng **gate theo IP**: đọc `CF-Connecting-IP`, phân tier, rate-limit,
budget ký tự/giây-audio/ngày (SQLite), concurrency/IP, **hàng đợi có trần → 429**,
timeout, và **công tắc tắt anon**. Clone CRUD giữ nguyên khóa key.

## Requirements

- Functional:
  - `resolve_tier(request, credentials)` → `ANON` | `TRUSTED` (key hợp lệ trong
    `API_KEYS`). `ANON_ENABLED=false` + không key → **401** như cũ.
  - TTS (`/v1/audio/speech`) và ASR (`/v1/audio/transcriptions`) chấp nhận anon.
  - Clone CRUD (`/v1/audio/voices`, `voice_consents`) **vẫn** `require_api_key`.
  - Discovery (`GET /v1/voices`, `/v1/models`, `/health`, preview) **public**.
  - Gate mỗi request synth/asr: rate-limit (token bucket/phút/IP) → reserve budget
    (ký tự cho TTS / giây-audio cho ASR) → giới hạn concurrency/IP → **admit**
    (semaphore + hàng đợi trần + timeout). Vượt bất kỳ bước nào → **429/400** với
    envelope OpenAI, không treo.
- Non-functional: in-memory + SQLite (1 worker, single-writer an toàn); không dep
  ngoài; đọc header không tin cậy phải an toàn (bind localhost là ranh giới tin cậy).

## Architecture

- **IP tin cậy (loopback-gate BẮT BUỘC):** `client_ip(request)` chỉ tin
  `cf-connecting-ip` **khi `request.client.host` là loopback** (nginx luôn nối từ
  `127.0.0.1` nên traffic thật không mất gì); peer non-loopback → **bỏ header, dùng
  `request.client.host`** — chống giả mạo ngay cả khi API lỡ bind ra ngoài. API vẫn
  bind `127.0.0.1` (Phase 4) là lớp 1, loopback-gate là lớp 2.
- **Tier:** dùng lại `settings.api_key_set` (auth.py). Key khớp = `TRUSTED`
  (bypass rate/budget, cap cao). Không key + `anon_enabled` = `ANON`. Không key +
  `anon_enabled=false` = 401.
- **Token bucket (rate):** dict `ip -> (tokens, last_refill)`; refill
  `anon_rate_per_min/60` mỗi giây, trần `anon_burst`. Thuần in-memory.
- **Budget ngày (SQLite):** `quota.db`, bảng `usage(ip TEXT, day TEXT, chars INT,
  audio_ms INT, PRIMARY KEY(ip,day))`. `reserve_chars(ip,n)` /`reserve_audio(ip,ms)`:
  `UPSERT` cộng dồn, so `anon_chars_per_day`/`anon_audio_seconds_per_day`; vượt →
  `QuotaExceeded`. `day` = UTC `YYYY-MM-DD` (tự reset qua ngày).
- **Admission (hàng đợi + timeout):** mở rộng `app/limits.py`. Đếm `waiters`; nếu
  `waiters >= max_queue_waiters` → `Overloaded` (429) **trước khi** chờ. Ngược lại
  `async with anyio.fail_after(request_timeout_s): async with synth_semaphore:`.
  Concurrency/IP: dict `ip -> count`, ≥ `anon_max_concurrent_per_ip` → 429.
- **Cap ký tự/request theo tier:** ANON `len(input) > anon_max_chars_buffered`
  (~1200) → 400 kèm gợi ý dùng `/v1/audio/stream` (né CF 524). TRUSTED tới 4096
  (schema giữ nguyên để tương thích OpenAI SDK).

## Related Code Files

- Create: `app/client_identity.py` — `client_ip()`, `Tier`, `resolve_tier()` (FastAPI dependency dùng `Request`).
- Create: `app/quota.py` — token bucket + SQLite budget; `QuotaExceeded`, `RateLimited`.
- Modify: `app/limits.py` — thêm `admit()` (waiter-count + semaphore + timeout), `Overloaded`, per-IP concurrency map.
- Modify: `app/config.py` — thêm: `anon_enabled`, `anon_rate_per_min`, `anon_burst`, `anon_chars_per_day`, `anon_audio_seconds_per_day`, `quota_db_path`, `anon_max_chars_buffered`, `anon_max_concurrent_per_ip`, `max_queue_waiters`, `request_timeout_s`; **[red-team]** `anon_max_streams_per_ip` (#8, Phase 3), `ip_key_ipv6_prefix=64` (#9), `ip_map_ttl_s` (#9).
- Modify: `app/routers/speech.py` — thay `require_api_key` bằng `resolve_tier`; chèn gate trước synth; ghi budget sau synth; log `ip`+`tier`+`chars`.
- Modify: `app/routers/transcriptions.py` — cùng gate; **[#7]** gate trước khi đọc body 25MB, `reserve_audio(probed_ms)` trước transcribe, reconcile `result.duration` sau; cap thời lượng ở Phase 2.
- Modify: `app/main.py` — audit auth từng router (discovery public; clone giữ key); log middleware thêm `client_ip`.
- Modify: `.env.example` — tài liệu biến mới + `ANON_ENABLED`.
- Create: `tests/test_gate.py` — unit test tier/rate/budget/queue với `CF-Connecting-IP` giả (marker `not synth`).

## Implementation Steps

1. `app/config.py`: thêm các trường Settings ở trên (giá trị nháp trong plan.md); giữ `api_keys`/`api_key_set` làm tầng TRUSTED.
2. `app/client_identity.py`: `client_ip(request)` + `resolve_tier(request, credentials=Depends(bearer_auth), settings=...)`. Trả dataclass `Identity(ip, tier)`. `anon_enabled=false` + anon → raise 401 (tái dùng `_unauthorized` của auth.py).
3. `app/quota.py`: token bucket in-memory (thread-safe bằng `threading.Lock`) + SQLite (`sqlite3`, `check_same_thread=False`, 1 kết nối, lock ghi). API: `allow_rate(ip)`, `reserve_chars(ip,n)`, `reserve_audio(ip,ms)`; TRUSTED bỏ qua (trả True).
4. `app/limits.py`: thêm `class Overloaded(Exception)`; `@asynccontextmanager admit(ip, tier)` làm: check per-IP concurrency → check waiter trần → `fail_after(timeout)` + `synth_semaphore`. TRUSTED có thể nới concurrency (tùy chọn, mặc định như anon).
5. `app/routers/speech.py`: `ident = Depends(resolve_tier)`; nếu ANON và `len(input) > anon_max_chars_buffered` → 400 (trỏ sang stream); `quota.allow_rate` → `quota.reserve_chars(ip, len(input))`; bọc synth trong `async with admit(...)`; bắt `RateLimited/QuotaExceeded/Overloaded` → 429, `TimeoutError` → 429/503; sau synth `log` kèm ip/tier.
6. `app/routers/transcriptions.py`: cùng pattern. **[#7] Gate theo header TRƯỚC khi
   đọc body 25MB** (rate/concurrency), rồi `probe_duration` (Phase 2) →
   `reserve_audio(ip, probed_ms)` **trước** `admit`/transcribe (đừng "reserve 0 rồi
   ghi sau" — request vượt cap vẫn cháy CPU). Sau transcribe reconcile với
   `result.duration` thật (refund/điều chỉnh nếu lệch). Bọc synth trong `admit`.
7. `app/main.py`: xác nhận `voices.py`/`models.py` public (bỏ `require_api_key` nếu đang có ở discovery), `voices_admin.py` giữ key; middleware log thêm `client_ip`.
8. Test `tests/test_gate.py`: TestClient gửi header `CF-Connecting-IP`; kịch bản: anon ok → vượt rate → 429; vượt chars/ngày → 429; `ANON_ENABLED=false` → 401; clone thiếu key → 401; queue đầy (mock semaphore) → 429.

## Red Team Fixes (đã Accept — áp trước khi cook)

Bổ sung/bắt buộc so với thiết kế gốc ở trên; mỗi mục gắn số finding.

- **[#1] Loopback-gate BẮT BUỘC** (không còn "tùy chọn"): `client_ip()` chỉ tin
  `cf-connecting-ip` khi `request.client.host` loopback; ngược lại dùng socket IP.
  Default `HOST=127.0.0.1` sửa cả **live `.env`** (Phase 4), không chỉ `.env.example`.
- **[#4] Hoàn budget khi KHÔNG giao audio:** reserve trước synth nhưng **refund
  trong `finally`/except** cho mọi lối ra không trả audio (429 Overloaded, timeout,
  400 `InvalidOption`, backend lỗi, client disconnect). Stream: commit **theo từng
  câu đã yield** (Phase 3). Test: 429/400/disconnect → net-zero budget/ngày.
- **[#5] Chốt 1 worker:** khi `ANON_ENABLED=true` mà `workers>1` → **refuse start**
  (log rõ). Lý do: bucket/concurrency/semaphore in-memory là per-process → nhân N;
  SQLite thành multi-writer. Docs cảnh báo ở Phase 4.
- **[#9] Chuẩn hóa key IP + evict:** trước khi key bucket/budget, chuẩn hóa
  **IPv6→/64, IPv4→/32** (né xoay địa chỉ). Map in-memory có **TTL/eviction**
  (bounded) để không phình RAM. NAT gộp: chấp nhận có chủ đích (ghi rõ), cap là nháp.
- **[#10] Chống thundering-herd sau restart:** seed token bucket **rỗng** lúc boot
  (client bắt đầu 0 token, không full burst); systemd `RestartSec`/
  `StartLimitIntervalSec` backoff (Phase 4). Budget SQLite vẫn bền qua restart.
- **[#12] Nhả counter chắc chắn:** per-IP concurrency + waiter count giảm trong
  `finally` quanh `yield` của `@asynccontextmanager admit` → mọi lối ra đều nhả slot.
  Test: raise-in-`admit` → counter về baseline.
- **[#15] SQLite & settings bền:** mở DB **WAL + `busy_timeout` NGAY từ đầu** (không
  đợi gặp lock); chạy reserve qua `anyio.to_thread.run_sync` để **không block event
  loop**; lỗi infra (`sqlite3.OperationalError`) → **fail-CLOSED** (429/503, không bao
  giờ allow). `admit()`/quota đọc cap từ `get_settings()` **lúc gọi** (không freeze
  lúc import); `resolve_tier(settings: Settings = Depends(get_settings))` để test
  override được `ANON_ENABLED`/cap.
- **[#3] Timeout đúng ngữ nghĩa:** `fail_after` chỉ bound **thời gian chờ semaphore**
  (queue-wait), KHÔNG kỳ vọng cắt wall-clock synth (thread `to_thread.run_sync` mặc
  định `abandon_on_cancel=False` → không hủy được). Đã admit thì để synth chạy xong;
  chặn tải bằng **từ chối lúc admit (429)** + cap ký tự theo **p95 synth đo thật** (Phase 2).
- **[#2] KHÔNG enforce trong code** (quyết định của chủ dự án): `dev-key` giữ nguyên
  như hiện tại; đổi key thật là trách nhiệm vận hành, README/docs đã có sẵn dòng nhắc.

Config bổ sung (thêm vào `config.py`): `anon_max_streams_per_ip` (dùng ở Phase 3),
`ip_key_ipv6_prefix=64`, `ip_map_ttl_s`, và cờ đọc `workers` để chốt 1-worker.

## Todo

- [x] `config.py`: thêm biến gate/budget/queue
- [x] `client_identity.py`: `client_ip` + `resolve_tier` (đọc `CF-Connecting-IP`)
- [x] `quota.py`: token bucket + SQLite budget (chars + audio_ms)
- [x] `limits.py`: `admit()` + `Overloaded` + concurrency/IP
- [x] `speech.py`: gate + cap ký tự tier + ghi budget + 429 mapping
- [x] `transcriptions.py`: gate + đo audio_ms
- [x] `main.py`: audit auth từng router + log `client_ip`
- [x] `.env.example`: biến mới + `ANON_ENABLED`
- [x] `tests/test_gate.py`: tier/rate/budget/queue/kill-switch
- [x] [#1] loopback-gate bắt buộc trong `client_ip()`
- [x] [#4] refund budget khi 429/400/timeout/disconnect (net-zero)
- [x] [#5] refuse start khi `ANON_ENABLED=true` + `workers>1`
- [x] [#9] chuẩn hóa IPv6→/64, IPv4→/32 + TTL/evict map in-memory
- [~] [#10] **Deviation (có chủ đích):** IP mới seed bucket **đầy burst** (UX lần đầu), KHÔNG rỗng — backstop lạm dụng là budget/ngày SQLite bền + hàng đợi admission (429 ngay, không treo). Phần crash-loop backoff (`StartLimitIntervalSec`/`Burst`) làm ở Phase 4. Ghi rõ trong `quota.allow_rate` docstring + report P5.
- [x] [#12] nhả per-IP concurrency + waiter trong `finally`
- [x] [#15] SQLite WAL+busy_timeout + reserve off-loop + fail-closed infra; settings đọc lúc gọi

## Success Criteria

- [ ] Anon gọi TTS/ASR không key → 200; clone không key → 401.
- [ ] Vượt rate/budget/queue → 429 (envelope OpenAI), không treo; có timeout.
- [ ] `resolve_tier` đọc đúng IP từ `CF-Connecting-IP` (test giả header).
- [ ] `ANON_ENABLED=false` → anon nhận 401.
- [ ] [#1] Header `CF-Connecting-IP` từ peer **non-loopback** bị bỏ qua (test giả socket non-loopback → dùng socket IP, không tin header).
- [ ] [#4] Request lỗi (429/400/timeout/disconnect) → budget/ngày **không** bị trừ (net-zero).
- [ ] [#12] Exception giữa `admit` → per-IP concurrency + waiter về baseline (không rò slot).
- [ ] [#5] `ANON_ENABLED=true` + `workers>1` → refuse start (log rõ).
- [ ] `pytest -q -m "not synth"` xanh (kèm test mới).

## Risk Assessment

- **Giả mạo `CF-Connecting-IP`:** nếu API lỡ bind ra ngoài, kẻ tấn công gửi header
  giả để né budget. *Tín hiệu:* request tới API không qua nginx. *Xử lý:* loopback-gate
  **bắt buộc** (chỉ tin header khi peer loopback) + Phase 4 bind `127.0.0.1` + đổi
  default `HOST=127.0.0.1` trong cả live `.env` (fail-closed, không chỉ `.env.example`).
- **SQLite khóa ghi khi tải cao:** mở **WAL + `busy_timeout` ngay từ đầu** (#15,
  không đợi gặp lock) + reserve chạy off event-loop; lỗi infra → **fail-CLOSED**.
  *Thay thế:* nếu lên nhiều worker (giai đoạn sau) → chuyển store dùng chung.
- **Cap 1200 ký tự chặn người dùng thật gõ đoạn vừa:** *Tín hiệu:* nhiều 400
  "input too long". *Xử lý:* nâng cap hoặc hướng dẫn dùng stream; số là nháp.

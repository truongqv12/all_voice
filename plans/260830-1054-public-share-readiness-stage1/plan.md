---
title: "Sẵn sàng chia sẻ công khai — Giai đoạn 1"
description: "Bảo vệ lõi TTS/ASR để mở công khai không đăng nhập sau Cloudflare Tunnel (1 máy): tầng ẩn danh + gate, gia cố synth + cache, streaming đọc file dài, edge nginx/Tunnel + UI test."
status: in-progress
priority: P1
effort: "~7.5-9 ngày"
tags: [tts, security, rate-limit, streaming, cloudflare-tunnel]
created: 2026-08-30
---

# Sẵn sàng chia sẻ công khai — Giai đoạn 1

## Overview

Mở dịch vụ TTS/ASR **công khai, KHÔNG đăng nhập** cho mọi người dùng free, chạy
trên **1 máy (i5-9400, 6 core, 11GB, no-GPU)** sau **Cloudflare Tunnel**, sao cho
**1 node CPU không sập/không treo** dù bị lạm dụng. Voice clone: **CRUD (tạo/sửa/
xóa) vẫn khóa sau key** (mở cho tài khoản ở giai đoạn sau); **liệt kê + nghe thử
(discovery/preview) công khai có chủ đích** (#6, theo quyết định commit gần đây).
Kèm **1 UI web đơn giản để kiểm chứng**;
web "xịn" làm ở giai đoạn sau.

### Hợp đồng (từ brainstorm đã chốt)

- **Outcome:** `/v1/audio/speech` + `/v1/audio/transcriptions` chạy được **không
  cần key** (tầng anon), có streaming đọc file dài; key hợp lệ = tầng cao hơn;
  clone **CRUD** giữ khóa key (discovery/preview công khai — #6). Server tự bảo vệ
  theo **chi phí thật (ký tự / giây audio)**, không chỉ đếm request.
- **Constraints:** hiệu quả > an toàn > KISS; **1 máy, 1 worker, in-memory +
  SQLite** (không Redis/DB ngoài); giữ tương thích OpenAI SDK; không phá deploy
  VieNeu-only; API **bind `127.0.0.1`** (ẩn), chỉ nginx lộ qua Tunnel.
- **Non-goals (giai đoạn này):** tài khoản/đăng ký, **mở clone CRUD cho anon**, web
  UI/UX thật, job-queue async, multi-máy/HA, đồng bộ DB. (Discovery/preview clone
  công khai là **có chủ đích** — #6, không phải non-goal.)
- **Acceptance:** xem "Success Criteria" bên dưới.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Truy cập **không key** cho TTS/ASR (tầng anon), key = tầng cao hơn; clone vẫn khóa key | P1 |
| 2 | Chặn lạm dụng theo **chi phí thật**: rate-limit + budget ký tự/giây-audio/ngày theo IP (`CF-Connecting-IP`) | P1 |
| 3 | Quá tải → **429 ngay, không treo**: hàng đợi có trần + timeout + concurrency/IP | P1 |
| 4 | Gia cố synth: **cap thread**, cap ký tự/request theo tier (né CF 524), **cache kết quả**, cap thời lượng ASR | P1 |
| 5 | **Streaming đọc file dài** từng câu (mp3), check budget + hủy khi ngắt kết nối | P1 |
| 6 | Đưa lên **nginx + Cloudflare Tunnel** (API ẩn ở localhost) + **UI test** + cập nhật docs | P1 |
| 7 | **Kiểm thử thực tế qua Cloudflare + stress test**: chứng minh không sập/không treo dưới lạm dụng, chốt số nháp | P1 |

## Phases

| # | Phase | Status | Phụ thuộc |
|---|-------|--------|-----------|
| 1 | [Tầng ẩn danh + gate bảo vệ](./phase-01-start.md) | Done | — |
| 2 | [Gia cố lõi synth + cache](./phase-02-core-hardening-cache.md) | Done | P1 |
| 3 | [Streaming đọc file dài](./phase-03-streaming-long-read.md) | Done | P1 (P2 tùy chọn) |
| 4 | [Edge (nginx + Tunnel) + UI test + docs](./phase-04-edge-tunnel-test-ui.md) | Done | P1–P3 |
| 5 | [Kiểm thử thực tế qua Cloudflare + Stress test](./phase-05-real-e2e-stress-test.md) | Tooling done · runs pending operator (CF Tunnel + load box) | P1–P4 (+ user config CF) |

## Kiến trúc tổng (1 máy, 0 port inbound)

```
Internet ─HTTPS─► Cloudflare edge (WAF 5 rule + 1 rate-rule + Bot Fight + DDoS)
                     ╲ cloudflared quay-ra-ngoài (KHÔNG mở port trên máy)
   ┌──────────────── 1 MÁY ────────────────┐
   │ nginx :8080  ── serve web/index.html   │  ◄─ cửa public duy nhất
   │      │  /v1/* → 127.0.0.1:8123         │     (proxy_buffering off, body cap)
   │      ▼                                  │
   │ FastAPI 127.0.0.1:8123 (localhost-only) │  ◄─ API ẩn hoàn toàn
   │  gate(CF-Connecting-IP): tier+rate+     │
   │  budget(SQLite)+queue/429+timeout       │
   │  → VieNeu (synth) / faster-whisper (ASR)│
   └─────────────────────────────────────────┘
```

## Nguyên tắc thiết kế then chốt (bám suốt các phase)

- **Đo theo chi phí thật:** TTS tính **ký tự**, ASR tính **giây audio** — đó là
  đơn vị CPU thật, quan trọng hơn đếm request.
- **`CF-Connecting-IP` (loopback-gate BẮT BUỘC):** qua Tunnel, IP thật ở header này;
  socket luôn `127.0.0.1`. Gate đọc header **nhưng chỉ tin khi peer là loopback**,
  + API bind `127.0.0.1` + nginx `listen 127.0.0.1` → không giả mạo từ ngoài (#1).
- **Fail-closed:** vượt hạn mức/quá tải → **429 ngay**, không block vô hạn (swap
  chỉ 975MB, cấm phình RAM). Lỗi hạ tầng (SQLite lock) cũng **fail-CLOSED** (#15).
- **Né CF 524 (timeout 100s):** buffered cap ký tự/request theo **p95 synth đo thật**
  để CPU < ~60-80s; cái dài đi **streaming**. Lưu ý: `fail_after` **KHÔNG** cắt được
  synth đang chạy (thread không hủy — #3) → chặn bằng cap + từ chối lúc admit.
- **VieNeu serialize nội bộ** (`vieneu_backend.py` `self._lock` — đã xác minh):
  `MAX_CONCURRENCY=1`, cap CPU synth preset bằng **cgroup `CPUQuota`/`taskset`**
  (onnxruntime torch-free bỏ qua `OMP_NUM_THREADS` — #13), chừa core cho loop/tunnel.
  Concurrency thật cần thêm máy (giai đoạn sau), **không** thêm worker (WORKERS>1
  phá gate in-memory — #5).

## Success Criteria (Acceptance)

- [x] Gọi `POST /v1/audio/speech` **không có** `Authorization` header vẫn trả audio (tầng anon). — `resolve_tier` → ANON; verified real-synth + gate tests.
- [x] Vượt budget ký tự/ngày hoặc rate-limit → **429** với envelope lỗi OpenAI, **không treo**. — `quota` + `main.py` GateError handler; `test_gate`.
- [x] Hàng đợi đầy (nhiều request đồng thời) → **429** ngay thay vì chờ vô hạn; có timeout/request. — `limits.admit` bounded queue + `fail_after`; `test_gate`.
- [x] Gate đọc đúng IP từ `CF-Connecting-IP` (test bằng header giả trong unit test). — `client_identity` loopback-gate; `test_gate`.
- [x] Clone **CRUD** (`/v1/audio/voices*` tạo/sửa/xóa) **vẫn 401** khi thiếu key; `GET /v1/voices` + preview **public** (anon thấy cả giọng clone — có chủ đích #6). — live smoke: clone 401, voices/models 200; `test_e2e`.
- [x] [#1] `CF-Connecting-IP` từ peer **non-loopback** bị bỏ qua; live `.env` bind `127.0.0.1`. — loopback-gate unit-tested; live smoke shows bind `127.0.0.1` only. (LAN-unreachable check là **P5** `assert_stateful spoof` từ máy khác.)
- [x] [#4] Request lỗi (429/400/timeout/disconnect) → budget/ngày **không** bị trừ. — reserve-then-refund; `test_gate`/`test_streaming` budget tests.
- [ ] [#13] Synth preset bị chặn CPU thật (cgroup/taskset, **đo** — không chỉ log config). — `CPUQuota=`/`AllowedCPUs=` trong `install-service.sh`; **đo là P5** trên systemd.
- [x] [#5] `ANON_ENABLED=true` + `workers>1` → refuse start. — `main.py` guard + `install-service.sh` guard.
- [x] `ANON_ENABLED=false` → dịch vụ quay về **chỉ nhận key** (401 cho anon). — `resolve_tier` raises 401 khi anon tắt.
- [x] Thread inference bị cap (log/khởi động xác nhận `OMP_NUM_THREADS`, `cpu_threads`). — `__init__` OMP setdefault + `transcriber` cpu_threads.
- [x] Request lặp (cùng text+voice+format) lần 2 trả từ **cache** (nhanh, có log cache-hit). — `result_cache` + `speech.py`; `test_result_cache`.
- [x] `POST /v1/audio/stream` với văn bản nhiều câu → **stream mp3** phát được; đóng client giữa chừng → server dừng synth **ở câu kế tiếp** (log disconnect; câu đang chạy không hủy được — #3). — `streaming`/`speech_stream`; `test_streaming` + real-synth HTTP test.
- [x] nginx phục vụ `index.html` + proxy `/v1/*`; API `127.0.0.1` **không** truy cập được trực tiếp từ ngoài. — `nginx.conf.example` (`listen 127.0.0.1:8080`, buffering off, body cap, CF-IP); API loopback proven. (chạy nginx thật là bước deploy/P5.)
- [x] `docs/deployment.md` + `.env.example` cập nhật đủ để dựng lại (Tunnel + nginx + localhost bind). — + `deploy/cloudflare-tunnel.md`.
- [x] `uv run pytest -q -m "not synth"` xanh; test gate/quota/stream mới đi kèm. — 102 passed.
- [ ] **[P5]** E2E qua **domain Cloudflare thật**: anon TTS + stream chạy, app log **IP thật**; stream dài **>100s không CF 524** (hoặc kết luận async-job). — **pending operator** (CF Tunnel); `stream-e2e.spec.ts` + checklist sẵn.
- [ ] **[P5] Stress test:** dưới tải + lạm dụng → box **không sập/không treo**, `/health` còn phản hồi, mọi vượt-ngưỡng **429 ngay**; refund/counter/RAM đúng; **con số nháp được chốt** (report ở `plans/reports/`). — **tooling delivered** (`scripts/loadtest/`, report scaffold); **runs pending operator**.

## Giai đoạn sau (ghi để chốt seam, KHÔNG làm bây giờ)

Chỉ để đảm bảo thiết kế hiện tại không vẽ nhầm đường:
- **Tài khoản + API key:** đăng ký → user + key (lưu hash) trong DB; free=tier
  theo IP, có key=tier cao (clone + quota lớn). Mở rộng đúng seam `resolve_tier`.
- **Multi-máy:** **1 DB chung (Postgres)** thay vì đồng bộ 2 DB; nginx đổi thành
  `upstream` round-robin (2× đồng thời + failover).
- **Clone qua nhiều máy:** **1 kho chung** (Cloudflare R2 free / thư mục LAN) +
  **lazy-enrol** (máy thiếu voice → kéo sample + enrol theo yêu cầu). Kiểm chứng
  VieNeu có cho lưu/nạp thẳng `speaker_emb`+`ref_codes` để synth khỏi cần torch.
- **Web UI thật** (SPA) + phát streaming bằng MediaSource Extensions (MSE) + test
  **a11y (axe-core)** + **Lighthouse** (hoãn từ Giai đoạn 1 — UI test hiện là harness
  dùng-rồi-bỏ; test web dùng bộ ak-web-testing: Playwright + k6).

## Open questions

- Con số budget/cap là **giá trị nháp** (50k ký tự-ngày, 10 req-phút, buffered
  1200 ký tự, stream 20k ký tự, ASR 300s). **→ Phase 5 chốt** từ số đo stress test.
- Streaming rất-dài (cả quyển sách, >100k ký tự): giữ streaming (đơn giản) hay
  chuyển async-job? Đề xuất **giữ streaming + cap 20k** giai đoạn này. **→ Phase 5
  đo CF 524 thật**; nếu xuất hiện → async-job (giai đoạn sau).

## Red Team Review

### Session — 2026-08-30
**Reviewers:** 3 (Security Adversary, Assumption Destroyer, Failure Mode Analyst) ·
Standard tier (Fact Checker + Contract Verifier).
**Findings:** 25 thô → **15 sau khử trùng lặp** (14 accepted, 1 rejected — theo quyết
định chủ dự án). Tất cả có bằng chứng `file:line`.
**Severity:** 4 Critical, 10 High, 1 Medium.

| # | Finding | Sev | Disposition | Applied To |
|---|---------|-----|-------------|------------|
| 1 | `CF-Connecting-IP` giả mạo được + bind fail-open (nginx 0.0.0.0, header verbatim, loopback "tùy chọn", live `.env`=0.0.0.0) | Critical | Accept | P1, P4 |
| 2 | `dev-key` mặc định = TRUSTED không giới hạn + clone CRUD | Critical | **Reject** (chủ dự án tự đổi key; giữ hành vi hiện tại, docs đã nhắc) | — |
| 3 | `fail_after` không hủy được synth đang chạy (`abandon_on_cancel=False`) → timeout vô hiệu | Critical | Accept | P1, P3 |
| 4 | Budget reserve trước synth, không hoàn khi request lỗi | Critical | Accept | P1, P3 |
| 5 | `WORKERS≥2` nhân gate in-memory + SQLite multi-writer | High | Accept | P1, P4 |
| 6 | `/v1/voices` public sẽ liệt kê giọng clone (mâu thuẫn hợp đồng) | High | Accept (giữ public có chủ đích — **sửa lời hợp đồng**, không ẩn clone) | plan.md |
| 7 | ASR đọc 25MB trước gate + charge sau transcribe + `duration` µs≠s | High | Accept | P1, P2 |
| 8 | Streaming không cap số kết nối/IP | High | Accept | P1, P3 |
| 9 | Key IP: IPv6 xoay né budget, NAT gộp, map không TTL | High | Accept | P1 |
| 10 | State volatile reset khi restart → thundering herd | High | Accept | P1, P4 |
| 11 | Result cache: "mirror previews LRU" sai (previews không có LRU) + race + disk-fill | High | Accept | P2 |
| 12 | Counter gate không `finally` → rò slot, nghẽn gate | High | Accept | P1, P3 |
| 13 | Cap thread vô hiệu trên VieNeu ONNX torch-free; acceptance đo sai | High | Accept | P2, P4 |
| 14 | Nối MP3 từng câu chưa kiểm chứng phát được (gapless) | High | Accept | P3 |
| 15 | SQLite sync-on-loop + fail-open infra + settings frozen `@lru_cache` | Medium | Accept | P1 |

**Đã xác minh (không thành finding):** VieNeu **có** serialize nội bộ qua `self._lock`
(`vieneu_backend.py:153`) → `MAX_CONCURRENCY=1` hợp lý; faster-whisper `cpu_threads` là
param thật (ASR OK).

### Whole-Plan Consistency Sweep
- Files reread: `plan.md`, `phase-01`, `phase-02`, `phase-03`, `phase-04`.
- Decision deltas checked: 15 (loopback bắt buộc, HOST default + live `.env`, refund
  budget, WORKERS guard, IP /64+TTL, cold-start+backoff, counter finally, SQLite
  WAL/off-loop/fail-closed, timeout semantics, cache eviction code-mới, thread cgroup,
  ASR probe µs→s + reserve-trước, stream cap/IP + reserve-per-câu, clone discovery
  public, dev-key không-guard).
- Reconciled stale references: 8 (`torch.set_num_threads` mô tả sai lever ×3,
  `info.duration`→`result.duration`, "mẫu previews LRU", WAL reactive, "dừng synth"
  ngụ ý tức thì ×2).
- Unresolved contradictions: **0**. `ak plan validate` → OK.

<!-- slug: public-share-readiness-stage1 -->

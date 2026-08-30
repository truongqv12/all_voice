---
title: "Phase 5: Kiểm thử thực tế qua Cloudflare + Stress test"
status: in-progress
---

<!-- Tooling delivered (k6 scenarios, assert_stateful.py, Playwright stream-e2e,
     report scaffold plans/reports/loadtest-260830-stage1.md). The RUNS below —
     E2E from an external 4G client over the live CF domain, the stress/soak runs,
     and finalizing the drafted gate numbers — require the operator's Cloudflare
     Tunnel + a separate load machine, so they stay unchecked until executed. -->


# Phase 5: Kiểm thử thực tế qua Cloudflare + Stress test

Priority: P1 · Effort: ~1.5–2 ngày · Phụ thuộc: P1–P4 (+ **user đã cấu hình Cloudflare Tunnel + WAF/rate-rule** theo `deploy/cloudflare-tunnel.md`)

## Overview

Chứng minh acceptance cốt lõi của plan — *"1 node CPU không sập/không treo dù bị
lạm dụng"* — bằng **kiểm chứng đầu-cuối THẬT qua domain Cloudflare** (client ngoài
→ CF edge → cloudflared → nginx → API) và một **bộ stress/load test tự động** mô
phỏng tải hợp lệ + lạm dụng. Kết quả dùng để **chốt các con số nháp** (giải quyết
Open Questions của plan). Đây là bước capstone: Phase 1–4 xây phòng thủ, Phase 5
**đo để tin**.

## Requirements

- Functional:
  - E2E qua domain thật: discovery + buffered TTS + streaming đọc file dài chạy
    được **không key** cho client ngoài; app log **IP thật** từ `CF-Connecting-IP`.
  - Trả lời dứt điểm câu hỏi mở **CF 524**: stream file rất dài (> 100s) có sống
    qua giới hạn 100s của Cloudflare không.
  - Bộ stress test tự động (free, ít dep) chạy được cả **local** (thẳng nginx/API,
    loại nhiễu mạng) lẫn **1 lượt qua CF** (thực tế).
  - Mỗi lớp phòng thủ (rate/budget/queue/refund/stream-cap/ASR-gate/loopback/
    counter) có kịch bản kiểm chứng tương ứng.
- Non-functional: công cụ load **không tự ăn hết CPU máy đích** (chạy từ máy khác
  hoặc script async nhẹ); phần lạm dụng chạy **local** để không bị CF coi là tấn
  công domain thật.

## Architecture

### A. E2E thật qua Cloudflare (thủ công + script kiểm chứng)

Chạy từ **client ngoài mạng** (điện thoại 4G / máy khác), gọi domain thật
`https://voice.example.com`:

- **Discovery:** `GET /v1/voices` → 200, thấy preset (+ giọng clone theo #6).
- **Buffered TTS anon** (không `Authorization`) → nhận audio, phát được.
- **Streaming** `/v1/audio/stream` văn bản nhiều câu → mp3 chảy dần, phát trên
  `<audio>` thật → **kiểm #14 (gapless) trên browser đích, qua đường CF thật**.
- **IP thật (#1):** app log IP client ngoài (KHÔNG phải `127.0.0.1`) → chứng minh
  gate đo đúng IP qua `CF-Connecting-IP`.
- **CF 524 (quyết định lớn):** đọc file **rất dài** qua stream, bấm giờ > 100s →
  xác nhận **không** 524 (byte chảy liên tục giữ kết nối). Nếu 524 xuất hiện →
  kích hoạt kế hoạch **async-job** (giai đoạn sau) hoặc giảm `anon_max_chars_stream`.
- **Edge WAF/rate-rule:** bắn vượt ngưỡng rate-rule CF trên `/v1/audio/*` → bị chặn
  ở **edge** (trang chặn CF), xác nhận rate-rule + Bot Fight hoạt động (lớp ngoài
  gate app).

### B. Stress / Load test (tự động, free)

Công cụ (bộ **ak-web-testing**): **k6** (binary standalone, script JS, **KHÔNG cần
npm**) sinh tải cho kịch bản throughput/rate/queue/soak (1–4, 6, 7, 10) — `stages`/
`scenarios` + thresholds p95/error-rate; **helper thin (python + `sqlite3`)** cho
assertion có-state mà k6 làm vụng (refund #4, counter #12, giả `CF-Connecting-IP`
#1 → kịch bản 5, 8, 9); **Playwright** (Chromium/Firefox/WebKit) cho E2E trình duyệt
thật ở phần A (streaming + **gapless #14 cross-browser**). Chạy phần lạm dụng
**local / từ máy khác** thẳng nginx/API; 1 lượt nhẹ qua CF cho thực tế. **a11y
(axe-core) + Lighthouse → hoãn** sang web thật (Giai đoạn sau) — UI Phase 4 là harness
dùng-rồi-bỏ.

Kịch bản (map tới finding/acceptance):

1. **Tải đồng thời hợp lệ:** N client TTS buffered ~1200 ký tự đồng thời → đo
   p50/p95 latency, throughput, CPU/RAM/swap. Xác nhận **không OOM, không treo**;
   `/health` vẫn phản hồi < X ms trong lúc synth (event loop không bị chẹn).
2. **Vượt rate-limit:** 1 IP bắn > `anon_rate_per_min` → **429 ngay** (không chờ),
   envelope OpenAI.
3. **Vượt budget/ngày:** 1 IP bơm tới `anon_chars_per_day` → 429; giả sang "ngày"
   mới → reset.
4. **Queue đầy:** đẩy đồng thời > `max_queue_waiters` → **429 Overloaded ngay**,
   không hang; xác nhận có `request_timeout_s`.
5. **Refund (#4):** bắn loạt request 429/400 → budget **không** bị trừ (net-zero) —
   query trực tiếp `quota.db`.
6. **Stream lạm dụng (#8):** 1 IP mở > `anon_max_streams_per_ip` stream → 429; đo
   RAM **phẳng** (yield từng câu, không buffer cả file).
7. **ASR mem-DoS (#7):** nhiều upload 25MB đồng thời → gate chặn theo header
   **trước khi** đọc body; RAM không nổ.
8. **Giả mạo IP (#1):** bắn nhiều `CF-Connecting-IP` ngẫu nhiên → xác nhận
   loopback-gate bỏ header khi peer non-loopback, và bind localhost + firewall chặn
   gọi thẳng `:8123`/`:8080` từ LAN.
9. **Counter leak (#12):** bắn liên tục request lỗi (bad `style`) → sau đó IP đó
   **vẫn phục vụ được** (per-IP concurrency + waiter về baseline, gate không kẹt).
10. **Soak/độ bền:** tải vừa **30–60 phút** → không rò RAM (map IP có TTL — #9),
    `data/cache` không vượt `result_cache_max_mb`, không crash-loop (systemd backoff).

**Đo & chốt số:** thu p50/p95, tỉ lệ 429 đúng/sai, CPU/RAM/swap đỉnh, mốc bắt đầu
suy giảm → **điều chỉnh con số nháp** trong `config.py`/`.env.example` (chốt Open
Questions). Lưu kết quả thành **report** (stateful, không evergreen).

## Related Code Files

- Create: `scripts/loadtest/*.js` — kịch bản **k6** (ak-web-testing): tải/rate/queue/
  soak (1–4, 6, 7, 10); `stages`/`scenarios`, `http.batch`, thresholds p95 +
  error-rate; đặt header `CF-Connecting-IP` (giả/xoay) qua `params.headers`.
- Create: `scripts/loadtest/assert_stateful.py` — helper thin (`httpx`/`sqlite3`):
  kịch bản 5 (refund → query `quota.db` net-zero), 8 (giả IP → loopback-gate), 9
  (counter leak → IP còn phục vụ); đọc CPU/RAM (`/proc`). Docstring = hướng dẫn dùng
  (không tạo README.md lạc ngoài docs/).
- Create: `tests/e2e/stream-e2e.spec.ts` — **Playwright** cross-browser: stream đọc
  file dài qua CF → `<audio>` phát liền mạch (kiểm **#14 gapless thật**), buffered
  phát, đối chiếu IP thật xuống app (log). Chạy từ máy dev/CI.
- Create: report `plans/reports/loadtest-<YYMMDD>-stage1.md` — số đo + số chốt +
  quyết định CF 524 (stateful record).
- Modify: `app/config.py` + `.env.example` — cập nhật con số cuối **nếu** đo lệch nháp.
- Modify: `docs/deployment.md` — mục "Kiểm thử thực tế qua Cloudflare + chạy stress
  test": cài **k6** (binary, không npm) + **Playwright** (Node, chỉ máy dev/CI —
  KHÔNG cài browser lên box prod); cách chạy k6 + `assert_stateful.py` + Playwright,
  cách đọc số, cách chốt config; lưu ý chạy phần lạm dụng local / tắt tạm rate-rule
  CF khi đo.

## Implementation Steps

1. **k6** `scripts/loadtest/*.js`: kịch bản tải/rate/queue/soak (1–4, 6, 7, 10) với
   `stages`/`scenarios` + thresholds p95/error-rate; header `CF-Connecting-IP` giả.
   `assert_stateful.py`: kịch bản có-state (5 refund, 8 giả IP, 9 counter) + sampler
   CPU/RAM/swap. Cả hai chạy `--local`/`--cf`.
2. **A. E2E CF:** thủ công checklist mục A từ client 4G (discovery, buffered, stream,
   IP thật, **đo CF 524** file dài, WAF/rate-rule) + **Playwright** `stream-e2e.spec.ts`
   cross-browser (Chromium/Firefox/WebKit) cho streaming/gapless #14. Ghi kết quả.
3. **B. Stress:** chạy k6 (1–4, 6, 7, 10) + `assert_stateful.py` (5, 8, 9) **thẳng vào
   nginx/API** (từ máy khác nếu tải nặng). Thu số; xác nhận acceptance (không sập/treo,
   429 đúng, refund, RAM phẳng, counter không kẹt, soak sạch).
4. **Chốt số:** so số đo với nháp; cập nhật `config.py`/`.env.example`; ghi lý do.
5. **1 lượt qua CF:** chạy 1 kịch bản tải vừa qua domain (không phải phần "tấn công"
   nặng) để xác nhận số liệu thực tế qua edge không lệch nhiều.
6. Viết report `plans/reports/loadtest-<ngày>-stage1.md` + cập nhật `docs/deployment.md`.
7. **Quyết định CF 524:** nếu stream dài **không** 524 → giữ nguyên; nếu **có** →
   ghi Open Question, giảm cap trước mắt, lên lịch async-job (giai đoạn sau).

## Todo

- [x] `scripts/loadtest/*.js`: kịch bản **k6** (1–4, 6, 7, 10) + thresholds p95/error-rate + header CF-IP giả (throughput/rate-limit/budget/queue/stream-abuse/asr-memdos/soak + common.js)
- [x] `scripts/loadtest/assert_stateful.py`: kịch bản có-state (5 refund, 8 reachability, 9 counter) + sampler CPU/RAM/swap từ `/proc`
- [x] `tests/e2e/stream-e2e.spec.ts`: **Playwright** cross-browser (chromium/firefox/webkit) stream + gapless #14 + buffered; đọc `E2E_BASE_URL`
- [x] `docs/deployment.md`: mục "Kiểm thử thực tế qua Cloudflare + chạy stress test" (cài k6 + cách chạy + đọc số)
- [x] Report scaffold `plans/reports/loadtest-260830-stage1.md` (bảng số nháp + kịch bản + CF 524 + sign-off)
- [ ] **(operator)** A. E2E qua CF thật: discovery + buffered + stream + IP thật (checklist + Playwright)
- [ ] **(operator)** A. Đo **CF 524** với file rất dài (> 100s) → quyết định giữ stream / async-job
- [ ] **(operator)** A. Xác nhận WAF/rate-rule CF chặn ở edge
- [ ] **(operator)** B. Stress local kịch bản 1–4 (tải/rate/budget/queue → 429 ngay, không treo)
- [ ] **(operator)** B. Kịch bản 5–7 (refund #4, stream-cap #8, ASR mem-DoS #7)
- [ ] **(operator)** B. Kịch bản 8–9 (reachability #1, counter leak #12)
- [ ] **(operator)** B. Kịch bản 10 soak 30–60′ (RAM/cache/crash-loop)
- [ ] **(operator)** Chốt số vào `config.py`/`.env.example` từ số đo; điền report load-test

## Success Criteria

- [ ] E2E qua **domain thật** (client 4G ngoài): anon TTS + stream chạy; app log **IP thật** từ `CF-Connecting-IP` (không phải `127.0.0.1`).
- [ ] Stream file dài **> 100s** không dính **CF 524** — HOẶC đã kết luận cần async-job và ghi rõ chuyển giai đoạn sau (câu hỏi mở được đóng).
- [ ] **Playwright** cross-browser (Chromium/Firefox/WebKit): stream mp3 phát **gapless** qua CF (đóng #14 trên browser thật).
- [ ] Dưới tải đồng thời + lạm dụng (k6 + helper): box **không OOM, không treo**; `/health` vẫn phản hồi; mọi vượt-ngưỡng → **429 ngay**, không hang; k6 thresholds (p95/error-rate) đạt.
- [ ] Refund đúng (429/400 → không trừ budget); counter không kẹt sau loạt lỗi; RAM **phẳng** khi stream + soak 30–60′ không rò.
- [ ] WAF/rate-rule Cloudflare chặn được flood ở **edge** (lớp ngoài gate app).
- [ ] Con số budget/cap được **chốt** từ số đo; report load-test lưu tại `plans/reports/`.

## Risk Assessment

- **Stress test vào domain public bị CF coi là tấn công:** *Tín hiệu:* IP bị CF
  challenge/ban. *Xử lý:* chạy phần lạm dụng **local (thẳng nginx/API)**; qua CF chỉ
  1 lượt tải vừa; hoặc tạm tắt rate-rule khi đo rồi bật lại.
- **Công cụ load tự ăn CPU máy i5 → sai số:** *Tín hiệu:* CPU của k6/Playwright cao
  ngang server. *Xử lý:* chạy **k6 + Playwright từ máy khác** trong LAN (không chạy
  trên chính box prod); Playwright browsers chỉ cài ở dev/CI.
- **CF 524 phụ thuộc hành vi thực (doc CF mơ hồ):** *Tín hiệu:* 524 trên stream dài.
  *Xử lý:* đã có kế hoạch async-job (giai đoạn sau) + cap `anon_max_chars_stream` —
  không phá plan, chỉ chuyển scope.
- **Số nháp lệch xa thực tế:** *Tín hiệu:* box suy giảm dưới cả tải nhẹ, hoặc cap quá
  chặt chặn người dùng thật. *Xử lý:* chốt lại từ số đo (đây chính là mục tiêu phase);
  ghi lý do trong report.

---
title: "Phase 4: Edge (nginx + Tunnel) + UI test + docs"
status: done
---

# Phase 4: Edge (nginx + Tunnel) + UI test + docs

Priority: P1 · Effort: ~1.5 ngày · Phụ thuộc: P1–P3

## Overview

Đưa lên "cửa công khai": **API ẩn ở `127.0.0.1`**, **nginx** serve UI test +
proxy `/v1/*` (cap body, tắt buffering, chuyển IP thật), **Cloudflare Tunnel**
(user tự cấu hình CF), **1 `index.html` vanilla JS** để kiểm chứng đầu-cuối, và
cập nhật docs/`.env.example`. UI "xịn" để giai đoạn sau.

## Requirements

- Functional:
  - API bind `127.0.0.1:8123` (không lộ ra mạng); chỉ nginx tới được.
  - nginx: serve `web/index.html`; `location /v1/` → `127.0.0.1:8123` với
    `proxy_buffering off`, `proxy_read_timeout 300s`, `client_max_body_size 25m`,
    chuyển `CF-Connecting-IP`.
  - cloudflared: hostname → `http://localhost:8080` (nginx); 0 port inbound.
  - UI: chọn voice (`GET /v1/voices`), nhập text / nạp `.txt`, nút "Đọc" (buffered)
    và "Đọc file dài" (stream), phát audio, hiện lỗi 429/quota.
- Non-functional: mọi thứ **free**; không tự động hoá tài khoản CF (user làm);
  docs đủ để dựng lại từ máy trắng.

## Architecture

- **Bind localhost (#1):** đổi `HOST=127.0.0.1` trong **live `.env`** (KHÔNG chỉ
  `.env.example`) + đổi **default** trong `config.py` và `install-service.sh` sang
  `127.0.0.1` (fail-closed nếu quên). Firewall lớp 2: chặn ngoài vào `:8123` (vd
  `sudo ufw deny 8123/tcp`, hoặc iptables chỉ cho loopback) — ghi lệnh cụ thể trong doc.
- **Thread/CPU cap ở systemd:** `Environment=OMP_NUM_THREADS=4` (cap trước khi nạp
  model, bổ trợ P2). **[#13]** vì onnxruntime có thể **bỏ qua** env đó, thêm chặn
  cứng CPU: `CPUQuota=` (cgroup) hoặc `AllowedCPUs=`/`taskset` cho synth preset.
  **[#10]** backoff crash-loop: `RestartSec=`, `StartLimitIntervalSec=`,
  `StartLimitBurst=`. **[#5]** giữ `WORKERS=1` khi anon bật (tăng WORKERS phá gate
  in-memory + SQLite multi-writer — doc cảnh báo).
- **nginx (systemd, `apt install nginx`):** file mẫu `deploy/nginx.conf.example`:
  ```nginx
  server {
      listen 127.0.0.1:8080;                   # chỉ localhost — cloudflared dial vào đây (#1)
      client_max_body_size 25m;
      root /var/www/all-voice;                 # chứa index.html
      location / { try_files $uri /index.html; }
      location /v1/ {
          proxy_pass http://127.0.0.1:8123;
          proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
          proxy_http_version 1.1;
          proxy_buffering off;                 # cho mp3 stream chảy ngay (né CF 524)
          proxy_read_timeout 300s;
      }
  }
  ```
- **cloudflared (user cấu hình):** doc `deploy/cloudflare-tunnel.md`:
  `cloudflared tunnel create all-voice` → `config.yml` ingress
  `hostname: voice.example.com → service: http://localhost:8080` → `tunnel route
  dns` → chạy như service. Kèm checklist CF dashboard: **1 rate-rule** trên
  `/v1/audio/*`, **5 WAF rule** (chặn scanner UA/path lạ), **Bot Fight Mode**.
- **UI test (`web/index.html`):** vanilla JS, không build. `fetch('/v1/voices')`
  đổ dropdown; `<textarea>` + `<input type=file accept=".txt">` (FileReader);
  nút buffered → `POST /v1/audio/speech` → `blob` → `<audio>`; nút stream →
  `POST /v1/audio/stream` → phát (blob cho đơn giản giai đoạn này; ghi chú MSE cho
  web thật). Hiện message lỗi khi 400/429.

## Related Code Files

- Create: `web/index.html` — UI test vanilla JS (+ CSS tối giản inline).
- Create: `tests/e2e/ui-smoke.spec.ts` — **Playwright** smoke (ak-web-testing): mở
  `http://localhost:8080`, voices dropdown load, bấm "Đọc" → `<audio>` phát (buffered),
  bấm "Đọc file dài" → stream phát, hiện lỗi 429 đúng. Chạy từ **máy dev/CI** (không
  cài lên box prod). Scaffold bằng script init của skill hoặc `npm init playwright`.
- Create: `deploy/nginx.conf.example` — reverse proxy mẫu (ở trên).
- Create: `deploy/cloudflare-tunnel.md` — hướng dẫn cloudflared + checklist CF dashboard.
- Modify: `deploy/install-service.sh` — `Environment=OMP_NUM_THREADS=...`; **[#13]** `CPUQuota=`/`AllowedCPUs=`; **[#10]** `RestartSec=`/`StartLimitIntervalSec=`/`StartLimitBurst=`; đổi default HOST→`127.0.0.1`; **[#5]** cảnh báo WORKERS>1.
- Modify: **live `.env`** — `HOST=127.0.0.1` (#1, ngoài `.env.example`).
- Modify: `app/config.py` — default `host` → `127.0.0.1` (#1, fail-closed).
- Modify: `.env.example` — `HOST=127.0.0.1`, ghi chú Tunnel/nginx, gom biến gate/budget từ P1–P3.
- Modify: `docs/deployment.md` — mục "Public qua Cloudflare Tunnel + nginx (API ẩn localhost)".
- Modify: `docs/kien-truc-va-mo-rong.md` — thêm mục tầng anon-gate + streaming + topology 1 cửa; ghi "Giai đoạn sau".
- Modify: `README.md` — 1 dòng trỏ tới cách chạy public + UI test (tùy chọn).

## Implementation Steps

1. **[#1]** Đổi `HOST=127.0.0.1` trong **live `.env` VÀ `.env.example`** + default
   `config.py`/`install-service.sh` → `127.0.0.1`; giải thích API chỉ nghe localhost,
   nginx là cửa; thêm lệnh firewall chặn `:8123` từ ngoài.
2. `deploy/nginx.conf.example` theo mẫu; ghi bước `apt install nginx`, copy `web/` → `/var/www/all-voice`, `nginx -t && systemctl reload nginx`.
3. `deploy/install-service.sh`: chèn vào unit `Environment=OMP_NUM_THREADS=4`,
   **[#13]** `CPUQuota=`/`AllowedCPUs=`, **[#10]** `RestartSec=`/`StartLimitIntervalSec=`/`StartLimitBurst=`;
   đổi default HOST→127.0.0.1; **[#5]** cảnh báo không tăng WORKERS khi anon bật; giữ đọc HOST/PORT.
4. `web/index.html`: viết UI test (voices dropdown, textarea + nạp .txt, 2 nút buffered/stream, `<audio>`, hiển thị lỗi).
5. `deploy/cloudflare-tunnel.md`: các bước cloudflared + `config.yml` mẫu + checklist CF (rate-rule/WAF/Bot Fight). Nhấn: **user tự làm phần CF**.
6. Cập nhật `docs/deployment.md`, `docs/kien-truc-va-mo-rong.md` (topology + gate + streaming + "Giai đoạn sau"), README 1 dòng.
7. Kiểm chứng đầu-cuối local: chạy API `127.0.0.1:8123` + nginx `:8080`; mở `http://localhost:8080`, đọc thử buffered + stream; xác nhận `curl 127.0.0.1:8123/v1/...` chỉ chạy từ máy, và `http://localhost:8080/v1/...` proxy đúng, IP thật xuống app (log).
8. **Playwright smoke** (ak-web-testing): scaffold `tests/e2e/` (script init của skill hoặc `npm init playwright`), viết `ui-smoke.spec.ts` chạy vào `http://localhost:8080` → voices load + buffered phát + stream phát + lỗi 429 hiển thị. Chạy từ máy dev/CI.

## Todo

- [x] `.env.example` + **live `.env`** + default `config.py`/`install-service.sh`: `HOST=127.0.0.1` (#1) + gom biến + ghi chú Tunnel/nginx + lệnh firewall `:8123`
- [x] `deploy/nginx.conf.example`: `listen 127.0.0.1:8080` (#1) + buffering off + body cap + CF-IP
- [x] `deploy/install-service.sh`: `OMP_NUM_THREADS` + **[#13]** `CPUQuota`/`AllowedCPUs` + **[#10]** `RestartSec`/`StartLimitIntervalSec`/`StartLimitBurst` + **[#5]** refuse anon+`WORKERS>1`
- [x] `web/index.html`: UI test (voices + text/.txt + buffered/stream + lỗi)
- [x] `deploy/cloudflare-tunnel.md`: cloudflared + checklist CF dashboard
- [x] `docs/deployment.md` + `docs/kien-truc-va-mo-rong.md` + README cập nhật
- [x] Kiểm chứng đầu-cuối local: API bind `127.0.0.1` only, `/v1/models`+`/v1/voices` public (200 no key), clone CRUD 401, real IP logged. (Chạy nginx thật là bước deploy.)
- [x] `tests/e2e/ui-smoke.spec.ts`: Playwright smoke UI (voices + buffered + stream + lỗi 429) — mock `/v1/*`, self-contained.

## Success Criteria

- [ ] Mở `http://localhost:8080` → UI test đọc được (buffered + stream) qua nginx.
- [ ] [#1] **Live `.env`** = `HOST=127.0.0.1`; nginx `listen 127.0.0.1:8080`; từ máy khác trong LAN gọi `:8123` và `:8080` → **không** kết nối được.
- [ ] [#1] App **bỏ qua** `CF-Connecting-IP` khi peer non-loopback (chỉ tin khi qua nginx-loopback); log IP thật khi gọi qua nginx.
- [ ] [#13] Unit có `CPUQuota=`/`AllowedCPUs=`; đo synth preset không ăn hết 6 core.
- [ ] [#10] Unit có `RestartSec`/`StartLimitIntervalSec` (crash-loop không dồn dập).
- [ ] [#5] `docs/deployment.md` cảnh báo `WORKERS>1` phá gate khi anon bật.
- [ ] `nginx -t` pass; `deploy/cloudflare-tunnel.md` đủ để user tự dựng Tunnel.
- [ ] `docs/deployment.md` + `.env.example` phản ánh đúng cấu hình mới.
- [ ] **Playwright smoke** `ui-smoke.spec.ts` xanh (voices load + buffered + stream + lỗi 429) từ máy dev.

## Risk Assessment

- **nginx đệm mất streaming:** thiếu `proxy_buffering off` → mp3 bị gom → CF 524.
  *Tín hiệu:* stream không chảy dần / 524. *Xử lý:* bắt buộc `proxy_buffering off`
  + `X-Accel-Buffering: no` (P3); kiểm chứng bằng mắt khi test.
- **Quên đổi HOST → API vẫn `0.0.0.0` (#1):** *Tín hiệu:* API gọi được từ mạng ngoài.
  *Xử lý:* đổi **default** HOST→127.0.0.1 (fail-closed) + sửa **live `.env`** +
  loopback-gate bắt buộc (P1) + firewall chặn `:8123` (lệnh cụ thể trong doc);
  success-criteria kiểm tra trực tiếp.
- **[#5] Operator tăng WORKERS phá gate:** *Tín hiệu:* limit thành N×, `database is
  locked`. *Xử lý:* refuse start khi anon+`workers>1` (P1) + doc cảnh báo rõ.
- **User cấu hình CF sai (không bật rate-rule/WAF):** *Tín hiệu:* lạm dụng vượt
  qua edge. *Xử lý:* gate app (P1) vẫn chặn theo chi phí thật — edge chỉ là lớp
  thêm; checklist rõ trong doc.

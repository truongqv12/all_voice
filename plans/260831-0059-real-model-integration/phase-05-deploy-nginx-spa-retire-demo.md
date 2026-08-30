---
phase: 5
title: "Deploy: nginx serve SPA + retire demo cũ"
status: pending
priority: P1
effort: "0.5d"
dependencies: [2, 3, 4]
---

# Phase 5: Deploy nginx SPA + retire demo cũ

## Overview

Cho nginx serve **SPA `frontend/dist`** thay vì `web/index.html`, giữ proxy `/v1` same-origin, và **retire demo cũ**. May mắn: `deploy/nginx.conf.example` **đã** có `try_files … /index.html` (SPA-style) + `proxy_buffering off` (hợp stream) + `client_max_body_size 25m` (hợp ASR) — nên thay đổi hạ tầng **tối thiểu**: đổi nguồn docroot (build FE) + cập nhật comment/doc + xoá artifact cũ.

Skills: `ak:deploy`/`ak:devops` (nginx/systemd/CF Tunnel topology), `ak:docs` (cập nhật `docs/deployment.md`), `ak:docs-seeker` (nginx SPA + cache-control hiện hành).

## Requirements

- Functional:
  - Build FE: `cd frontend && npm ci && npm run build` → `frontend/dist/` (đã cấu hình Vite).
  - Docroot lấy từ `frontend/dist/*` (thay `web/*`). `try_files $uri /index.html` phục vụ deep-link `/transcribe` (và `/clone` sẽ redirect ở app-level).
  - Proxy `/v1/` giữ nguyên (streaming-friendly). Same-origin ⇒ không CORS.
  - **Retire `web/index.html`**: xoá file + gỡ mọi tham chiếu phục vụ nó (nginx comment, docs, install steps). E2E cũ test `web/index.html` (`tests/e2e/*`) **gỡ/thay** (e2e mới ở phase 6).
  - **[Goal-warmup: GO-LIVE IN SCOPE]** Deploy SPA lên **:8123 public thật** (thay demo): `cd frontend && npm ci && npm run build` → `sudo cp -r frontend/dist/* /var/www/all-voice/` (docroot root-owned) → `sudo nginx -t && sudo systemctl reload nginx` (graceful, ~0 downtime). **GIỮ NGUYÊN** uvicorn :8124 (không đổi backend code → không restart/kill) + cloudflared tunnel. Sau reload: kiểm `curl -s http://127.0.0.1:8123/` trả SPA mới + `curl -s http://127.0.0.1:8123/v1/voices` vẫn 200.
- Non-functional: cache-control cho asset băm tên (`/assets/*` immutable) + `index.html` no-cache (tránh kẹt bản cũ); giữ topology CF Tunnel :8123→app:8124; không mở port ra LAN; **không gián đoạn API :8124 + tunnel**.

## Architecture

- **nginx.conf.example** (sửa nhẹ):
  - Comment install: đổi `sudo cp -r web/* /var/www/all-voice/` → build rồi `sudo cp -r frontend/dist/* /var/www/all-voice/`.
  - `root /var/www/all-voice;` giữ; comment "Test UI (web/index.html)" → "SPA (frontend/dist)".
  - (Tùy chọn, khuyến nghị) thêm block cache asset:
    ```nginx
    location /assets/ { try_files $uri =404; expires 1y; add_header Cache-Control "public, immutable"; }
    location = /index.html { add_header Cache-Control "no-cache"; }
    ```
    (đặt trước `location /`).
  - Giữ `location /v1/ { proxy_buffering off; ... }`.
- **docs/deployment.md**: mục "nginx là cửa" + block `cp -r web/*` → quy trình build + copy `frontend/dist`; ghi rõ retire demo, deep-link SPA.
- **README.md** (dòng ~308) + **docs/kien-truc-va-mo-rong.md** (~493): cập nhật câu "UI hiện tại chỉ web/index.html vanilla" → SPA `frontend/`.
- **tests/e2e (cũ)**: `tests/e2e/ui-smoke.spec.ts` + `playwright.config.ts` + `README.md` phục vụ `web/index.html` — **gỡ** (thay bằng e2e SPA phase 6). Xác nhận CI không phụ thuộc trước khi xoá.

## Related Code Files

- Modify: `deploy/nginx.conf.example` (docroot source + comments + cache block)
- Modify: `docs/deployment.md` (build+serve dist, retire demo)
- Modify: `README.md`, `docs/kien-truc-va-mo-rong.md` (câu mô tả UI)
- Modify: `deploy/install-service.sh` (nếu có bước liên quan docroot — hiện không; xác nhận)
- Delete: `web/index.html` (+ thư mục `web/` nếu rỗng)
- Delete/replace: `tests/e2e/ui-smoke.spec.ts`, `tests/e2e/playwright.config.ts`, `tests/e2e/README.md` (phối hợp phase 6)

## Implementation Steps

1. `grep` xác nhận toàn bộ tham chiếu `web/index.html` / `cp -r web` / docroot (đã liệt kê ở plan).
2. Build FE thật; kiểm `dist/` có `index.html` + `assets/`.
3. Sửa `nginx.conf.example` (docroot source, comments, cache block).
4. Cập nhật `docs/deployment.md` + README + kien-truc.
5. Gỡ e2e cũ (sau khi phase 6 có e2e mới, hoặc gỡ trước + phase 6 thêm mới — chọn thứ tự để CI không đỏ).
6. Xoá `web/index.html`.
7. Chạy thử cục bộ: `npm run build && (serve dist qua nginx local hoặc `vite preview` :4273)` + app :8124; kiểm `/`, deep-link `/transcribe`, `/v1/voices` qua origin.

## Success Criteria

- [ ] `npm run build` ra `frontend/dist` phục vụ được; `/` + deep-link `/transcribe` OK (SPA fallback), `/clone` redirect.
- [ ] `/v1/*` proxy chạy same-origin; stream không bị nginx buffer (nghe TTS dài mượt).
- [ ] `web/index.html` đã xoá; **không** còn tham chiếu phục vụ nó trong nginx/docs/install.
- [ ] E2E cũ (web demo) đã gỡ; CI/không đỏ vì thiếu file.
- [ ] `docs/deployment.md` mô tả đúng quy trình build+serve dist + retire demo.
- [ ] **GO-LIVE**: `:8123` public phục vụ **SPA mới** (không còn demo); `curl :8123/` = SPA, `curl :8123/v1/voices` = 200; **uvicorn :8124 + cloudflared không gián đoạn** (không restart).

## Risk Assessment

- **Rủi ro:** xoá `web/index.html` làm đỏ CI (e2e cũ). **Tín hiệu:** Playwright cũ fail "file not found". **Ứng phó:** gỡ/thay e2e cũ **trước hoặc cùng lúc** (phase 6 điều phối); grep CI config trước xoá.
- **Rủi ro:** browser kẹt `index.html` bản cũ sau deploy. **Tín hiệu:** user thấy UI cũ/asset 404. **Ứng phó:** `Cache-Control: no-cache` cho `index.html`, immutable cho `/assets` băm tên.
- **Rủi ro:** dev proxy vs prod base khác nhau gây gọi sai path. **Tín hiệu:** 404 `/v1` ở prod. **Ứng phó:** base mặc định `/v1` tương đối (same-origin) chạy cả dev (proxy) lẫn prod (nginx) — 1 giá trị, không phân nhánh.
- **Rủi ro:** thay đổi `nginx.conf.example` là **file mẫu**, máy thật cần copy lại. **Ứng phó:** ghi rõ trong `docs/deployment.md` bước cập nhật site + `nginx -t && reload`.

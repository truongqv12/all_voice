# Triển khai (Deployment)

Self-hosted trên máy Linux/macOS. App là service Python quản lý bằng `uv`;
không cần DB, không cần cài FFmpeg hệ thống (PyAV đã kèm), không cần cài Python
tay (uv tự tải Python 3.12).

## Nền tảng
Máy chủ tự quản (VPS/bare-metal). Chạy nền bằng **systemd** trên Linux.

## Lệnh triển khai (máy mới)

```bash
git clone <repo> all-voice && cd all-voice   # hoặc copy source (kèm uv.lock, .python-version)
bash deploy/setup.sh                         # cài uv + deps (gồm PyTorch cho voice clone)
nano .env                                     # đặt API_KEYS thật, chỉnh PORT/DEVICE nếu cần
sudo bash deploy/install-service.sh           # chạy nền như service (Linux)
```

Không cần voice cloning (nhẹ hơn, không tải PyTorch): `CLONE=0 bash deploy/setup.sh`.

Model VieNeu (~313MB) tải tự động ở **request synth đầu tiên** về
`~/.cache/huggingface/hub` (đổi chỗ bằng `HF_HOME` trong `.env`).

## Scripts trong `deploy/`

| File | Việc |
|---|---|
| `deploy/setup.sh` | Cài `uv`, `uv sync --frozen [--extra clone]`, tạo `.env` + `logs/`. Idempotent. |
| `deploy/install-service.sh` | Sinh unit systemd theo path/user/PORT thật, `enable --now`. Linux, cần `sudo`. |

## Biến môi trường (`.env`)

`API_KEYS` (bắt buộc đổi khỏi `dev-key`) · `DEVICE` (cpu/cuda/auto) ·
`DEFAULT_BACKEND` · `MAX_CONCURRENCY` · `VOICES_DIR` · `HOST` (**mặc định
`127.0.0.1`** — loopback, ẩn sau nginx; xem "Public qua Cloudflare Tunnel") ·
`PORT` (mặc định 8123) · `LOG_LEVEL` · `LOG_DIR` · `HF_HOME`.

Tầng công khai không cần key (anon gate) + streaming + cache kết quả: các biến
`ANON_ENABLED`, `ANON_RATE_PER_MIN`, `ANON_BURST`, `ANON_CHARS_PER_DAY`,
`ANON_AUDIO_SECONDS_PER_DAY`, `ANON_MAX_*`, `MAX_QUEUE_WAITERS`, `REQUEST_TIMEOUT_S`,
`INFERENCE_THREADS`, `ASR_CPU_THREADS`, `RESULT_CACHE_*` — bảng đầy đủ + mặc định
nằm trong `.env.example` và `app/config.py`. Xem mục "Public qua Cloudflare Tunnel"
bên dưới.

Engine tuỳ chọn (bảng đầy đủ + mặc định: `app/config.py`, README mục "Engines"):
`ENABLE_KOKORO` · `KOKORO_MODEL_PATH` · `KOKORO_VOICES_PATH` · `KOKORO_DEFAULT_VOICE` ·
`ENABLE_VOICEVOX` · `VOICEVOX_DICT_DIR` · `VOICEVOX_VVM_DIR` · `VOICEVOX_ONNXRUNTIME` ·
`VOICEVOX_SPEAKER_ALLOWLIST`.

Nghe thử giọng (preview): `PREVIEWS_DIR` (mặc định `data/previews`, **xóa được** —
tự tạo lại) · `PREVIEW_WARM_ON_STARTUP` (warm backend mặc định + clone lúc khởi
động, chạy nền) · `PREVIEW_CONCURRENCY` (ngân sách CPU **riêng** cho preview, tách
khỏi `MAX_CONCURRENCY` nên preview không giành CPU của `/v1/audio/speech` + ASR;
mặc định 1) · `PREVIEW_TEXT_VI` / `PREVIEW_TEXT_EN` / `PREVIEW_TEXT_JA` (đổi câu
mẫu, để trống = câu mặc định). Với `WORKERS≥2`, preview lưu **mỗi file một sidecar**
(`{slug}.mp3.json`) nên không có tranh chấp manifest dùng chung.

## Engine tiếng Anh (Kokoro) & Nhật (VOICEVOX)

Tuỳ chọn, tách khỏi base install. Bật engine mà **chưa tải asset** thì backend tự
bỏ qua (không phá startup); tắt hẳn bằng `ENABLE_KOKORO=false` / `ENABLE_VOICEVOX=false`.

- **Tiếng Anh (Kokoro):** cần system package **`espeak-ng`** cho G2P —
  `sudo apt-get install -y espeak-ng`. Rồi `uv sync --extra en` +
  `bash scripts/fetch-kokoro.sh` (model int8 **~88 MB** + voices vào `models/kokoro/`).
- **Tiếng Nhật (VOICEVOX):** `uv sync --extra ja` + `bash scripts/fetch-voicevox.sh`
  (cài wheel `voicevox_core` từ GitHub release + tải OpenJTalk dict + VVM vào
  `models/voicevox/`). **Credit:** ghi công nhân vật khi phát hành audio (xem README).
- **RAM / lazy-load:** mỗi engine bật chỉ nạp model ở **request đầu** cho ngôn ngữ
  đó; VOICEVOX nạp **từng VVM theo style** khi cần → startup không phình RAM. Vẫn
  khuyến nghị **giữ 1 worker** (mỗi worker giữ bản model riêng). Đĩa: `models/` không
  commit (đã `.gitignore`), tổng dung lượng tuỳ engine bật.

## Vận hành service (Linux)

```bash
systemctl status all-voice            # trạng thái
journalctl -u all-voice -f            # log realtime (hoặc: tail -f logs/server.log)
sudo systemctl restart all-voice      # khởi động lại
sudo systemctl disable --now all-voice # dừng + tắt autostart
```

- Service tự khởi động lại khi crash (`Restart=always`) và khi reboot máy.
- **1 worker mặc định** (đổi bằng `WORKERS=N sudo bash deploy/install-service.sh`). Mỗi
  worker nạp **bản model TTS + ASR riêng** vào RAM, mà inference lại **CPU-bound**
  (CTranslate2/torch chiếm hết nhân) — thêm worker chỉ tốn thêm RAM chứ không tăng
  throughput trên máy 1 node. Chỉ tăng `WORKERS` khi có nhiều CPU/RAM rảnh và cần chịu
  tải song song thật.
- **Giọng clone khi chạy nhiều worker (`WORKERS≥2`):** danh sách/xóa giọng dùng chung
  `registry.json` (store đọc lại đĩa mỗi lần) nên xóa được ở bất kỳ worker nào. Nhưng
  giọng clone đã enrol để **synth** nằm trong RAM của **đúng worker tạo nó** cho tới
  khi restart — worker khác chưa có sẽ rơi về preset đầu tiên. Muốn mọi worker synth
  được giọng vừa tạo ngay: `sudo systemctl restart all-voice` (khởi động lại enrol
  toàn bộ từ `registry.json`). Với mặc định 1 worker thì không gặp vấn đề này.
- `logs/server.log` gom stdout+stderr (bắt cả log uvicorn và segfault native);
  `logs/app.log` là log ứng dụng xoay vòng (startup/request/synth/lỗi 500).

## Public qua Cloudflare Tunnel + nginx (API ẩn ở localhost)

Mở dịch vụ ra internet cho **người dùng free, không cần đăng nhập**, chạy trên
**1 máy CPU** mà không sập/treo khi bị lạm dụng. Kiến trúc "1 cửa":

```
internet → Cloudflare edge → cloudflared (outbound) → nginx 127.0.0.1:8080 → API 127.0.0.1:8123
```

- **API ẩn hoàn toàn:** `HOST=127.0.0.1` (mặc định) — API chỉ nghe loopback, **không**
  lộ ra LAN. Chỉ nginx (cũng ở localhost) tới được. Ngoài ra chặn thẳng cổng ở
  firewall: `sudo ufw deny 8123/tcp`.
- **nginx là cửa:** serve UI test (`web/index.html`) + proxy `/v1/*` với
  `proxy_buffering off` (cho mp3 stream chảy ngay, né timeout 524 của Cloudflare),
  `client_max_body_size 25m`, và chuyển `CF-Connecting-IP` xuống app. App **chỉ tin**
  header IP này khi peer là loopback (qua nginx) — request gọi thẳng không giả mạo
  được IP. File mẫu: `deploy/nginx.conf.example`.
- **Cloudflare Tunnel (user tự cấu hình):** `cloudflared` mở kết nối **ra ngoài** tới
  edge, **0 cổng inbound**, 0 IP công khai. Các bước + `config.yml` mẫu + **checklist
  dashboard CF** (rate-rule trên `/v1/audio/*`, WAF chặn scanner, Bot Fight Mode):
  `deploy/cloudflare-tunnel.md`.

**Tầng tự bảo vệ trong app (bật bằng `ANON_ENABLED=true`).** Không phụ thuộc edge —
edge chỉ là lớp thêm. App gate theo **chi phí thật**:

- Rate-limit token-bucket theo IP + **ngân sách ngày** (ký tự cho TTS, giây audio cho
  ASR) lưu SQLite; hoàn ngân sách khi lỗi. IP ẩn danh vượt hạn → 429/413 **ngay**,
  không treo.
- Admission control: giới hạn đồng thời + hàng đợi có trần → từ chối nhanh thay vì
  ôm request tới sập. Văn bản dài → dùng `/v1/audio/stream` (đọc file dài, mp3 stream).
- Có **API key hợp lệ** = tier TRUSTED (bỏ qua rate/budget). Không key = tier ẩn danh
  (bị gate). CRUD giọng clone vẫn **bắt buộc key**; khám phá (`/v1/voices`, `/v1/models`,
  nghe thử) là công khai.

> ⚠️ **Giữ `WORKERS=1` khi `ANON_ENABLED=true`.** Gate chạy in-memory theo tiến trình
> + ngân sách SQLite một-người-ghi; tăng worker sẽ nhân giới hạn lên N lần và gây
> `database is locked`. App **từ chối khởi động** với tổ hợp anon + `workers>1`, và
> `deploy/install-service.sh` cũng chặn combo này.

**Chặn CPU ở systemd (bổ trợ giới hạn thread trong app).** Vì onnxruntime có thể **bỏ
qua** `OMP_NUM_THREADS`, `deploy/install-service.sh` đặt cả `Environment=OMP_NUM_THREADS`
lẫn chặn cứng **`CPUQuota=400%`** (≈4 nhân, chừa nhân cho nginx + OS) — pin nhân cụ thể
bằng `CPU_ALLOWED=0-3`. Kèm backoff crash-loop (`StartLimitIntervalSec`/`StartLimitBurst`)
để một cấu hình hỏng không dồn dập restart.

Các bước gọn (sau khi đã `install-service.sh` cho API):

```bash
sudo apt install nginx
sudo mkdir -p /var/www/all-voice && sudo cp -r web/* /var/www/all-voice/
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/all-voice
sudo ln -sf /etc/nginx/sites-available/all-voice /etc/nginx/sites-enabled/all-voice
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
# rồi làm theo deploy/cloudflare-tunnel.md để dựng Tunnel + checklist CF.
```

## Kiểm thử thực tế qua Cloudflare + chạy stress test

Chứng minh *"1 node CPU không sập/không treo dù bị lạm dụng"* và **chốt các con số**
của anon-gate. Công cụ nằm ở `scripts/loadtest/` (k6 + helper Python) và `tests/e2e/`
(Playwright). Report mẫu: `plans/reports/loadtest-260830-stage1.md`.

> ⚠️ Chạy phần **lạm dụng** thẳng vào nginx/API **từ máy khác trong LAN** (hoặc trên
> chính box nếu chỉ đo nhẹ) — **đừng** bắn vào domain CF công khai (CF sẽ coi là tấn
> công và challenge/ban). Qua CF chỉ chạy **1 lượt tải vừa** để đối chiếu. Khi đo số
> có thể tạm tắt rate-rule CF rồi bật lại. **Đừng cài browser Playwright lên box prod** —
> chỉ máy dev/CI.

**Cài k6** (binary standalone, **không cần npm**):

```bash
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt update && sudo apt install k6
```

**Chạy các kịch bản** (đặt `BASE_URL` trỏ vào **nginx**, không phải API loopback, để
`CF-Connecting-IP` được tin ở hop loopback như production):

```bash
# tải hợp lệ + đo tài nguyên song song
uv run python scripts/loadtest/assert_stateful.py sample --seconds 150 --out cpu.csv &
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/throughput.js
# rate/budget/queue/stream/asr/soak
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/rate-limit.js
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/queue.js
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/soak.js         # ~45 phút
# assertion có-state (refund #4, counter #12, reachability #1)
uv run python scripts/loadtest/assert_stateful.py refund  --base http://127.0.0.1:8080
uv run python scripts/loadtest/assert_stateful.py counter --base http://127.0.0.1:8080
uv run python scripts/loadtest/assert_stateful.py spoof   --host <IP-LAN-cua-box>   # chạy TỪ máy LAN khác
```

**E2E trình duyệt thật (máy dev/CI, cross-browser)** — kiểm stream gapless (#14) qua
đường thật:

```bash
cd tests/e2e && npm install && npx playwright install
# smoke UI (mock, không cần server): npx playwright test ui-smoke.spec.ts
E2E_BASE_URL=https://voice.example.com npx playwright test stream-e2e.spec.ts
```

**Đọc số & chốt config:** thu p50/p95, tỉ lệ 429, CPU/RAM/swap đỉnh từ `sample`; nếu
lệch nháp thì sửa `app/config.py` + `.env.example` và ghi lý do vào report. Kiểm
**CF 524**: stream một đoạn rất dài (phát > 100s) qua CF — nếu **không** 524 thì giữ
nguyên; nếu **có**, giảm `ANON_MAX_CHARS_STREAM` và ghi Open Question (async-job giai
đoạn sau). Chi tiết checklist + bảng số: report ở `plans/reports/`.

## macOS (không có systemd)

Chạy nền tạm: `nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8123 >> logs/server.log 2>&1 &`.
Bền vững hơn thì dùng `launchd` (tạo `~/Library/LaunchAgents/*.plist`).

## GPU (tùy chọn, Linux + NVIDIA)

Mặc định torch CPU. Muốn CUDA: cài torch bản CUDA từ index PyTorch, rồi đặt
`DEVICE=cuda` trong `.env` và `restart` service. macOS để `DEVICE=cpu` (ONNX).

## Mang theo giọng clone

Copy thư mục `data/voices/` (mẫu + `registry.json`) sang máy mới → app tự enrol
lại lúc khởi động. Không copy thì máy mới bắt đầu với 0 giọng clone (preset vẫn đủ).

## Rollback

Service không có state ngoài `data/voices/`. Quay lui = `git checkout <tag/commit
cũ>` rồi `bash deploy/setup.sh && sudo systemctl restart all-voice`. Dữ liệu giọng
clone trong `data/` không bị ảnh hưởng.

## Cập nhật phiên bản

```bash
git pull
bash deploy/setup.sh                 # đồng bộ deps theo lock mới
sudo systemctl restart all-voice
```

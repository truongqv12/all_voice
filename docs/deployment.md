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
`DEFAULT_BACKEND` · `MAX_CONCURRENCY` · `VOICES_DIR` · `HOST` · `PORT` (mặc định 8123) ·
`LOG_LEVEL` · `LOG_DIR` · `HF_HOME`.

## Vận hành service (Linux)

```bash
systemctl status all-voice            # trạng thái
journalctl -u all-voice -f            # log realtime (hoặc: tail -f logs/server.log)
sudo systemctl restart all-voice      # khởi động lại
sudo systemctl disable --now all-voice # dừng + tắt autostart
```

- Service tự khởi động lại khi crash (`Restart=always`) và khi reboot máy.
- `--workers 2` mặc định (đổi bằng `WORKERS=4 sudo bash deploy/install-service.sh`) để
  chạy song song thật, vì mỗi engine bị lock tuần tự trong 1 tiến trình.
- **Giọng clone khi chạy nhiều worker:** danh sách/xóa giọng dùng chung
  `registry.json` (store đọc lại đĩa mỗi lần) nên xóa được ở bất kỳ worker nào. Nhưng
  giọng clone đã enrol để **synth** nằm trong RAM của **đúng worker tạo nó** cho tới
  khi restart — worker khác chưa có sẽ rơi về preset đầu tiên. Muốn mọi worker synth
  được giọng vừa tạo ngay: `sudo systemctl restart all-voice` (khởi động lại enrol
  toàn bộ từ `registry.json`). Hoặc chạy `--workers 1` nếu cần nhất quán tức thời.
- `logs/server.log` gom stdout+stderr (bắt cả log uvicorn và segfault native);
  `logs/app.log` là log ứng dụng xoay vòng (startup/request/synth/lỗi 500).

## macOS (không có systemd)

Chạy nền tạm: `nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8123 >> logs/server.log 2>&1 &`.
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

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

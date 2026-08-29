# Báo cáo hoàn thành — Multi-engine TTS (Kokoro + VOICEVOX) + Swagger tiếng Việt

- **Ngày:** 2026-08-30
- **Nhánh:** `feat/multi-engine-tts-kokoro-voicevox`
- **Plan:** `plans/260829-2258-multi-engine-tts-kokoro-voicevox`
- **Trạng thái:** DONE — code + docs + Swagger VI + test đã xong. Chưa push.

## 1. Mục tiêu & phạm vi (đạt)

Thêm 2 engine TTS drop-in vào gateway OpenAI-compatible, **không đụng core**
(router/registry/encoder/auth/schemas contract):

- **Kokoro-82M v1.0** — preset tiếng Anh, `kokoro-onnx` (torch-free), 24kHz.
- **VOICEVOX** — preset tiếng Nhật, `voicevox_core` in-process, 24kHz.

Cả hai: in-process, lazy-load, **không cloning**, đăng ký có guard (chỉ register
khi bật flag AND asset/thư viện sẵn sàng; thiếu → log 1 dòng, không raise).
VieNeu (tiếng Việt) vẫn là default.

## 2. Thay đổi chính

| Vùng | File | Nội dung |
|------|------|----------|
| Config | `app/config.py` | 9 setting mới: `enable_kokoro`, `kokoro_*`, `enable_voicevox`, `voicevox_*` |
| Đăng ký | `app/main.py` | Guarded registration + log skip khi asset vắng |
| Adapter | `app/backends/kokoro_backend.py` | 28 preset EN, lazy engine, espeak-ng guard |
| Adapter | `app/backends/voicevox_backend.py` | lazy synth, lazy per-VVM load, allowlist speaker |
| Deps | `pyproject.toml` | extras `en` (kokoro-onnx/onnxruntime/soundfile), `ja` (soundfile) |
| Scripts | `scripts/fetch-kokoro.sh`, `scripts/fetch-voicevox.sh` | tải asset, idempotent |
| Test | `tests/` | unit + synth (skip khi thiếu asset) + round-trip TTS→ASR |
| Docs | `README.md`, `docs/kien-truc-va-mo-rong.md`, `docs/deployment.md`, `.env.example` | hướng dẫn 2 engine (VI) |

## 3. Swagger / OpenAPI → tiếng Việt (toàn bộ bề mặt hiển thị)

- `main.py`: mô tả API, TAGS_METADATA, summary health "Kiểm tra sống".
- `auth.py`: mô tả ô Bearer key.
- Routers (`speech`, `models`, `voices`, `transcriptions`, `voices_admin`):
  summary + mô tả response (200/400/401/404/503) + mô tả Form/Query field + docstring.
- `schemas.py`: mọi `Field(description=...)` + docstring class.

**Cố ý giữ tiếng Anh (không phải label Swagger):** nội dung *message lỗi runtime*
trong response body (vd `"file is empty."`) — vì mỗi lỗi đã có `code` máy-đọc ổn
định để client bắt lỗi. Field name, enum literal (`ResponseFormat`,
`TranscriptionResponseFormat`), và error `code` **không đổi** → không phá contract.

Smoke: `app.openapi()` build sạch, 8 paths, các chuỗi VI có mặt.

## 4. Kiểm thử

```
71 passed, 8 skipped, 0 failed  (~67s)
```

- Trước và sau khi Việt-hóa Swagger: **giống hệt** → không hồi quy.
- 8 skip = test synth engine thật, skip đúng thiết kế vì asset Kokoro/VOICEVOX vắng.
- Guarded registration xác nhận qua log startup: cả 2 engine "not registered"
  (thiếu asset) trong khi `backends=['vieneu']` vẫn chạy.

## 5. Review đã xử lý (từ vòng code-review trước)

- **High** — VOICEVOX: `_get_synth()` chạy ngoài `self._lock` trong khi `_loaded`
  mutate trong lock → race lúc cold-start (MAX_CONCURRENCY=2) có thể dựng 2
  Synthesizer, desync `_loaded`, gây 500 dai dẳng. **Đã fix:** đưa
  `synth = self._get_synth()` vào trong `with self._lock`.
- **Medium** — chỉ log skip khi có exception, không log khi `is_available()==False`.
  **Đã fix:** thêm nhánh `else: log.info(...)` trong `main.py`.
- **Nit** — bỏ `_SAMPLE_RATE` chết trong kokoro_backend.

## 6. Commit

Feature (6 commit) đã có trên nhánh: adapter, extras, scripts, tests, docs, plan/journal.
Localization Swagger: commit riêng `docs(swagger): localize OpenAPI/Swagger UI to Vietnamese`
(8 file router/schemas/auth/main). **Chưa push.**

## 7. Câu hỏi mở

- Có dịch nốt *message lỗi runtime* (400/401/404/503) sang tiếng Việt không?
  (An toàn vì client nên dựa `code`, nhưng đổi response body → cần bạn duyệt.)
- Có push nhánh + mở PR không?

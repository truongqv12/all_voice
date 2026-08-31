# Hướng dẫn sử dụng API (API Reference)

Tài liệu này cung cấp chi tiết cách gọi API và các tính năng mở rộng của `all-voice`.

Tài liệu API tương tác (tự sinh): **`http://localhost:8123/docs`** (Swagger) · `/redoc` · `/openapi.json`.

## 🔌 Các API Endpoints chính
Mọi route `/v1/*` cần header `Authorization: Bearer <key>`.

| Method | Path | Mô tả |
|--------|------|-------|
| `POST` | `/v1/audio/speech` | Tổng hợp giọng nói (schema OpenAI) |
| `POST` | `/v1/audio/transcriptions` | Nhận dạng giọng → transcript + phụ đề (cần extra `asr`) |
| `GET`  | `/v1/models` | Liệt kê các backend đã đăng ký |
| `GET`  | `/v1/voices` | Liệt kê giọng preset + giọng clone (mọi backend) |
| `GET`  | `/v1/voices/{model}/{voice_id}/preview` | Nghe thử giọng (mp3) — công khai |
| `POST` | `/v1/audio/voices` | Tạo giọng clone (multipart) |
| `GET` · `DELETE` | `/v1/audio/voices/{id}` | Lấy / xóa một giọng clone |
| `GET`  | `/health` | Kiểm tra sống (không cần auth) |

## Dùng với SDK OpenAI
Giao thức tương thích 100% với SDK chuẩn của OpenAI.

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8123/v1", api_key="dev-key")

# Text-to-Speech
client.audio.speech.create(
    model="vieneu", voice="Trúc Ly",
    input="Xin chào, đây là all-voice.", response_format="mp3",
).stream_to_file("out.mp3")

# Speech-to-Text
srt = client.audio.transcriptions.create(
    model="whisper-1", file=open("bai_giang.mp3", "rb"), response_format="srt",
)
```

## 🎙️ Clone giọng (Nhân bản giọng nói)
Enrol (`add_voice`) tốn vài chục giây nên là bước **một lần duy nhất**. Hệ thống sẽ cấp một `voice_id` để tái sử dụng.

```python
# 1) Enrol một lần
voice = client.audio.voices.create(name="My Voice", audio_sample=open("ref.wav", "rb"))

# 2) Dùng lại với speech.create
client.audio.speech.create(model="vieneu", voice=voice.id, input="Xin chào!").stream_to_file("out.mp3")
```

**Yêu cầu mẫu**: 3–8s, **một người nói**, nền sạch, nói rõ và có ngữ điệu. Nếu mẫu thu âm ở studio quá sạch, nên tắt khử nhiễu (`denoise=false`) để giữ nguyên chất giọng.

## 🎛️ Knob tinh chỉnh giọng (Style)
Dùng `extra_body` để tinh chỉnh kiểu đọc (chỉ áp dụng cho các engine hỗ trợ như VieNeu).
```python
client.audio.speech.create(
    model="vieneu", voice="Trúc Ly", input="Ngày xửa ngày xưa...",
    extra_body={"style": "doc_truyen"}, # tu_nhien, tin_tuc, doc_truyen
)
```

## ⚙️ Cấu hình môi trường (.env)
- `API_KEYS`: Danh sách key (cách nhau dấu phẩy).
- `DEVICE`: `cpu`, `cuda`, hoặc `auto`.
- `MAX_CONCURRENCY`: Số worker chạy đồng thời.
- `ASR_MODEL`: Model STT (vd: `tiny`, `small`, `large-v3`).
- Các cấu hình engine: `ENABLE_KOKORO`, `ENABLE_VOICEVOX`.

## 🩺 Log & Debug
Log hệ thống xoay vòng ở `logs/app.log`. 
- Traceback lỗi 500 sẽ được ghi log chi tiết vào file.
- Thời gian trễ (latency) của từng API được ghi lại (vd: `-> 200 (150ms)`).

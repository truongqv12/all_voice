---
title: "Phase 2: Kokoro English Backend"
status: done
phase: 2
priority: P1
effort: "0.5d"
dependencies: [1]
---

# Phase 2: Kokoro English Backend

## Overview

Viết adapter `KokoroBackend` (`name="kokoro"`) chạy Kokoro-82M v1.0 trên `kokoro-onnx` (torch-free, onnxruntime) — 28 giọng English preset, synth 24kHz, không clone. Bám đúng pattern VieNeu: lazy-load engine + `threading.Lock`, `is_available()`, trả `AudioResult`.

## Requirements

- **Functional**
  - `list_voices()` trả 28 giọng English (20 US + 8 GB) với `language="en"`, tên hiển thị người-đọc-được (vd "Heart (US, nữ)"), `id` = voice id gốc của Kokoro (vd `af_heart`).
  - `synthesize(text, voice, speed, options)` → PCM float32 mono 24kHz; `speed` map thẳng vào Kokoro; voice không hợp lệ xử lý qua `resolve_voice` (strict/lenient của base).
  - `supports_cloning=False`; `register_voice`/`remove_voice` để mặc định (NotImplemented).
  - `is_available(settings)` = `kokoro_onnx` import được **và** 2 file model/voices tồn tại.
- **Non-functional**
  - Lazy-load: chỉ nạp ONNX session ở lần synth đầu; cache + lock (engine không đảm bảo thread-safe, và router đã cap concurrency).
  - Không nuốt lỗi thiếu `espeak-ng`: nếu G2P lỗi do thiếu system lib → raise rõ ràng (không trả audio rỗng).

## Architecture

- **Runtime:** `from kokoro_onnx import Kokoro; kokoro = Kokoro(model_path, voices_path)`.
- **Synthesis:** `samples, sample_rate = kokoro.create(text, voice=voice_id, speed=speed, lang="en-us")`. `samples` là float32 [-1,1], `sample_rate=24000`. Trả `AudioResult(pcm=np.asarray(samples, float32).reshape(-1), sample_rate=24000)`.
- **G2P:** Kokoro cần phoneme; `kokoro-onnx` dùng `espeak-ng` (system) cho English. Accent US/GB suy ra từ prefix voice (`a*`=US → `lang="en-us"`, `b*`=GB → `lang="en-gb"`).
- **Voice map:** hardcode bảng 28 voice (id → tên hiển thị + accent + giới tính) trong module (nguồn: VOICES.md). Không auto-scan để tránh lộ giọng ngôn ngữ khác trong `voices-v1.0.bin` (bin chứa 54 giọng đa ngôn ngữ — chỉ expose English).
- **Options:** ban đầu chỉ hỗ trợ `speed` (đã là tham số riêng). Không có style. Nếu client gửi option lạ → bỏ qua (giữ contract engine-agnostic). Có thể thêm knob `lang` (ép us/gb) sau, không bắt buộc.

## Related Code Files

- Create: `app/backends/kokoro_backend.py` — `KokoroBackend(VoiceBackend)`.
- Modify: `app/main.py` — đã có guard đăng ký (Phase 1); xác nhận `default=False`.
- Reference: `app/backends/vieneu_backend.py` (pattern), `app/backends/base.py` (contract).

## Implementation Steps

1. Khung class + lazy-load:
   ```python
   class KokoroBackend(VoiceBackend):
       name = "kokoro"
       def __init__(self, settings):
           self._model_path = settings.kokoro_model_path
           self._voices_path = settings.kokoro_voices_path
           self._default_voice = settings.kokoro_default_voice
           self._engine = None
           self._lock = threading.Lock()
           self.supports_cloning = False

       @staticmethod
       def is_available(settings) -> bool:
           import importlib.util, os
           if importlib.util.find_spec("kokoro_onnx") is None:
               return False
           return os.path.isfile(settings.kokoro_model_path) and os.path.isfile(settings.kokoro_voices_path)

       def _get_engine(self):
           if self._engine is None:
               from kokoro_onnx import Kokoro
               self._engine = Kokoro(self._model_path, self._voices_path)
           return self._engine
   ```
2. Bảng 28 giọng English (id, tên, accent, gender) — hằng số module `_EN_VOICES`. `list_voices()` dựng `Voice(id, name, model="kokoro", language="en")` từ bảng. `resolve_voice` kế thừa base; override default để trả `self._default_voice` khi lenient (đảm bảo `af_heart` tồn tại trong bảng).
3. `synthesize`:
   ```python
   def synthesize(self, text, voice, speed=1.0, options=None):
       lang = "en-gb" if voice.startswith(("b",)) else "en-us"
       engine = self._get_engine()
       with self._lock:
           samples, sr = engine.create(text, voice=voice, speed=float(speed), lang=lang)
       pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
       return AudioResult(pcm=pcm, sample_rate=int(sr))
   ```
   - Xác thực `sr == 24000` (assert/log nếu khác — bản v1.0 luôn 24k).
4. Xử lý lỗi G2P: bắt lỗi thiếu `espeak-ng` (ImportError/RuntimeError từ phonemizer) → raise `RuntimeError` message hướng dẫn `apt-get install espeak-ng` (không trả PCM rỗng).
5. Kiểm tra thủ công nhanh: `scripts/fetch-kokoro.sh` rồi `POST /v1/audio/speech {"model":"kokoro","voice":"af_heart","input":"Hello world"}` → nghe file.

## Success Criteria

- [ ] `GET /v1/models` có `kokoro`; `GET /v1/voices?language=en` trả đúng 28 giọng.
- [ ] `POST /v1/audio/speech model=kokoro` với vài voice khác nhau → audio non-silent, 24kHz, encode được wav/mp3.
- [ ] `model=kokoro` + voice sai (strict) → 404; model OpenAI-generic (lenient) không đụng Kokoro (vẫn default VieNeu).
- [ ] Không có torch trong môi trường vẫn synth được (torch-free).
- [ ] Bin 54 giọng nhưng API chỉ lộ 28 giọng English (không rò giọng ngôn ngữ khác).

## Testing / Validation

- Unit (không cần model, `not synth`): `is_available` False khi thiếu file; `list_voices` đúng số lượng + `language="en"` khi mock engine.
- `synth` (cần asset): xem Phase 4 (RMS non-silent, sample_rate, duration).

## Risk Assessment

- **Rủi ro:** thiếu `espeak-ng` → synth lỗi khó hiểu. **Tín hiệu:** exception phonemizer ở lần synth đầu. **Phản ứng:** message lỗi hướng dẫn cài; ghi vào docs Phase 5; test skip nếu `espeak-ng` vắng.
- **Rủi ro:** API `kokoro-onnx` đổi chữ ký `create()` giữa version. **Tín hiệu:** TypeError khi gọi. **Phản ứng:** pin `kokoro-onnx>=0.4` và kiểm tra chữ ký lúc cài; điều chỉnh adapter (điểm cô lập, không lan ra lõi).
- **Rủi ro:** accent map theo prefix sai với vài voice. **Phản ứng:** lấy accent từ bảng `_EN_VOICES` (nguồn chuẩn) thay vì đoán prefix nếu phát hiện lệch.

## Rollback

- Xóa `kokoro_backend.py` + block đăng ký kokoro. Lõi và các engine khác không phụ thuộc → an toàn.

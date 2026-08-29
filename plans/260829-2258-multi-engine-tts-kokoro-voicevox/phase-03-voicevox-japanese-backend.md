---
title: "Phase 3: VOICEVOX Japanese Backend"
status: done
phase: 3
priority: P1
effort: "1d"
dependencies: [1]
---

# Phase 3: VOICEVOX Japanese Backend

## Overview

Viết `VoicevoxBackend` (`name="voicevox"`) chạy **`voicevox_core` in-process** (Rust core + onnxruntime) — nhiều giọng nhân vật Nhật, synth 24kHz, không clone. Trọng tâm: **lazy-load từng VVM theo nhu cầu** để không phình RAM trên deploy 1-worker, và **credit bắt buộc** theo điều khoản VOICEVOX. Phương án Docker ENGINE (HTTP) được ghi làm fallback.

## Requirements

- **Functional**
  - Setup asset: cài wheel `voicevox_core`, tải `open_jtalk_dic_utf_8-1.11` + các file VVM voice model.
  - `list_voices()` liệt kê speaker×style từ metadata VVM (không cần nạp toàn bộ model để list — dùng metadata), `language="ja"`, tên gồm nhân vật + style + credit.
  - `synthesize(text, voice, speed, options)` → PCM float32 mono 24kHz qua `Synthesizer.tts(text, style_id)`; decode WAV bytes → float32.
  - `voice` id = `style_id` (int) hoặc chuỗi ổn định `"{speaker_uuid}:{style_id}"`; `resolve_voice` map tên→id.
  - `supports_cloning=False`.
  - `is_available(settings)` = `voicevox_core` import được **và** dict dir tồn tại **và** có ≥1 VVM.
- **Non-functional**
  - **Lazy VVM:** chỉ `VoiceModelFile.open()` + `synthesizer.load_voice_model()` cho VVM chứa style được yêu cầu, ở lần đầu dùng; cache theo VVM. `Synthesizer`/`OpenJtalk`/`Onnxruntime` khởi tạo 1 lần (lazy) + `threading.Lock`.
  - RAM: không nạp sẵn toàn bộ VVM lúc startup; `list_voices()` đọc metadata rẻ.
  - Credit: mỗi `Voice.name` (hoặc field phụ) kèm `"VOICEVOX:<nhân vật>"` để lộ ra `/v1/voices` và docs.

## Architecture

```
OpenJtalk(dict_dir) ─┐
Onnxruntime.get(...) ─┼─> Synthesizer(ort, ojt)  ── load_voice_model(VoiceModelFile) ──> tts(text, style_id) -> WAV bytes
VVM metadata (rẻ) ────┘                              (lazy, cache theo vvm_id)
```

- **Init (lazy, 1 lần):**
  ```python
  from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
  ort = Onnxruntime.load_once()            # hoặc đường dẫn ort riêng nếu cần
  ojt = OpenJtalk(settings.voicevox_dict_dir)
  synth = Synthesizer(ort, ojt)
  ```
- **Discovery (rẻ, không nạp model):** duyệt `*.vvm` trong `voicevox_vvm_dir`, mở metadata mỗi file để lấy `speakers[].styles[].id/name` + `speaker_uuid` + tên nhân vật. Xây map `style_id -> (vvm_path, display, credit)`. Áp `voicevox_speaker_allowlist` nếu có.
- **Synthesis (lazy nạp VVM):**
  ```python
  style_id = int(voice)  # hoặc parse "{uuid}:{style_id}"
  vvm_path = self._style_to_vvm[style_id]
  with self._lock:
      if vvm_path not in self._loaded:
          with VoiceModelFile.open(vvm_path) as vm:
              self._synth.load_voice_model(vm)
          self._loaded.add(vvm_path)
      wav = self._synth.tts(text, style_id)   # WAV bytes (có header)
  pcm, sr = _decode_wav_f32(wav)              # soundfile.read(BytesIO(wav), dtype="float32")
  return AudioResult(pcm=pcm.reshape(-1), sample_rate=sr)  # sr = 24000
  ```
  - `speed`: dùng đường `audio_query(text, style_id)` → chỉnh `query.speed_scale = speed` → `synthesis(query, style_id)` (tts() không nhận speed trực tiếp). Nếu `speed==1.0` dùng `tts()` cho gọn.
- **Fallback (documented, không code ở phase này):** biến thể HTTP gọi Docker ENGINE `:50021` (`POST /audio_query` → `POST /synthesis`), chọn qua `settings.voicevox_mode="core"|"http"`. Ghi trong docs Phase 5; chỉ hiện thực khi `voicevox_core` không cài được.

## Related Code Files

- Create: `app/backends/voicevox_backend.py` — `VoicevoxBackend(VoiceBackend)` + helper `_decode_wav_f32`.
- Create: `scripts/fetch-voicevox.sh` — cài wheel + tải dict + VVM (xem Steps).
- Modify: `app/main.py` — guard đăng ký voicevox (Phase 1).
- Modify: `app/config.py` — settings đã thêm ở Phase 1 (dict_dir, vvm_dir, allowlist, mode).

## Implementation Steps

1. **`scripts/fetch-voicevox.sh`** (idempotent):
   - Cài wheel CPU (abi3 dùng chung cp311/cp312), pin theo release:
     `pip install "https://github.com/VOICEVOX/voicevox_core/releases/download/<VER>/voicevox_core-<VER>+cpu-cp310-abi3-manylinux_2_34_x86_64.whl"` (chọn tag Linux x86_64 đúng ở trang releases).
   - Dùng `download` binary của voicevox_core để tải: OpenJTalk dict → `models/voicevox/open_jtalk_dic_utf_8-1.11`, VVM → `models/voicevox/vvms`, onnxruntime (nếu cần). Ví dụ: `./download --output models/voicevox --only models,dict` (kiểm tra flag thực tế qua `download --help`).
   - Verify: có dict dir + ≥1 `*.vvm`.
   - **Pin cùng release cho wheel + VVM** để tránh version mismatch.
2. **Helper decode:** `_decode_wav_f32(wav_bytes) -> (np.float32, int)` bằng `soundfile.read(io.BytesIO(wav_bytes), dtype="float32")` (mono; nếu stereo → mean/lấy kênh 0).
3. **Class + lazy init** (`voicevox_core.blocking`), `_lock`, cache `_loaded: set[str]`, map `_style_to_vvm`, `_voices_cache`.
4. **`is_available(settings)` static:** `find_spec("voicevox_core")` + `os.path.isdir(dict_dir)` + tồn tại ≥1 `*.vvm` trong `vvm_dir`.
5. **`list_voices()`:** build từ metadata VVM (lazy 1 lần, cache). `Voice(id=str(style_id), name=f"{char} · {style} (VOICEVOX)", model="voicevox", language="ja")`. Áp allowlist.
6. **`synthesize()`** theo Architecture (lazy load VVM + tts/audio_query cho speed).
7. **Credit:** đảm bảo tên nhân vật + "VOICEVOX" xuất hiện ở `/v1/voices`; thêm dòng credit vào docs (Phase 5). Ghi chú điều khoản: hiển thị credit khi phát hành audio.
8. **Kiểm tra thủ công:** `scripts/fetch-voicevox.sh` → `POST /v1/audio/speech {"model":"voicevox","voice":"3","input":"こんにちは、世界"}` → nghe file (speaker 3 = Zundamon ノーマル nếu có trong VVM tải về).

## Success Criteria

- [ ] `GET /v1/models` có `voicevox`; `GET /v1/voices?language=ja` liệt kê speaker×style kèm credit.
- [ ] `POST /v1/audio/speech model=voicevox` với ≥2 style khác nhau → audio non-silent, 24kHz, encode wav/mp3.
- [ ] **Lazy verify:** startup KHÔNG nạp VVM (RAM thấp); VVM chỉ nạp ở request đầu cho style đó (đo bằng log/ănstrument hoặc test kiểm tra `_loaded` rỗng trước synth, có phần tử sau synth).
- [ ] Thiếu asset (dict/VVM) → backend skip gọn, app vẫn chạy (đã guard Phase 1).
- [ ] Credit hiển thị ở `/v1/voices`.

## Testing / Validation

- Unit (`not synth`): `is_available` False khi thiếu dict/VVM; `_decode_wav_f32` round-trip đúng dtype/sr với WAV giả (soundfile write→read); `list_voices` map metadata (mock).
- `synth` (cần asset): Phase 4 — sinh audio thật cho ≥2 speaker, assert non-silent/sr/duration + kiểm tra lazy-load (`_loaded`), text tiếng Nhật.

## Risk Assessment

- **Rủi ro (cao):** wheel `voicevox_core` không có cho Python/OS hiện tại hoặc onnxruntime version lệch. **Tín hiệu:** pip install wheel fail / import lỗi symbol. **Phản ứng:** thử abi3 wheel (cp310-abi3 chạy 3.11/3.12); nếu vẫn fail → **chuyển sang fallback Docker ENGINE HTTP** (`voicevox_mode="http"`) — đã thiết kế sẵn, đổi adapter path, không đụng lõi.
- **Rủi ro:** VVM/dict version mismatch. **Phản ứng:** pin cùng release; script verify version.
- **Rủi ro:** RAM phình nếu người dùng gọi nhiều style (nạp nhiều VVM). **Tín hiệu:** RSS tăng theo số style. **Phản ứng:** giữ lazy per-VVM; tùy chọn giới hạn qua `allowlist`; (tương lai) LRU unload VVM.
- **Rủi ro:** `tts()` không nhận `speed`. **Phản ứng:** dùng `audio_query` + `speed_scale` như Architecture.
- **Rủi ro:** quên credit → vi phạm điều khoản. **Phản ứng:** credit là success-criteria + test kiểm tra chuỗi "VOICEVOX" trong `/v1/voices`.

## Rollback

- Xóa `voicevox_backend.py` + block đăng ký + `scripts/fetch-voicevox.sh`. Không đụng lõi → VieNeu/Kokoro không ảnh hưởng. Asset dưới `models/` xóa tay nếu cần giải phóng đĩa.

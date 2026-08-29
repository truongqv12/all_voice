---
title: "Phase 4: Voice-Generation Tests"
status: done
phase: 4
priority: P1
effort: "0.5d"
dependencies: [2, 3]
---

# Phase 4: Voice-Generation Tests

## Overview

Bộ test **sinh voice thật** (không mock synthesis) cho Kokoro + VOICEVOX, dưới marker `synth` sẵn có. Test assert audio là **âm thanh thật** (không im lặng), đúng sample_rate/kênh, độ dài hợp lý, chạy được nhiều giọng, encode round-trip; **lưu WAV ra đĩa để nghe tay**. VOICEVOX được test kỹ hơn (nhiều speaker + lazy-load + text tiếng Nhật + credit).

**Bổ sung (chốt ở Validation Log #5): test round-trip TTS→ASR ("sub").** Tận dụng phương án e2e của plan ASR cũ (`ASR_MODEL=tiny` set trước import app + `TestClient`): audio do chính TTS sinh ra được nạp ngược vào `POST /v1/audio/transcriptions` và assert transcription **khớp nội dung input** — vừa chứng minh giọng **nghe-hiểu-được** (mạnh hơn ngưỡng RMS), vừa tiện kiểm luôn tính năng phụ đề (sub) end-to-end.

## Requirements

- **Functional**
  - `tests/test_kokoro.py` + `tests/test_voicevox.py` (marker `synth`).
  - Skip gọn khi asset/engine vắng (`is_available` False) → CI tối thiểu không đỏ.
  - Assertion chất lượng: RMS > ngưỡng im lặng; `sample_rate == 24000`; mono; duration ∈ [khoảng hợp lý theo độ dài text]; nội dung khác nhau giữa 2 voice (không phải cùng buffer).
  - Sinh nhiều voice: Kokoro ≥3 giọng (US nam/nữ, GB); VOICEVOX ≥2 style.
  - Encode round-trip: PCM → `encode(..., "wav")` và `"mp3")` giải mã lại được (dùng soundfile/av), sr giữ nguyên ở wav.
  - Discovery e2e: `/v1/models` chứa kokoro+voicevox; `/v1/voices?language=en|ja` đúng; `model=<engine>` + voice sai → 404.
  - **VOICEVOX lazy-load test:** trước synth `_loaded` rỗng; sau synth 1 style → chứa đúng VVM đó.
  - **Round-trip TTS→ASR (sub):** `tests/test_tts_asr_roundtrip.py` (marker `synth`). Sinh audio từ text đã biết → encode WAV → `POST /v1/audio/transcriptions` (`ASR_MODEL=tiny`, `TestClient`) → transcription non-empty và khớp input. **EN (Kokoro): chặt** — normalize (lower, bỏ dấu câu) rồi assert ≥60% từ khóa input xuất hiện (vd input "the quick brown fox jumps over the lazy dog"). **JA (VOICEVOX): lỏng** — chỉ assert transcription non-empty + `duration>0` (whisper `tiny` yếu tiếng Nhật, tránh flaky). Skip nếu ASR extra chưa cài (`app.asr` unavailable) HOẶC engine TTS không available.
  - Lưu output: `tests/output/<engine>-<voice>.wav` (gitignore) để nghe tay; in đường dẫn.
- **Non-functional**
  - `pytest -m "not synth"` vẫn nhanh & xanh (test synth tách biệt).
  - Test độc lập thứ tự, tự dọn (trừ WAV output cố ý giữ để nghe).

## Architecture

- **Fixtures dùng chung** (`tests/conftest.py` hoặc trong từng file): helper `assert_real_audio(pcm, sr, min_rms=1e-3, expected_sr=24000)`; helper `save_wav(pcm, sr, name)` ghi `tests/output/`.
- **3 tầng test mỗi engine:**
  1. **Adapter trực tiếp** (`Backend.synthesize`) — nhanh, cô lập engine.
  2. **HTTP e2e** qua `TestClient` (`POST /v1/audio/speech`) — chứng minh path đầy-cuối (auth, router, encoder). Theo mẫu `tests/test_multi_backend_e2e.py`.
  3. **Round-trip TTS→ASR** (`POST /v1/audio/speech` → bytes → `POST /v1/audio/transcriptions`) — chứng minh giọng nghe-hiểu-được + kiểm luôn feature sub. Theo mẫu e2e của `tests/test_transcriptions.py` (đặt `os.environ["ASR_MODEL"]="tiny"` + `get_settings.cache_clear()` **trước** import app).
- **Nguồn 1 client dùng chung:** `ASR_MODEL=tiny` phải set trước khi app import & cache settings; đặt env + `cache_clear()` ở đầu file round-trip (giống `tests/test_transcriptions.py:15-22`) để tránh xung đột cache settings với test khác.
- **Skip guard:** `pytest.mark.skipif(not Backend.is_available(settings), reason="asset chưa tải")` + marker `synth`.
- **Ngưỡng RMS**: chọn thận trọng (vd 1e-3) để phân biệt audio thật vs buffer im lặng; kèm assert `len(pcm) > 0.2*sr` (âm > 0.2s cho câu ngắn).

## Related Code Files

- Create: `tests/test_kokoro.py`
- Create: `tests/test_voicevox.py`
- Create: `tests/test_tts_asr_roundtrip.py` — round-trip TTS→ASR (sub), tự set `ASR_MODEL=tiny`.
- Create/Modify: `tests/conftest.py` — helper `assert_real_audio`, `save_wav`, settings fixture.
- Modify: `tests/test_multi_backend_e2e.py` — mở rộng discovery cho 3 backend (giữ backend giả nếu cần cho path không-asset).
- Modify: `.gitignore` — thêm `tests/output/`.
- Reference: `app/audio/encoder.py`, `app/backends/*`, `app/routers/transcriptions.py`, `tests/test_transcriptions.py` (mẫu ASR e2e).

## Implementation Steps

1. `tests/conftest.py`: thêm `assert_real_audio(pcm, sr, ...)` (kiểm dtype float32, mono, `sr==expected`, `rms>min_rms`, `len>0`); `save_wav(pcm, sr, name)` → `tests/output/`.
2. `tests/test_kokoro.py` (`@pytest.mark.synth`, skipif không available):
   - `test_kokoro_synthesizes_multiple_voices`: cho ≥3 voice, synth "The quick brown fox...", `assert_real_audio`, `save_wav`, và assert 2 voice cho PCM khác nhau (`not np.array_equal`).
   - `test_kokoro_http_speech`: `TestClient` POST `model=kokoro,voice=af_heart,response_format=mp3` → 200, content-type `audio/mpeg`, body > vài KB; POST voice sai → 404.
   - `test_kokoro_duration_scales_with_speed` (nhẹ): speed 1.3 cho audio ngắn hơn speed 1.0.
3. `tests/test_voicevox.py` (`@pytest.mark.synth`, skipif):
   - `test_voicevox_synthesizes_japanese`: ≥2 style, text "こんにちは、世界。今日はいい天気ですね。", `assert_real_audio` (sr 24000), `save_wav`, 2 style khác buffer.
   - `test_voicevox_lazy_loads_vvm`: khởi tạo backend, assert `_loaded` rỗng; sau 1 synth → `_loaded` có đúng VVM chứa style đó; style khác VVM → nạp thêm.
   - `test_voicevox_http_and_credit`: `/v1/voices?language=ja` chứa chuỗi "VOICEVOX" (credit) + ≥1 voice; POST `model=voicevox` → 200 audio.
4. Mở rộng `tests/test_multi_backend_e2e.py`: `/v1/models` ⊇ {vieneu, kokoro, voicevox} khi asset có; `/v1/voices?language=` lọc đúng; VieNeu vẫn default.
5. `tests/test_tts_asr_roundtrip.py` (`@pytest.mark.synth`, skipif thiếu asset TTS **hoặc** `app.asr` ASR):
   - Header: `os.environ["ASR_MODEL"]="tiny"` → `from app.config import get_settings; get_settings.cache_clear()` → import `app`, `TestClient` (đúng mẫu `tests/test_transcriptions.py`).
   - `test_kokoro_roundtrip_english`: `POST /v1/audio/speech {model:kokoro, voice:af_heart, input:"the quick brown fox jumps over the lazy dog", response_format:wav}` → body WAV → `POST /v1/audio/transcriptions {file, response_format:verbose_json}` → 200, `text` non-empty; normalize (lower, strip dấu câu) rồi assert ≥60% token input có trong transcription.
   - `test_voicevox_roundtrip_japanese` (lỏng): synth text Nhật ngắn → transcribe → assert `text` non-empty + `duration>0` (KHÔNG so khớp ký tự — whisper `tiny` yếu JA). Ghi transcription ra log để soi tay.
   - Dùng `response_format=wav` cho audio giữa để ASR decode chắc chắn (không phụ thuộc mp3 codec).
6. `.gitignore`: `tests/output/`. In đường dẫn WAV ở cuối mỗi test synth để nghe tay.
7. Chạy: `pytest -m synth -k "kokoro or voicevox or roundtrip" -s` (xem đường dẫn WAV + transcription); `pytest -m "not synth"` xác nhận không hồi quy.

## Success Criteria

- [ ] `pytest -m "not synth"` xanh (lõi không hồi quy).
- [ ] `pytest -m synth` (khi asset có): Kokoro + VOICEVOX sinh audio thật, mọi assert pass, WAV xuất hiện trong `tests/output/` nghe được.
- [ ] Khi asset vắng: test synth **skip** (không fail), CI tối thiểu xanh.
- [ ] Test lazy-load VOICEVOX chứng minh không nạp VVM lúc khởi tạo.
- [ ] Test credit VOICEVOX pass (chuỗi "VOICEVOX" ở `/v1/voices`).
- [ ] **Round-trip TTS→ASR pass:** Kokoro EN transcribe khớp ≥60% từ khóa input; VOICEVOX JA trả transcription non-empty. Skip gọn khi thiếu asset TTS hoặc extra `asr`.

## Testing / Validation

- Đây là phase test → validation = chính nó chạy xanh + nghe tay WAV output.
- Đo thời gian: đảm bảo mỗi test synth < ~30s trên CPU (câu ngắn) để vòng lặp chịu được.

## Risk Assessment

- **Rủi ro:** ngưỡng RMS quá nhạy → flaky. **Tín hiệu:** test đỏ ngẫu nhiên trên audio hợp lệ. **Phản ứng:** hạ ngưỡng/nới, dùng RMS trên đoạn giữa (bỏ silence đầu/cuối).
- **Rủi ro:** test synth chậm làm nản vòng lặp. **Phản ứng:** marker `synth` tách khỏi default; câu ngắn; chỉ vài voice tiêu biểu.
- **Rủi ro:** CI không có asset → đỏ. **Phản ứng:** skipif `is_available` — synth chỉ chạy khi có model; document cách tải để chạy full.
- **Rủi ro:** `duration_scales_with_speed` giòn. **Phản ứng:** so sánh với biên (>=10% chênh) thay vì con số cứng; nếu vẫn giòn → hạ xuống smoke test độ dài > 0.
- **Rủi ro:** round-trip EN flaky nếu ngưỡng khớp quá chặt (ASR sai vài từ). **Tín hiệu:** test đỏ dù audio nghe rõ. **Phản ứng:** ngưỡng 60% từ khóa (không đòi khớp tuyệt đối), normalize dấu câu/hoa-thường, câu input đơn giản rõ ràng.
- **Rủi ro:** whisper `tiny` phiên âm tiếng Nhật kém → không thể so khớp. **Phản ứng:** JA chỉ assert non-empty + `duration>0` (thiết kế lỏng có chủ đích); log transcription để soi tay, không gate theo nội dung.
- **Rủi ro:** `ASR_MODEL=tiny` set muộn (sau khi app cache settings) → round-trip dùng nhầm model nặng. **Phản ứng:** set env + `get_settings.cache_clear()` ở đầu file trước import app; giữ round-trip ở **file riêng** để cô lập thứ tự import.

## Rollback

- Xóa file test mới. Không ảnh hưởng runtime. `tests/output/` chỉ là artifact nghe tay.

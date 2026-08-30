---
title: "Research — SRT/VTT subtitle export for TTS + ASR (all_voice)"
type: research
status: reference
created: 2026-08-30
tags: [research, srt, vtt, subtitles, asr, tts, alignment]
related_plan: 260830-2020-tts-frontend-visual-shell
---

# Research — Subtitle (SRT/VTT) export

Trả lời yêu cầu "tương lai muốn xuất file .srt sub" (owner) — nghiên cứu cả hai hướng: **ASR→SRT** (upload audio → phụ đề) và **TTS→SRT** (tạo giọng từ text + xuất phụ đề khớp). Kết luận dựa trên **đọc source thực tế** của repo, không suy đoán.

## Kết luận nhanh

- **ASR → SRT/VTT: đã khả thi ngay** — backend có `POST /v1/audio/transcriptions` trả `srt`/`vtt` và `verbose_json` + `timestamp_granularities[]=word`. Nhưng `srt`/`vtt` hiện tại chỉ ở mức **segment của Whisper** (cue có thể quá dài, không đúng chuẩn phụ đề). → Cần **re-chunk phía client** từ `words[]` (word timestamps) thành cue chuẩn.
- **TTS → SRT (verbatim, khớp đúng text nhập): KHÔNG có lời giải nhẹ hôm nay** cho Kokoro/VieNeu. Chỉ **VOICEVOX** có timing sẵn (đang bị bỏ). → Là **dự án backend riêng ở tương lai**, không thuộc visual-shell.

## Bằng chứng từ source (đã kiểm tra)

- `app/backends/base.py`: `AudioResult` = `pcm + sample_rate` **only** — không backend TTS nào trả timing.
- `voicevox_backend.py`: `synthesize()` **dựng `audio_query`** (đường speed-scale) rồi **vứt đi**. `audio_query.accent_phrases` chứa `vowel_length`/`consonant_length` per-mora (giây) — **timing chính xác cho đúng text, đã tính, đang bị bỏ**.
- `kokoro_backend.py`, `vieneu_backend.py`: **không** có API timing (wrapper `kokoro-onnx` không expose; VieNeu không có).
- `app/asr/subtitles.py`: `to_srt`/`to_vtt` chỉ format từ **segment boundaries** của Whisper — không word-level, không giới hạn ký tự/dòng. `TranscriptionResult.words` (`Word.start/end`) có khi request `verbose_json`+word, **nhưng chưa được đưa vào `to_srt`/`to_vtt`** → gap thực tế cho UX "xuất phụ đề".
- `tests/test_tts_asr_roundtrip.py`: đã chứng minh TTS→ASR chạy in-process (tiền lệ cho phương án fallback bên dưới).

## Hướng 1 — ASR → SRT/VTT (khuyến nghị cho visual-shell)

- Request nội bộ **`verbose_json` + `timestamp_granularities[]=word`** rồi **re-chunk client-side** thành cue chuẩn (bắt buộc vì `to_srt` hiện tại không theo chuẩn nào).
- Tuỳ chọn màn export: **max chars/line** (mặc định 42, cho override theo ngôn ngữ), **max lines/cue** (2), **granularity** (word-accurate vs sentence), **ngôn ngữ**, **format** (SRT/VTT). **Không** có "translate" (endpoint transcribe-only) — để tương lai.
- Thuật toán chunk: greedy-fill words tới giới hạn ký tự, ưu tiên ngắt ở dấu câu/mệnh đề, tách cue mới khi vượt thời lượng hoặc tốc độ đọc (CPS). Chạy **client-side** trên `words[]` JSON → endpoint không đổi.

## Hướng 2 — TTS → SRT (feasibility, cho tương lai)

- **(a) Native engine timestamps** — không đồng nhất:
  - **VOICEVOX (JP): rẻ + chính xác, làm trước.** Mora `vowel_length`/`consonant_length` cho timing chính xác đúng text, **không cần bước alignment** — chỉ cần backend **giữ lại** `audio_query` đang dựng. Đơn vị caption theo **accent-phrase**, KHÔNG theo "word" (tiếng Nhật không tách bằng space).
  - **Kokoro (EN): wrapper cài đặt không expose.** `kokoro-onnx` không có API timestamp. Có bản community `Kokoro-82M-v1.0-ONNX-timestamped` expose phoneme-duration nhưng phải đổi ONNX asset + tự viết decode → fork/patch, không phải bật cờ. Effort: trung bình, chưa chắc tới khi spike.
  - **VieNeu (VI): không có** bằng chứng timing → coi như không.
- **(b) Forced alignment** (text đã biết ép lên audio) — chính xác nhất về khái niệm nhưng **đều nặng**:
  - **MFA 3.x**: chính xác nhất nhưng toolchain conda + model/dictionary theo ngôn ngữ — lạ với pattern in-process ONNX/Rust của repo.
  - **WhisperX**: cần torch + model wav2vec2 CTC theo ngôn ngữ; coverage VI/JP không đều, phải verify.
  - **stable-ts `align(audio, known_text)`**: hợp khái niệm nhất nhưng **chỉ chạy với openai-whisper (torch), không phải faster-whisper/CTranslate2** mà backend đang dùng → phải chạy song song stack Whisper thứ 2 (tốn RAM trên box CPU single-worker).
  - **aeneas**: nhẹ, dùng chung `espeak-ng` (đã có cho Kokoro G2P) nhưng chỉ hợp sync câu/đoạn, không word-level.
  - **Gentle**: chỉ EN, gần như bỏ hoang → loại.
- **(c) Fallback thực dụng — chạy audio TTS qua `/v1/audio/transcriptions`**: rất dễ (đã có tiền lệ test), 0 dependency mới, dùng lại đúng bộ chunk ở Hướng 1. Trade-off: text Whisper **nhận** có thể lệch text **nhập** (phát âm sai, đồng âm, danh từ riêng, giọng biểu cảm VOICEVOX) → phụ đề có thể không verbatim; **gấp đôi** latency/CPU mỗi request; lãng phí vì text đã biết.

**Xếp hạng khuyến nghị:**
1. **VOICEVOX: caption từ mora-timing native ngay** (rẻ nhất, chính xác, 0 dep mới).
2. **Kokoro/VieNeu near-term: fallback ASR round-trip (2c)** — **cần chốt UX**: caption "gần đúng" (ASR-recovered) có chấp nhận không, hay **bắt buộc verbatim**? Nếu bắt buộc verbatim → **không có aligner nhẹ (torch-free) hôm nay** → dự án lớn hơn.

## SRT vs VTT + chuẩn cue
- **SRT**: phân cách thập phân bằng phẩy, cue đánh số, không header — phổ biến nhất, mặc định cho "tải file phụ đề".
- **VTT**: dấu chấm, header `WEBVTT`, hỗ trợ style/position — native cho `<track>` trong `<video>` HTML5; ưu tiên khi nhúng web.
- Chuẩn nên encode vào exporter: **≤42 ký tự/dòng, ≤2 dòng/cue, tốc độ đọc ≤17-20 CPS** (Latin; CJK thấp hơn, Nhật ~4 CPS), cue **min ~0.83s, max ~7s**. (Nguồn: Netflix Timed Text Style Guide — coi là default công nghiệp.)

## Thư viện (build SRT/VTT client-side từ word-timestamp JSON)
- **`subsrt-ts`** — zero-dep, TS/ESM, parse+build nhiều format → **mặc định tốt nhất**.
- **`subtitle`** — TS, stream API, SRT mạnh, VTT một phần.
- **`@plussub/srt-vtt-parser`** — zero-dep, parse-only (ghép builder tự viết nếu muốn nhẹ nhất).

## Rủi ro hàng đầu
1. **Verbatim TTS caption cho Kokoro/VieNeu không có lời giải sạch hôm nay** — mọi aligner đều thêm torch/conda/fork ONNX. Đây là rủi ro scope lớn nhất.
2. **ASR round-trip (2c) có thể lệch text** — cần quyết định sản phẩm, không để mặc định ngầm.
3. **`to_srt`/`to_vtt` segment-level sẽ trông sai** trong UI export chuyên dụng nếu không có re-chunk client-side (Hướng 1) — là hạ tầng bắt buộc, không phải polish.
4. **Ngân sách RAM/CPU**: deploy tuned cho box CPU single-worker — mọi runtime nặng thứ 2 (torch/MFA/WhisperX) là rủi ro dung lượng thật.
5. **Đơn vị caption tiếng Nhật**: mora-timing VOICEVOX không map "word" theo space — dùng nhầm thuật toán word tiếng Anh sẽ vỡ caption Nhật (phải theo accent-phrase).

## Câu hỏi chưa chốt (cho tương lai)
- TTS caption **phải verbatim** theo text nhập, hay **ASR-recovered chấp nhận được**? (Quyết định 2b vs 2c cho Kokoro/VieNeu.)
- Có ưu tiên spike Kokoro timestamped-ONNX không, hay **VOICEVOX-native + ASR-fallback** là đủ cho v1?
- Đối tượng tiêu thụ phụ đề: chỉ `<track>` web, hay file tải về cho player ngoài? (Ảnh hưởng default SRT vs VTT.)

## Áp dụng vào plan hiện tại
- **Visual-shell (plan `260830-2020-...`)**: khu **Speech-to-Text (phase 5)** là bề mặt export **SRT/VTT/TXT** chính (backend-real). Chunk client-side (`subsrt-ts`) chạy **thật** trên fixture transcript có word-timestamp (không phải fake).
- **TTS→SRT**: chỉ là **affordance mock đánh dấu "thử nghiệm"** trên result-card TTS (nếu có), + ghi nhận đây là **follow-on** (VOICEVOX-native trước; Kokoro/VieNeu chờ chốt verbatim-vs-ASR). Không hiện thực backend trong plan này.

---
title: "Phase 2: Gia cố lõi synth + cache"
status: done
---

# Phase 2: Gia cố lõi synth + cache

Priority: P1 · Effort: ~1.5 ngày · Phụ thuộc: P1

## Overview

Làm lõi synth "sẵn sàng" trên máy 6 core: **cap số thread inference** (chừa CPU
cho event loop/tunnel), **cache kết quả ra đĩa** (dedup text+voice+format — chỉ
path **buffered ≤ cap anon**; long-read qua `/v1/audio/stream` KHÔNG cache, nên
"thắng lớn" chỉ áp cho đoạn ngắn lặp — #5-note), và **cap thời lượng ASR** + tính
đúng giây-audio vào budget.

## Requirements

- Functional:
  - Thread/CPU inference bị giới hạn: ASR qua `OMP_NUM_THREADS` +
    `WhisperModel(cpu_threads=...)` (=`asr_cpu_threads`, mặc định 4); **preset VieNeu
    ONNX** qua **cgroup/taskset** (onnxruntime bỏ qua env — #13). `torch.set_num_threads`
    chỉ ảnh hưởng path clone-enrol.
  - Cache kết quả `/v1/audio/speech` (buffered) trên đĩa: hit → trả ngay không synth.
  - ASR: probe thời lượng **trước khi** transcribe; ANON vượt `anon_max_audio_seconds`
    → 400/413; ghi `audio_ms` thực vào budget (đã nối P1).
- Non-functional: cache an toàn đa tiến trình (atomic write như previews), có trần
  dung lượng LRU; thay đổi thread không phá chất lượng synth.

## Architecture

- **Cap thread (đúng thứ tự nạp):** onnxruntime/CTranslate2 đọc `OMP_NUM_THREADS`
  **lúc import**, nên đặt **trước** khi backend nạp. Cách chắc nhất: systemd
  `Environment=OMP_NUM_THREADS=4` (Phase 4). Phòng thủ trong code: set
  `os.environ.setdefault(...)` ở đầu `app/__init__.py` (trước mọi import nặng) +
  truyền `cpu_threads` cho WhisperModel (faster-whisper mặc định `cpu_threads=0`→CT2
  dùng 4; đặt tường minh = 4).
- **[#13] Cảnh báo — hot-path anon (VieNeu preset) là ONNX torch-FREE:**
  `torch.set_num_threads` **không** ảnh hưởng preset synth (torch chỉ dùng lúc clone
  enrol); onnxruntime wheel thường **bỏ qua `OMP_NUM_THREADS`** (tự sizing intra-op);
  `Vieneu(backend="onnx")` không cho truyền `SessionOptions.intra_op_num_threads`.
  → Lever THẬT để chặn CPU của preset synth là **`taskset`/cgroup `CPUQuota`** ở
  systemd unit (Phase 4). Acceptance phải **ĐO** thread/CPU khi synth thật, không
  chỉ đọc lại config. ASR (faster-whisper) thì `cpu_threads` là param thật → dùng OK.
- **Result cache:** module mới `app/result_cache.py`. Dùng LẠI `_atomic_write`/
  sidecar/slug từ `app/previews.py`, **nhưng eviction là code MỚI** — `previews.py`
  KHÔNG có LRU size-based (chỉ `prune_orphans` theo voice, `previews.py:250`). Key =
  `sha1(model|voice|style|speed|format|input)`. `get(key)->bytes|None`, `put(key,bytes)`.
  **[#11] Eviction:** sweep dưới **lock** (hoặc single-writer) theo **size + số
  file**, `unlink(missing_ok=True)` (chịu unlink song song), theo **access-order**
  (đụng = chạm mtime/atime, không evict bản hot), chạy trên **timer nền** — KHÔNG
  trên hot-path `put`. Chỉ cache **buffered** (stream không cache). VieNeu ngẫu nhiên
  nội bộ nên bản cache ≠ regenerate — chấp nhận (cache = tái dùng bản đã tạo).
- **ASR duration cap + charge TRƯỚC:** helper `probe_duration(bytes)->float` mở
  container bằng `av` đọc `duration` (rẻ, không decode toàn bộ) — **`container.duration`
  là micro-giây (`AV_TIME_BASE`), phải `/ 1e6` ra giây** (#6). Chặn ANON quá dài
  trước khi tốn CPU. **[#7] `reserve_audio(ip, probed_ms)` TRƯỚC `admit`/transcribe**
  (cap-ngày chặn kịp, không "reserve 0 rồi ghi sau"); sau transcribe reconcile với
  `result.duration` thật (`transcribe()` trả `TranscriptionResult.duration`, không
  phải raw `info` — `transcriber.py:168`).

## Related Code Files

- Create: `app/result_cache.py` — cache đĩa cho audio đã encode (dùng lại atomic-write/sidecar của `app/previews.py`; eviction là **code mới** — previews KHÔNG có LRU, #11).
- Modify: `app/routers/speech.py` — tra cache trước synth; miss → synth+encode+`put`; log cache hit/miss.
- Create/Modify: `app/__init__.py` — set `OMP_NUM_THREADS`/thread env sớm (nếu chưa có ở systemd). (`torch.set_num_threads` chỉ ảnh hưởng path **clone-enrol**, KHÔNG ảnh hưởng preset synth ONNX — #13; cap CPU preset bằng cgroup/taskset ở Phase 4.)
- Modify: `app/asr/transcriber.py` — `WhisperModel(..., cpu_threads=settings.asr_cpu_threads)`; thêm `probe_duration(bytes)`.
- Modify: `app/routers/transcriptions.py` — cap thời lượng ANON trước transcribe; ghi `audio_ms` vào budget.
- Modify: `app/config.py` — `inference_threads`, `asr_cpu_threads`, `result_cache_enabled`, `result_cache_dir`, `result_cache_max_mb`, `anon_max_audio_seconds`.
- Modify: `.gitignore` — thêm `data/cache/` (như `data/previews/`).
- Create: `tests/test_result_cache.py` — put/get, LRU prune, key ổn định (marker `not synth`).

## Implementation Steps

1. `config.py`: thêm biến thread + cache + `anon_max_audio_seconds`.
2. Thread/CPU cap: xác nhận cách onnxruntime nhận thread (#13 — có thể **bỏ qua**
   `OMP_NUM_THREADS`); đặt `OMP_NUM_THREADS` sớm **+ cgroup `CPUQuota`/`taskset`**
   (Phase 4) là lever thật cho preset. **ĐO thực nghiệm**: số thread/CPU khi synth
   thật (không chỉ đọc config), p50/p95 latency 1 request để chắc cap không làm chậm.
3. `transcriber.py`: truyền `cpu_threads`; thêm `probe_duration` (av.open →
   `container.duration / 1e6` ra **giây** — #6). (Không dùng `torch.set_num_threads`
   cho preset — vô tác dụng, #13.)
4. `result_cache.py`: dùng lại atomic-write/sidecar của previews; `get/put`; eviction
   là **code mới** — sweep nền dưới lock theo size+count, `missing_ok`, access-order
   (#11). KHÔNG khung "mirror LRU previews" (previews không có LRU size-based).
5. `speech.py`: sau khi resolve voice/options, tính key; `get` → hit trả ngay (vẫn ghi budget ký tự — hoặc miễn budget cho cache-hit? *Quyết định:* vẫn tính budget theo ký tự để công bằng chi phí "đọc", nhưng có thể giảm nửa cho hit — mặc định tính đủ, KISS); miss → synth+encode+`put`.
6. `transcriptions.py`: gate header **trước khi đọc body 25MB** (#7); ANON +
   `probe_duration > anon_max_audio_seconds` → 400/413 trước `admit`;
   `reserve_audio(probed_ms)` **trước** transcribe; sau transcribe reconcile
   `result.duration` thật (#7).
7. Test `test_result_cache.py`: round-trip, prune khi vượt trần, key khác nhau cho input khác nhau.

## Todo

- [x] `config.py`: thread + cache + `anon_max_audio_seconds`
- [x] Cap thread: `OMP_NUM_THREADS` sớm + `cpu_threads` cho ASR; **[#13]** taskset/cgroup `CPUQuota` (làm ở Phase 4 `install-service.sh`) — acceptance **ĐO** thread thật là bước P5
- [x] `transcriber.py`: `probe_duration()` (giây, #6) + `cpu_threads`
- [x] `result_cache.py`: get/put + **[#11]** eviction code-mới (sweep nền, lock, `missing_ok`, access-order) — previews KHÔNG có LRU
- [x] `speech.py`: tra/ghi cache + log hit/miss
- [x] `transcriptions.py`: **[#7]** gate header trước khi đọc body 25MB + `reserve_audio(probed)` trước transcribe + reconcile `result.duration`; cap thời lượng ANON
- [x] `.gitignore`: `data/cache/`
- [x] `tests/test_result_cache.py`

## Success Criteria

- [ ] [#13] **Đo thực tế** khi synth preset: CPU/thread bị giới hạn (taskset/cgroup), không chỉ log config; p50 latency 1 request không tệ đi.
- [ ] [#7] ASR vượt cap-ngày bị chặn **trước** transcribe (không cháy CPU rồi mới báo); `probe_duration` trả đúng **giây** (không phải µs).
- [ ] Request lặp (cùng text+voice+format) lần 2 = cache-hit (nhanh rõ rệt, có log).
- [ ] ASR file dài hơn `anon_max_audio_seconds` (anon) → 400/413 trước khi tốn CPU.
- [ ] Budget ASR trừ theo giây-audio thật.
- [ ] `pytest -q -m "not synth"` xanh.

## Risk Assessment

- **Đặt `OMP_NUM_THREADS` quá muộn (sau import onnxruntime) → vô hiệu.** *Tín hiệu:*
  synth vẫn ăn hết 6 core. *Xử lý:* ưu tiên set ở systemd `Environment=` (Phase 4);
  code chỉ là phòng thủ. Kiểm chứng bằng đo tải CPU thực.
- **Cache phình đĩa / rác + race prune (#11):** *Tín hiệu:* `data/cache` lớn dần,
  hoặc `FileNotFoundError` khi 2 `put` cùng xóa 1 file. *Xử lý:* sweep **nền** dưới
  lock theo size+count, `unlink(missing_ok=True)`; thư mục xóa được, tự tạo lại.
- **Cache-hit vẫn trừ budget gây khó chịu:** cân nhắc miễn/nửa budget cho hit —
  để tùy chọn, mặc định tính đủ cho đơn giản & công bằng.

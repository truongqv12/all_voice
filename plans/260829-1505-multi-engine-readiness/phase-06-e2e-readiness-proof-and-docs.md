---
title: "Phase 6: E2E readiness proof + docs"
status: done
priority: P1
dependencies: [phase-02, phase-03, phase-04, phase-05]
effort: "3-4h"
---

# Phase 6: E2E readiness proof + docs

## Overview

Chứng minh mục tiêu "**sẵn sàng tích hợp**": một backend **thứ hai** cắm vào chạy trơn
qua tất cả seam (định tuyến, gate strict, options, discovery, cloning-ref_text) mà
**không sửa** router core/encoder/auth. Dùng `FakeBackend` trong test (không tải model
→ nhanh, tất định) đóng vai engine tương lai (`language="ja"`, clone cần `ref_text`).
Cuối cùng **chạy lại đúng bộ baseline phase 1** để xác nhận không hồi quy, và cập nhật
docs hợp đồng. Đây là "bước test ban đầu để kiểm tra lại — ok là được".

## Requirements

- Functional: `tests/test_multi_backend_e2e.py` đăng ký `FakeBackend` cạnh VieNeu qua fixture (teardown gỡ sạch, không rò sang test khác).
- Functional: e2e chứng minh 6 tính chất readiness (mục Architecture).
- Functional: **chạy lại toàn bộ baseline** (`test_e2e.py`, `test_transcriptions.py`, `test_readiness.py`) → xanh.
- Docs: cập nhật `docs/kien-truc-va-mo-rong.md` §5 (options/extra) và §7 (hợp đồng thêm backend); ghi rõ VoiceVox/F5 là **bước tích hợp sau**.
- Non-functional: `FakeBackend` không import engine thật, synth trả PCM tất định (vd `np.zeros`/sine ngắn).

## Architecture

**FakeBackend** (chỉ trong test) — engine thứ 2 tối giản, clone-first kiểu F5:

```python
class FakeBackend(VoiceBackend):
    name = "faketts"
    supports_cloning = True
    def __init__(self): self._clones = {}
    def list_voices(self):
        base = [Voice(id="ja_1", name="Yuki", model=self.name, language="ja")]
        return base + [Voice(id=i, name=n, model=self.name, language="ja") for i, n in self._clones.items()]
    def synthesize(self, text, voice, speed=1.0, options=None):
        return AudioResult(pcm=np.zeros(16000, dtype=np.float32), sample_rate=16000)  # 1s im lặng, đủ để encode
    def register_voice(self, voice_id, name, sample_path, *, denoise=True, use_ref_codes=True, options=None):
        if not (options or {}).get("ref_text"):
            raise InvalidOption("faketts requires ref_text to clone")   # chứng minh hợp đồng ref_text
        self._clones[voice_id] = name
    def remove_voice(self, voice_id): return self._clones.pop(voice_id, None) is not None
```

**Fixture** đăng ký/gỡ (registry là singleton toàn process → phải dọn):

```python
@pytest.fixture
def with_fake_backend():
    be = FakeBackend()
    registry.register(be)                 # thêm cạnh vieneu; vieneu vẫn default
    try: yield be
    finally:
        registry._backends.pop("faketts", None)   # dọn để không rò sang test khác
```

**6 tính chất e2e phải xanh:**

1. **Discovery models:** `GET /v1/models` chứa `faketts`.
2. **Discovery voices + filter:** `GET /v1/voices` có voice `language="ja"`; `?model=faketts` chỉ trả voice faketts; `?language=ja` tương tự.
3. **Định tuyến đúng:** `POST /v1/audio/speech {model:"faketts", voice:"ja_1", response_format:"wav"}` → 200 + audio (từ fake).
4. **Gate strict cross-backend:** `{model:"faketts", voice:"Trúc Ly"}` (voice của vieneu) → **404 unknown_voice** (không im lặng đọc sai ngôn ngữ).
5. **Lenient drop-in còn nguyên:** `{model:"tts-1", voice:"alloy"}` → 200 qua default (vieneu).
6. **Cloning đa-engine + ref_text:**
   - `POST /v1/audio/voices {model:"faketts", name, ref_text:"...", audio_sample}` → 200; voice mới xuất hiện ở `/v1/voices` dưới `faketts`; synth bằng nó → 200.
   - `POST /v1/audio/voices {model:"faketts", name, audio_sample}` **thiếu** ref_text → **400** (InvalidOption → 400, chứng minh passthrough + validate backend).
   - (options) fake synth với `extra={...}` → 200.

**Docs cập nhật** `docs/kien-truc-va-mo-rong.md`:
- §5: `style` giờ do backend validate; thêm `extra` cho param riêng engine.
- §7 "Cách thêm một model voice mới": cập nhật hợp đồng — `resolve_voice(strict=…)`, `register_voice(..., options=…)` (ref_text), chọn `model` khi enrol clone, gắn `language` cho voice, và filter `?model=/?language=`. Thêm 1 dòng: **VoiceVox/F5 chưa tích hợp — sẽ có plan riêng.**
- README.md (tùy chọn, tối thiểu): nếu muốn, thêm 1 dòng vào bảng tính năng về multi-engine readiness + `extra`/`model` khi clone. Chỉ sửa nếu thấy cần (hợp đồng public có thay đổi nhỏ).

## Related Code Files

- Create: `tests/test_multi_backend_e2e.py` (FakeBackend + fixture + 6 nhóm assert)
- Modify: `docs/kien-truc-va-mo-rong.md` (§5, §7)
- Modify: `README.md` (tùy chọn, 1 dòng)
- Modify: _(không đụng `app/**` trong phase này — nếu phải sửa app để fake chạy, đó là dấu seam chưa đủ mở → quay lại phase tương ứng)_

## Implementation Steps

1. Viết `tests/test_multi_backend_e2e.py`: `FakeBackend`, fixture `with_fake_backend`, và các test cho 6 tính chất.
2. Chạy `uv run pytest -q tests/test_multi_backend_e2e.py` → xanh.
3. **Chạy lại toàn bộ baseline**: `uv run pytest -q` → xanh (không hồi quy). Đây là bước "dùng chính test ban đầu kiểm tra lại".
4. Cập nhật `docs/kien-truc-va-mo-rong.md` §5 & §7 theo hợp đồng mới; thêm ghi chú VoiceVox/F5 là bước sau.
5. (Tùy chọn) cập nhật README bảng tính năng.
6. `ak plan check`/đánh dấu hoàn tất theo CLI; whole-plan consistency sweep.

## Success Criteria

- [x] `test_multi_backend_e2e.py` xanh; cả 6 tính chất readiness đạt.
- [x] Thêm `FakeBackend` **không** cần sửa `app/routers/*` core, `encoder`, `auth`, `schemas` (nếu cần sửa → seam chưa đủ, quay lại phase liên quan).
- [x] `uv run pytest -q` toàn bộ (baseline + mới) **xanh** → không hồi quy.
- [x] Fixture dọn sạch `faketts` (chạy lại suite nhiều lần vẫn ổn định, không rò).
- [x] Docs §5/§7 phản ánh hợp đồng mới + ghi chú "VoiceVox/F5: plan sau".

## Risk Assessment

- **Rủi ro:** `FakeBackend` rò vào test khác do registry singleton. **Tín hiệu:** test khác thấy `faketts` bất ngờ / thứ tự test đổi kết quả. **Phản ứng:** teardown pop `faketts`; cân nhắc snapshot/restore `registry._backends` nếu cần chắc hơn.
- **Rủi ro:** phải sửa `app/**` để fake chạy → chứng tỏ seam chưa đủ mở (mục tiêu readiness chưa đạt). **Phản ứng:** KHÔNG vá tạm ở phase 6; quay lại đúng phase seam (2/3/4/5) sửa cho tổng quát.
- **Rủi ro:** encode PCM `np.zeros` lỗi ở codec nào đó. **Phản ứng:** dùng `response_format:"wav"` (an toàn nhất) cho test định tuyến; hoặc sine ngắn thay zeros nếu encoder cần tín hiệu.

---
title: "Phase 4: Cloning multi-engine readiness"
status: done
priority: P1
dependencies: [phase-02]
effort: "4-5h"
---

# Phase 4: Cloning multi-engine readiness

## Overview

Mở seam cloning cho **nhiều engine cùng clone** (VieNeu VN, sau này F5 EN). Hai việc:
(1) khi enrol, cho chọn **`model`** = engine nào clone; (2) thêm **`ref_text`** — F5 cần
reference text lúc enrol, VieNeu bỏ qua. `voice_store.backend` **đã** ghi backend chủ
của mỗi clone (bảng map clone→provider có sẵn, tự quản, sống qua restart) nên không cần
bảng mới; chỉ thêm chỗ chứa `ref_text` và truyền nó qua hợp đồng enrol.

## Requirements

- Functional: `POST /v1/audio/voices` thêm form `model?` (engine enrol; thiếu → logic default hiện tại) và `ref_text?` (passthrough).
- Functional: `model` chỉ định phải là backend **đã đăng ký** và **clone được**; sai → 400.
- Functional: `register_voice` có túi `options` để truyền param riêng engine (ref_text…) mà không đổi chữ ký mỗi lần thêm engine.
- Functional: `VoiceRecord` **persist** `enrol_options` (gồm ref_text) → restart enrol lại đúng như cũ.
- Non-functional: tương thích ngược — không truyền `model`/`ref_text` → hành vi y hệt hiện tại; registry.json cũ (thiếu key mới) vẫn load được.

## Architecture

**Base** — `register_voice` thêm `options` (giữ `denoise`/`use_ref_codes` cho VieNeu):

```python
# base.py
def register_voice(self, voice_id, name, sample_path, *,
                   denoise=True, use_ref_codes=True, options: dict | None = None) -> None:
    raise NotImplementedError(...)
```

VieNeu override: nhận thêm `options=None` và **bỏ qua** (nó chỉ dùng denoise/use_ref_codes). Engine tương lai (F5) đọc `options.get("ref_text")`, thiếu → `InvalidOption`.

**voice_store** — persist túi enrol (default rỗng → forward-compat như denoise/use_ref_codes hiện có):

```python
# voice_store.py
from dataclasses import field
@dataclass
class VoiceRecord:
    ...
    denoise: bool = True
    use_ref_codes: bool = True
    enrol_options: dict = field(default_factory=dict)   # ref_text,... cho engine cần

def create(self, ..., enrol_options: dict | None = None) -> VoiceRecord:
    ...
    record = VoiceRecord(..., enrol_options=dict(enrol_options or {}))
```

> `VoiceRecord(**r)` với record JSON cũ (không có `enrol_options`) → default_factory cấp `{}` → load OK. Đây đúng pattern các field defaulted sẵn (dòng chú thích 25–28 ở file hiện tại).

**voices_admin** — chọn backend theo `model`, gom `ref_text` vào options:

```python
# voices_admin.py
def _cloning_backend(model: str | None) -> VoiceBackend:
    if model:
        be = registry.get(model)                    # get() ĐÍCH DANH: chỉ trả nếu khớp tên
        if be is None or not registry.has(model):
            raise _error(400, f"Model '{model}' is not a registered backend.", "model_not_found")
        if not be.supports_cloning:
            raise _error(400, f"Model '{model}' does not support voice cloning.", "cloning_unsupported")
        return be
    # thiếu model -> logic cũ: default nếu clone được, else backend clone đầu tiên
    ...

# trong create_voice(): thêm Form model, ref_text
enrol_options = {"ref_text": ref_text} if ref_text else {}
record = voice_store.create(..., backend=backend.name, denoise=denoise,
                            voice_id=custom_id, enrol_options=enrol_options)
backend.register_voice(record.id, record.name, record.sample_path,
                       denoise=record.denoise, use_ref_codes=record.use_ref_codes,
                       options=record.enrol_options)
```

> Lưu ý: `_cloning_backend` khi có `model` phải dùng phân giải **đích danh** (`registry.has`/duyệt `models()`), KHÔNG dùng `registry.get` lenient (get trả default cho tên lạ → sẽ enrol nhầm). Kiểm `registry.has(model)` trước.

**main** — reenrol truyền options đã lưu:

```python
# main.py _reenrol_cloned_voices()
backend.register_voice(record.id, record.name, record.sample_path,
                       denoise=record.denoise, use_ref_codes=record.use_ref_codes,
                       options=record.enrol_options)
```

## Related Code Files

- Modify: `app/backends/base.py` (`register_voice(..., options=None)`)
- Modify: `app/backends/vieneu_backend.py` (nhận `options`, bỏ qua)
- Modify: `app/voice_store.py` (`enrol_options` field + `create` param)
- Modify: `app/routers/voices_admin.py` (`model?`+`ref_text?` form, `_cloning_backend(model)`, truyền options)
- Modify: `app/main.py` (`_reenrol_cloned_voices` truyền options)
- Modify: `tests/test_readiness.py` (test model/ref_text/persist)

## Implementation Steps

1. `base.py`: thêm `options` vào chữ ký `register_voice`.
2. `vieneu_backend.py`: thêm `options=None` vào override, không dùng (chú thích rõ VieNeu chỉ dùng denoise/use_ref_codes).
3. `voice_store.py`: thêm `enrol_options` (default_factory=dict) + tham số `enrol_options` cho `create`; đảm bảo `_save/_load` round-trip.
4. `voices_admin.py`: đổi `_cloning_backend()` → `_cloning_backend(model)`; thêm Form `model`, `ref_text`; gom `enrol_options`; truyền `options` vào `register_voice`.
5. `main.py`: `_reenrol_cloned_voices` truyền `options=record.enrol_options`.
6. Test ở `test_readiness.py`:
   - `test_clone_default_model_unchanged`: create không `model`/`ref_text` → 200 (như baseline).
   - `test_clone_explicit_model_vieneu`: `model="vieneu"` → 200.
   - `test_clone_unknown_model_400`: `model="voicevox"` (chưa đăng ký) → 400 `model_not_found`.
   - `test_clone_ref_text_ignored_by_vieneu`: `ref_text="hello"` trên vieneu → 200 (không crash).
   - `test_voice_store_persists_enrol_options` (unit, không qua HTTP): `create(..., enrol_options={"ref_text":"x"})` → đọc lại registry.json thấy key; load `VoiceRecord` từ JSON **cũ thiếu key** → default `{}`.
7. `uv run pytest -q` → toàn bộ xanh (gồm `test_voice_clone_lifecycle`).

## Success Criteria

- [x] Enrol chọn được `model`; `model` lạ/không-clone → 400 đúng code.
- [x] `ref_text` được nhận, persist trong `enrol_options`, truyền qua `register_voice`; VieNeu bỏ qua an toàn.
- [x] registry.json cũ (thiếu `enrol_options`) vẫn load; record mới round-trip đủ.
- [x] Clone lifecycle cũ + toàn bộ suite vẫn xanh.

## Risk Assessment

- **Rủi ro:** `_cloning_backend(model)` lỡ dùng `registry.get` lenient → tên lạ enrol nhầm vào default. **Tín hiệu:** `test_clone_unknown_model_400` trả 200. **Phản ứng:** kiểm `registry.has(model)` đích danh trước khi enrol.
- **Rủi ro:** thêm field dict vào `VoiceRecord` phá load registry cũ. **Tín hiệu:** `test_voice_store_persists_enrol_options` (nhánh load JSON cũ) fail. **Phản ứng:** dùng `field(default_factory=dict)`; test cả nhánh JSON thiếu key.
- **Rủi ro:** backend đích danh (`model`) trùng luồng resolve của phase 2. **Phản ứng:** clone-create dùng phân giải đích danh riêng (`has`/`models()`), độc lập với `resolve()` lenient của synth.

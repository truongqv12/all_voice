---
title: "Phase 3: Input options gate"
status: done
priority: P1
dependencies: [phase-02]
effort: "3-4h"
---

# Phase 3: Input options gate

## Overview

Làm gate **đầu vào** trung lập với provider. Hiện `style` bị ép cứng bằng
`Literal[...]` giá trị riêng của VieNeu ngay trong schema chung → engine khác không
nhét knob của nó vào được. Đổi sang: schema **chấp nhận** `style` tự do + một túi
`extra` cho param engine tương lai; **validation dời xuống từng backend** (VieNeu vẫn
báo 400 cho style sai). Nhờ đó `style="tin_tuc"` map sang engine khác được, còn param
kiểu `speedScale` (VoiceVox) đi qua `extra` mà không phải sửa schema.

## Requirements

- Functional: bỏ `Literal` ở `SpeechRequest.style`; thêm `extra: dict | None` (OpenAI extension, qua `extra_body`).
- Functional: VieNeu **tự validate** `style ∈ {tu_nhien, tin_tuc, doc_truyen}`; sai → 400 (giữ status cũ).
- Functional: `extra` được gộp vào options truyền xuống backend; VieNeu **bỏ qua** key nó không hiểu, không crash.
- Non-functional: tương thích ngược — `style="doc_truyen"`→200, `style="opera"`→400; client cũ không đổi.

## Architecture

**Base** — exception chuyên cho option sai (router map → 400, tách khỏi 500):

```python
# base.py
class InvalidOption(ValueError):
    """Backend từ chối một tuning option (giá trị/khoá không hợp lệ). Router -> 400."""
```

**Schema** — `style` tự do + `extra`; gộp options:

```python
# schemas.py
style: str | None = Field(default=None, description="Reading style; giá trị hợp lệ do backend quy định (VieNeu: tu_nhien/tin_tuc/doc_truyen).")
extra: dict[str, Any] | None = Field(default=None, description="OpenAI extension: tham số riêng của backend (qua extra_body). Backend bỏ qua khoá không hiểu.")

_OPTION_KEYS = ("style",)
def backend_options(self) -> dict[str, Any]:
    opts = dict(self.extra or {})
    for k in self._OPTION_KEYS:
        if (v := getattr(self, k)) is not None:
            opts[k] = v
    return opts
```

**VieNeu adapter** — validate style, map/bỏ qua phần còn lại:

```python
# vieneu_backend.py
_STYLES = {"tu_nhien", "tin_tuc", "doc_truyen"}
_INFER_OPTIONS = ("style",)

def synthesize(self, text, voice, speed=1.0, options=None):
    options = options or {}
    style = options.get("style")
    if style is not None and style not in self._STYLES:
        raise InvalidOption(f"Unknown style '{style}'. Allowed: {sorted(self._STYLES)}")
    kwargs = {k: options[k] for k in self._INFER_OPTIONS if k in options}
    ...
```

**Router speech** — map `InvalidOption` → 400 (không để rơi vào handler 500):

```python
# speech.py — quanh chỗ gọi synthesize
try:
    result = await anyio.to_thread.run_sync(backend.synthesize, req.input, voice, req.speed, options)
except InvalidOption as exc:
    raise HTTPException(400, {"message": str(exc), "type": "invalid_request_error", "code": "invalid_option"})
```

> Ghi chú tương thích: trước đây `style` sai bị Pydantic chặn (RequestValidationError → 400). Sau đổi, VieNeu chặn (InvalidOption → 400). **Status vẫn 400**; test baseline chỉ assert status nên vẫn xanh. `message/param` có thể khác — không có test cũ nào phụ thuộc nội dung đó.

## Related Code Files

- Modify: `app/backends/base.py` (thêm `InvalidOption`)
- Modify: `app/schemas.py` (`style: str|None`, `extra: dict|None`, `backend_options`)
- Modify: `app/backends/vieneu_backend.py` (validate style, đọc options)
- Modify: `app/routers/speech.py` (map `InvalidOption`→400)
- Modify: `tests/test_readiness.py` (test extra passthrough + style-invalid do backend)

## Implementation Steps

1. Thêm `InvalidOption(ValueError)` vào `base.py`; export nếu cần.
2. `schemas.py`: đổi `style` sang `str | None`; thêm `extra: dict[str, Any] | None`; cập nhật `backend_options()` gộp `extra`+`style`. Giữ ví dụ `style="doc_truyen"` trong docs schema.
3. `vieneu_backend.py`: validate `style` (raise `InvalidOption`), tiếp tục chỉ forward key nó hiểu.
4. `speech.py`: bọc `synthesize` bắt `InvalidOption`→400 `invalid_option`.
5. Test ở `test_readiness.py`:
   - `test_options_style_invalid_400_from_backend`: `style="opera"`→400.
   - `test_options_extra_passthrough_ignored`: `extra={"foo":1,"speedScale":1.2}` + style hợp lệ → 200 (VieNeu bỏ qua, không crash).
6. `uv run pytest -q` → toàn bộ xanh (bao gồm `test_tuning_options` cũ ở `test_e2e.py`).

## Success Criteria

- [x] `style` không còn `Literal`; `extra` tồn tại và được gộp vào options.
- [x] `style` sai → 400 (do VieNeu); `style` đúng → 200.
- [x] `extra` dict lạ được chấp nhận và bỏ qua an toàn.
- [x] `test_tuning_options` (test_e2e.py) và toàn bộ suite vẫn xanh.

## Risk Assessment

- **Rủi ro:** nới `style` sang `str` làm mất validation ở tầng schema → nếu quên chặn ở backend, style rác lọt vào engine. **Tín hiệu:** `test_options_style_invalid_400` fail (trả 200). **Phản ứng:** validation ở VieNeu là bắt buộc trong phase này; test chặn.
- **Rủi ro:** bắt `InvalidOption` quá rộng (mọi `ValueError`) → nuốt lỗi thật thành 400. **Phản ứng:** chỉ bắt đúng lớp `InvalidOption`, không bắt `ValueError` chung; lỗi khác vẫn rơi handler 500.
- **Rủi ro:** `extra` không giới hạn kích thước. **Phản ứng:** readiness scope để adapter tự lo (Open question ở plan.md); không thêm giới hạn bây giờ (YAGNI).

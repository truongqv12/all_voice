---
title: "Phase 5: Voice discovery filter"
status: done
priority: P2
dependencies: [phase-02]
effort: "1-2h"
---

# Phase 5: Voice discovery filter

## Overview

Cho UI/client "chọn ngôn ngữ → ra danh sách voice" và "xem voice theo provider" bằng
cách thêm filter `?model=` và `?language=` (cộng dồn) vào `GET /v1/voices`. Thuần
**additive**: không tham số → trả tất cả như hiện tại. Đây là cơ chế lấy danh sách
voice theo ngôn ngữ mà không cần field `language` trên request TTS.

## Requirements

- Functional: `GET /v1/voices?model=vieneu` → chỉ voice của backend đó.
- Functional: `GET /v1/voices?language=vi` → chỉ voice ngôn ngữ đó.
- Functional: kết hợp cả hai → AND.
- Functional: không tham số → toàn bộ (bất biến).
- Non-functional: filter phân biệt hoa/thường hợp lý cho `language` (so khớp bình thường; không tự suy diễn locale).

## Architecture

```python
# voices.py
from fastapi import Query

@router.get("/voices", ...)
async def list_voices(
    model: str | None = Query(None, description="Chỉ voice của backend này."),
    language: str | None = Query(None, description="Chỉ voice ngôn ngữ này (vd `vi`, `ja`, `en`)."),
    _key: str = Depends(require_api_key),
) -> VoiceList:
    voices = registry.all_voices()
    if model:
        voices = [v for v in voices if v.model == model]
    if language:
        voices = [v for v in voices if v.language == language]
    data = [VoiceInfo(id=v.id, name=v.name, model=v.model, language=v.language, styles=v.styles) for v in voices]
    return VoiceList(data=data)
```

Quyết định (Open question ở plan.md): `model`/`language` không khớp gì → **200 danh
sách rỗng** (thân thiện khám phá), không 400. Đổi nếu bạn muốn chặt.

## Related Code Files

- Modify: `app/routers/voices.py` (thêm Query `model`,`language` + lọc)
- Modify: `tests/test_readiness.py` (test filter)

## Implementation Steps

1. Thêm 2 Query optional vào `list_voices`; lọc `registry.all_voices()` theo model/language.
2. Test ở `test_readiness.py`:
   - `test_voices_filter_by_model`: `?model=vieneu` → mọi item `model=="vieneu"`; số lượng > 0.
   - `test_voices_filter_by_language`: `?language=vi` → mọi item `language=="vi"`.
   - `test_voices_filter_unknown_returns_empty`: `?model=voicevox` → 200, `data==[]`.
   - `test_voices_no_filter_unchanged`: không param → như baseline.
3. `uv run pytest -q` → xanh.

## Success Criteria

- [x] Lọc theo `model`, theo `language`, và AND cả hai hoạt động.
- [x] Không param → hành vi cũ (bất biến); filter không khớp → 200 rỗng.
- [x] Toàn bộ suite xanh.

## Risk Assessment

- **Rủi ro:** đổi chữ ký handler làm hỏng OpenAPI/`test_voices`. **Tín hiệu:** `test_voices` (test_e2e.py) fail. **Phản ứng:** tham số Query đều optional default None → schema thêm query params, không phá response model.
- **Rủi ro:** người dùng kỳ vọng 400 cho model lạ. **Phản ứng:** đã ghi Open question; mặc định 200 rỗng, dễ đổi 1 dòng nếu bạn chốt khác.

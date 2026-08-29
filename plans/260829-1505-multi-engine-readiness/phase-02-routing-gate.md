---
title: "Phase 2: Routing gate (strict/lenient)"
status: done
priority: P1
dependencies: [phase-01]
effort: "3-4h"
---

# Phase 2: Routing gate (strict/lenient)

## Overview

Bịt lỗ hổng "im lặng sai ngôn ngữ": khi client gọi **đích danh** một model đã đăng ký
nhưng gửi voice không tồn tại → trả **404** thay vì âm thầm lấy `voices[0]`. Khi model
**lạ** (OpenAI generic như `tts-1`) → giữ **lenient** fallback preset đầu để "SDK openai
chạy ngay" không vỡ. Đây là cái gate quyết định "đầu vào ↔ đầu ra đồng nhất".

## Requirements

- Functional: `registry` phân biệt được model **quen** (khớp backend đã đăng ký) vs **lạ** (rơi về default).
- Functional: `resolve_voice` nhận cờ `strict`; strict → voice lạ báo lỗi (router 404 `unknown_voice`); non-strict → lenient như hiện tại.
- Non-functional: **giữ `registry.get()`** cho các caller khác (models.py, voices.py, voices_admin.py) — chỉ **thêm** API mới, không xóa.
- Non-functional: tương thích ngược — `tts-1`+`alloy` vẫn 200; voice thật/clone của vieneu vẫn resolve.

## Architecture

**Registry** — thêm phân giải có cờ "explicit", không đụng `get()`:

```python
# registry.py
def resolve(self, model: str | None) -> tuple[VoiceBackend | None, bool]:
    """(backend, explicit). explicit=True nếu `model` khớp một backend đã đăng ký;
    False nếu rơi về default (model lạ/rỗng — kiểu OpenAI)."""
    if model and model in self._backends:
        return self._backends[model], True
    if self._default is not None:
        return self._backends[self._default], False
    return None, False
```

**Base** — `resolve_voice` thêm `strict`, tách "không tìm thấy" khỏi "fallback":

```python
# base.py
def resolve_voice(self, voice: str | None, *, strict: bool = False) -> str | None:
    voices = self.list_voices()
    if not voices:
        raise RuntimeError(f"Backend '{self.name}' exposes no voices")
    ids = {v.id for v in voices}
    if voice in ids:
        return voice
    names = {v.name: v.id for v in voices}
    if voice in names:
        return names[voice]
    if strict:
        return None                 # gọi đích danh + voice lạ -> router trả 404
    return voices[0].id             # OpenAI generic -> lenient (giữ drop-in)
```

**Router speech** — dùng `resolve` + 404 khi voice lạ (chỉ xảy ra khi strict):

```python
# speech.py
backend, explicit = registry.resolve(req.model)
if backend is None:
    raise HTTPException(404, {... "model_not_found"})
voice = backend.resolve_voice(req.voice, strict=explicit)
if voice is None:
    raise HTTPException(404, {"message": f"Voice '{req.voice}' not found for model '{req.model}'.",
                             "type": "invalid_request_error", "code": "unknown_voice"})
```

Bảng hành vi (bất biến quan trọng để không phá code):

| model | voice | explicit | Kết quả |
|---|---|---|---|
| `vieneu` (quen) | `Trúc Ly` / clone id | True | resolve OK (như cũ) |
| `vieneu` (quen) | không tồn tại | True | **404 unknown_voice** (MỚI; trước là 200 preset đầu) |
| `tts-1` (lạ) | `alloy` | False | lenient → preset đầu → **200** (giữ nguyên) |
| `""`/thiếu | bất kỳ | False | default + lenient |

## Related Code Files

- Modify: `app/backends/registry.py` (thêm `resolve`, giữ `get`)
- Modify: `app/backends/base.py` (`resolve_voice(strict=…)`)
- Modify: `app/routers/speech.py` (dùng `resolve`, 404 `unknown_voice`)
- Modify: `tests/test_readiness.py` (thêm test hành vi mới)

## Implementation Steps

1. Thêm `Registry.resolve()` trả `(backend, explicit)`; giữ nguyên `get()`.
2. Sửa `VoiceBackend.resolve_voice` thêm `*, strict: bool = False`; strict → `None` khi không khớp.
3. Sửa `speech.py`: thay `registry.get(req.model)` + `backend.resolve_voice(req.voice)` bằng luồng `resolve` + kiểm `voice is None` → 404.
4. Thêm test ở `test_readiness.py`:
   - `test_gate_known_model_unknown_voice_404`: `{model:"vieneu", voice:"khong_ton_tai"}` → 404, code `unknown_voice`.
   - `test_gate_unknown_model_alias_still_200`: `{model:"tts-1", voice:"alloy"}` → 200 (re-assert lenient).
   - `test_gate_known_model_real_voice_200`: voice thật của vieneu → 200.
5. Chạy `uv run pytest -q` → toàn bộ xanh (bao gồm baseline phase 1).

## Success Criteria

- [x] `registry.resolve` trả đúng cờ explicit; `get` còn nguyên và mọi caller cũ chạy.
- [x] `model` quen + voice lạ → 404 `unknown_voice`.
- [x] `tts-1`+`alloy` vẫn 200; voice thật/clone vieneu vẫn resolve.
- [x] Toàn bộ suite xanh; không đụng encoder/auth/schemas.

## Risk Assessment

- **Rủi ro:** đổi `vieneu`+voice-sai từ 200→404 làm vỡ client đang dựa vào fallback im lặng. **Tín hiệu:** client báo 404 cho voice họ tưởng có. **Phản ứng:** đây là chủ đích (đã chốt brainstorm) và không test cũ nào dựa vào; message 404 nêu rõ "voice not found for model" để client tự sửa. Nếu cần nới, có thể cho `vieneu` (vốn là default) chạy lenient — nhưng KHÔNG làm trừ khi bạn yêu cầu.
- **Rủi ro:** caller khác gọi `resolve_voice` thiếu `strict`. **Phản ứng:** default `strict=False` giữ hành vi cũ; chỉ router speech truyền cờ.

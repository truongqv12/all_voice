---
title: "Phase 1: Baseline test oracle (test-first)"
status: done
priority: P1
dependencies: []
effort: "2-3h"
---

# Phase 1: Baseline test oracle (test-first)

## Overview

Trước khi đụng bất kỳ code sản phẩm nào, khóa **hành vi hiện tại** thành một bộ test
làm **oracle hồi quy** (đây là "bước test trước" theo yêu cầu). Phase này **không sửa
code trong `app/`** — chỉ chạy suite hiện có cho xanh và **thêm** test ghim đúng các
seam sắp đổi, để phase 6 chạy lại chính bộ này mà xác nhận không phá gì.

## Requirements

- Functional: chạy `uv run pytest -q` hiện tại → **xanh** (đây là mốc gốc).
- Functional: thêm `tests/test_readiness.py` ghim **các bất biến** (invariants) mà refactor KHÔNG được đổi.
- Non-functional: KHÔNG chạm `app/**`. KHÔNG thêm dependency. Test mới phải chạy được trên CPU.
- Non-functional: tách rõ **bất biến** (giữ mãi) khỏi **hành vi sẽ đổi có chủ đích** (ghim ở phase sau) để bộ baseline luôn xanh xuyên suốt.

## Architecture

`tests/test_readiness.py` dùng `fastapi.testclient.TestClient` như `test_e2e.py`
(chung `AUTH` header, key `dev-key`). Ghim **invariants** — những thứ phải đúng cả
trước và sau refactor:

- `GET /v1/models` chứa `"vieneu"`.
- `GET /v1/voices` trả `object=="list"`; mỗi item có đủ khóa `id/name/model/language/styles`; mọi voice hiện tại `language=="vi"`, `model=="vieneu"`.
- Drop-in OpenAI: `POST /v1/audio/speech {model:"tts-1", voice:"alloy"}` → **200** + audio.
- `style="doc_truyen"` → **200**; `style="opera"` → **400** (bất biến: style sai bị chặn — dù ở phase 3 tầng chặn dời xuống backend, **status vẫn 400**).
- Clone lifecycle (không truyền `model`): create → xuất hiện ở `/v1/audio/voices` và `/v1/voices` → synth bằng `{"id": voice_id}` → delete. (Đã có ở `test_e2e.py`; ở đây chỉ assert lại phần **shape** không dùng model, tránh trùng lặp synth nặng.)

**Không** ghim ở phase này (vì sẽ đổi có chủ đích): `model="vieneu"` + voice không tồn tại. Hiện trả 200 (preset đầu); phase 2 đổi thành 404 và **test cho case này viết ở phase 2**, không viết ở đây.

## Related Code Files

- Create: `tests/test_readiness.py`
- Modify: _(không có — phase test-first thuần)_
- Delete: _(không)_

## Implementation Steps

1. Chạy `uv run pytest -q` → xác nhận baseline xanh; lưu lại danh sách test pass (mốc gốc). Nếu môi trường chưa có weights, để pytest tự tải lần đầu (hoặc chạy `uv run pytest -q tests/test_readiness.py -m "not synth"` cho vòng nhanh — nhưng vòng đầy đủ vẫn phải xanh).
2. Viết `tests/test_readiness.py` với các test invariant ở mục Architecture. Đặt tên rõ: `test_baseline_models_lists_vieneu`, `test_baseline_voices_shape_and_language`, `test_baseline_openai_dropin_alias`, `test_baseline_style_valid_and_invalid`, `test_baseline_clone_appears_in_both_lists`.
3. Tách test synth-nặng (tải model) sau marker `synth`, lọc bằng `-m "not synth"` để vòng lặp dev nhanh (dùng `-m` chứ không `-k`: `-k` sẽ bắt nhầm test có chữ "synth" trong tên); nhưng KHÔNG loại chúng khỏi suite đầy đủ.
4. Chạy `uv run pytest -q tests/test_readiness.py` → xanh.
5. Chạy `uv run pytest -q` (toàn bộ) → xanh. Đây là **bộ baseline** phase 6 sẽ chạy lại.

## Success Criteria

- [x] `tests/test_readiness.py` tồn tại, mọi test xanh.
- [x] `uv run pytest -q` toàn bộ xanh; không sửa file nào trong `app/`.
- [x] Có test ghim: models chứa vieneu; voices shape+language; drop-in alias 200; style 200/400; clone xuất hiện ở cả 2 list.
- [x] KHÔNG có test nào assert `model="vieneu"`+voice-sai → 200 (để phase 2 đổi được mà không phá baseline).

## Risk Assessment

- **Rủi ro:** synth VieNeu thật tải ~313MB lần đầu → CI chậm/độ giòn mạng. **Tín hiệu:** test timeout/tải fail. **Phản ứng:** cho phép chạy vòng nhanh bằng `-m "not synth"` khi dev; vòng đầy đủ chạy khi có mạng/weights. Không đổi hành vi app.
- **Rủi ro:** ghim nhầm một hành vi sắp-đổi thành invariant → phase 2 phá baseline. **Phản ứng:** tuân thủ mục "Không ghim" ở trên; review lại danh sách assert trước khi sang phase 2.

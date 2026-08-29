---
title: "multi-engine-readiness"
description: "Mở seam để sẵn sàng cắm engine đa ngôn ngữ (VoiceVox JA / F5 EN) — refactor tương thích ngược, CHƯA tích hợp engine thật."
status: completed
priority: P1
effort: "1-2d"
tags: [backend, refactor, tts, readiness, openai-compat]
created: 2026-08-29
---

# multi-engine-readiness

## Overview

Chuẩn bị (không tích hợp) cho việc cắm thêm engine voice đa ngôn ngữ — **VoiceVox**
(tiếng Nhật) và **F5-TTS** (tiếng Anh, clone-first). Plan này **chỉ mở các "gate"**
trong lõi để sau này thêm adapter là drop-in, **không thêm engine thật bây giờ** và
**không phá code hiện tại** (VieNeu phải xanh nguyên trạng).

Thiết kế đã chốt qua brainstorm: **hướng B** (`model` + `voice`), gate định tuyến
**strict/lenient**, gate input **options passthrough**, cloning **đa-engine
(model + ref_text)**, và **filter khám phá** `?model=/?language=`. Ngôn ngữ vẫn là
**thuộc tính của voice/backend** (chọn ngôn ngữ = chọn voice/model) — KHÔNG thêm
field `language` vào request TTS (giữ thuần OpenAI).

**Vòng test theo yêu cầu (TDD):** Phase 1 viết **bộ test baseline làm oracle** (chạy
xanh trước khi sửa). Các phase 2–5 refactor, mỗi phase chạy lại test liên quan.
Phase 6 **chạy lại đúng bộ baseline** để xác nhận không hồi quy + **e2e** chứng minh
"một backend thứ 2 cắm vào được mà không đụng lõi".

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Định tuyến strict/lenient: `model` quen + voice sai → 404; `model` lạ (OpenAI) → lenient giữ drop-in | P1 |
| 2 | Gate input trung lập provider: `style` → passthrough + `extra`, validation dời về backend (giữ 400) | P1 |
| 3 | Cloning sẵn sàng đa-engine: chọn `model` khi enrol + `ref_text` passthrough + persist qua restart | P1 |
| 4 | Khám phá voice theo ngôn ngữ/provider: `GET /v1/voices?model=&language=` (additive) | P2 |
| 5 | Chứng minh readiness bằng e2e với backend giả (2 backend) + cập nhật docs hợp đồng | P1 |
| 6 | Tương thích ngược tuyệt đối: mọi test VieNeu hiện có vẫn xanh | P1 |

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Phase 1: Baseline test oracle (test-first)](./phase-01-start.md) | Done |
| 2 | [Phase 2: Routing gate (strict/lenient)](./phase-02-routing-gate.md) | Done |
| 3 | [Phase 3: Input options gate](./phase-03-input-options-gate.md) | Done |
| 4 | [Phase 4: Cloning multi-engine readiness](./phase-04-cloning-multi-engine-readiness.md) | Done |
| 5 | [Phase 5: Voice discovery filter](./phase-05-voice-discovery-filter.md) | Done |
| 6 | [Phase 6: E2E readiness proof + docs](./phase-06-e2e-readiness-proof-and-docs.md) | Done |

## Design decisions (đã chốt)

- **B, không A/C:** client gửi `model`+`voice`; `voice` id chỉ cần duy nhất trong 1 backend. Không làm voice-id toàn cục (khỏi lo id số của VoiceVox trùng).
- **Strict/lenient:** `registry` phân biệt model **quen** (đã đăng ký) vs **lạ** (rơi về default). Quen + voice lạ → **404**; lạ (vd `tts-1`) → **lenient** fallback preset đầu (giữ "OpenAI SDK chạy ngay").
- **Options gate:** schema thôi ép `style` bằng `Literal`; mỗi backend **tự validate** knob nó sở hữu (VieNeu vẫn 400 với style sai). Thêm `extra: dict` để param engine tương lai (speedScale của VoiceVox…) lọt qua mà không sửa schema.
- **Cloning:** `voice_store.backend` **đã** ghi backend chủ của mỗi clone → bảng map clone→provider có sẵn, tự quản, sống qua restart. Chỉ cần thêm `model` (enrol vào engine nào) + `ref_text` (F5 cần) + persist.
- **Ngôn ngữ:** là `Voice.language`, dùng để lọc/hiển thị. Không có field `language` trên request TTS.

## Non-goals (tích hợp thật để plan sau)

- KHÔNG viết adapter VoiceVox thật (HTTP client, `VOICEVOX_URL`, gọi `/speakers`+`audio_query`).
- KHÔNG viết adapter F5-TTS thật (torch model, weights, reference-text synth).
- KHÔNG synth tiếng Nhật/Anh thật.
- KHÔNG thêm field `language` vào `POST /v1/audio/speech`.
- KHÔNG làm global voice-id routing, KHÔNG làm catalog alias cross-provider.
- KHÔNG nối `speed` native cho engine cụ thể (đi kèm adapter sau).

## Testing strategy (vòng TDD mỗi phase)

1. **Baseline xanh** (Phase 1 oracle: `test_e2e.py` + `test_transcriptions.py` + `test_readiness.py`).
2. Viết/điều chỉnh test cho hành vi mới/đổi của phase.
3. Cài đặt tối thiểu.
4. Chạy test phase + **toàn bộ suite** → xanh.
5. Phase 6: chạy lại **nguyên bộ baseline** + e2e 2-backend (dùng `FakeBackend` không cần model → nhanh, tất định).

> Lưu ý chi phí: test synth VieNeu thật tải weights (~313MB) lần đầu; test `FakeBackend` cố ý **không** dùng model để chạy nhanh.

## Success Criteria

- [x] Toàn bộ test VieNeu/ASR hiện có vẫn **xanh** sau mọi phase (không hồi quy).
- [x] `model` quen + voice sai → **404 `unknown_voice`**; `tts-1`+`alloy` vẫn **200**.
- [x] `style` sai vẫn **400** (do backend validate); `extra` dict được chấp nhận & bỏ qua an toàn.
- [x] Enrol clone chọn được `model`; `ref_text` được persist & truyền qua; clone sống qua restart.
- [x] `GET /v1/voices?model=&language=` lọc đúng; không tham số → như cũ.
- [x] E2E: `FakeBackend` (backend thứ 2, `language="ja"`, clone cần `ref_text`) xuất hiện ở `/v1/models`+`/v1/voices`, định tuyến đúng, cross-backend voice → 404 — **không sửa** router core/encoder/auth để có nó.
- [x] Docs `kien-truc-va-mo-rong.md` §5 & §7 phản ánh hợp đồng mới; ghi rõ VoiceVox/F5 là bước sau.

## Open questions

_(Đã chốt trong Validation Log — không còn câu hỏi mở.)_

## Validation Log

### Verification Results (Step 2.5)
- Tier: **Full** (6 phase). Claims checked: 12 · Verified: **12** · Failed: **0** · Unverified: 0.
- Bằng chứng: `resolve_voice` chỉ 1 caller (`speech.py:54`); `register_voice` đúng 2 caller (`main.py:39`, `voices_admin.py:91`); `registry.get` các caller khác giữ nguyên (không xóa `get`); `voice_store.create`/`VoiceRecord` chỉ construct tại `voice_store.py:72` + load `:43`; `voices_admin.py:95` `except Exception → 400` đã bọc `register_voice` (thiếu `ref_text` → 400 tự động).

### Session 1 — Quyết định (4)
1. **Strict scope:** model quen (kể cả `vieneu`) + voice sai → **404 đồng nhất**. Xác nhận Phase 2 (vieneu strict; `tts-1` vẫn lenient). Đổi hành vi nhỏ: `vieneu`+typo trước 200 nay 404 (không test nào dựa vào).
2. **Filter unknown:** `GET /v1/voices?model=<lạ>` → **200 danh sách rỗng**. Xác nhận Phase 5.
3. **`extra` guard:** **để adapter lo sau** (không guard ở bước readiness). Xác nhận Phase 3.
4. **Docs scope:** chỉ `docs/kien-truc-va-mo-rong.md` §5/§7 (+ghi chú VoiceVox/F5 bước sau); **README để nguyên**. Xác nhận Phase 6.

### Phase propagation
- Không phase nào cần sửa: cả 4 câu trả lời trùng mặc định plan. (Phase 2/3/5/6 giữ nguyên nội dung đã viết.)

### Whole-Plan Consistency Sweep
- Đọc lại `plan.md` + 6 phase. Không thuật ngữ cũ/mâu thuẫn; `resolve()`/`InvalidOption`/`enrol_options`/filter dùng nhất quán. Quyết định Session 1 củng cố plan hiện có. **Zero mâu thuẫn chưa giải quyết** → đủ điều kiện cook.

<!-- slug: multi-engine-readiness -->

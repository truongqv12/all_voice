---
phase: 7
title: "E2E Visual + vision review kết quả"
status: completed
priority: P1
effort: "0.5-1d"
dependencies: [6]
---

# Phase 7: E2E Visual + vision review kết quả

## Overview
Chốt thẩm mỹ: **sub-agent thao tác** chụp ma trận ảnh dữ liệu thật của các luồng mới → **vision
review** (đọc ảnh, soi AI-slop/vỡ layout/cuộn ngang/tương phản) → **vòng lặp tự sửa** tới hội tụ →
report. Đây là yêu cầu "đọc và vision kết quả test".
<!-- Updated: Validation Session 1 - state subtitle-kèm-voice mới là SRT; "export" ở khu transcribe là panel cũ (VTT/TXT giữ nguyên) -->

## Requirements
- Functional:
  - Chụp ma trận ảnh **dữ liệu thật** cho: compose (idle/loading/progress/success/error/subtitle "gần đúng"), transcribe (drop/upload%/transcribing/kết quả/export/lỗi 503-asr), preview (playing/không-mẫu) — × breakpoints (mobile/tablet/desktop) × theme (light/dark) × VN/EN (smoke).
  - **Vision review** từng ảnh: dùng **`agy` CLI** (nếu có trên PATH) hoặc `ak:ai-multimodal` — chấm AI-slop, vỡ khung, tràn chữ mobile, tương phản, trạng thái loading/timeout/error rõ ràng.
  - **Vòng lặp tự sửa:** finding major → sửa FE → chụp lại → review lại; trần 4 vòng hoặc 0 finding major.
- Non-functional: ảnh chờ `network-idle`/`fonts.ready`; không FOUC khi đổi theme; report `plans/reports/visual-review-260831-*.md` với verdict cuối + ảnh dẫn chứng.

## Architecture
- Harness: tái dùng cơ chế capture `frontend/e2e/*` (đã có từ plan trước) — mở rộng cho state mới (subtitle/progress/timeout/error/preview).
- Backend dev :8125 (như P6). Sub-agent điều phối capture; vision tool đọc thư mục ảnh, trả findings JSON; controller quyết định sửa/hội tụ.
- Ưu tiên state khó: **progress/timeout/error** và **subtitle card "gần đúng"** (mới, dễ AI-slop/nhãn khó hiểu).

## Related Code Files
- Modify: `frontend/e2e/*` (capture ma trận state mới)
- Modify (khi có finding): các component FE liên quan (compose/transcribe/preview/subtitle)
- Output: `plans/reports/visual-review-260831-*.md` + thư mục ảnh (`__screenshots__/` hoặc tương tự)

## Implementation Steps
1. `ak:web-testing`: mở rộng script capture cho các state mới (subtitle/progress/timeout/error/preview).
2. Chạy capture ma trận trên backend dev :8125 (dữ liệu thật, text ngắn).
3. **Vision review** bằng `agy` CLI (print/JSON) hoặc `ak:ai-multimodal` — thu findings.
4. Vòng lặp tự sửa tới 0 finding major hoặc trần 4 vòng; ghi report + verdict cuối.
5. `ak:git` commit; cập nhật status plan.

## Success Criteria
- [ ] Ma trận ảnh dữ liệu thật đủ 2 khu × breakpoints × theme, gồm state mới (subtitle/progress/timeout/error/preview).
- [ ] Vision review chạy (agy hoặc ai-multimodal); **0 finding major** ở verdict cuối (hoặc trần vòng lặp + ghi rõ tồn đọng).
- [ ] Không AI-slop / vỡ layout / cuộn ngang / tràn chữ mobile; loading/timeout/error rõ ràng.
- [ ] Report `plans/reports/visual-review-260831-*.md` có verdict + ảnh dẫn chứng.

## Risk Assessment
- **Rủi ro:** không có `agy` trên PATH. **Tín hiệu:** command not found. **Ứng phó:** fallback `ak:ai-multimodal` (Gemini vision) đọc ảnh; nếu cả hai thiếu → review thủ công + ghi hạn chế.
- **Rủi ro:** vòng lặp tự sửa lan man/không hội tụ. **Tín hiệu:** >4 vòng còn major. **Ứng phó:** trần 4 vòng, liệt kê tồn đọng cho user quyết, không kéo dài vô hạn.
- **Rủi ro:** state khó tái lập (timeout/error) để chụp. **Tín hiệu:** ảnh không ra state. **Ứng phó:** route-intercept ép state (như P6) trước khi chụp.

# Checklist thực thi — TTS Frontend Visual Shell

## Bằng chứng khởi điểm

- Repo chưa có `frontend/`; chỉ có `tests/e2e/` cho UI cũ `web/index.html`.
- Backend Python dùng 8123/8124; mọi phase FE mở để kiểm tra tại `http://localhost:5273` (`strictPort`), không chồng tiến trình. Phase 7 preview production dùng 4273.
- Không đổi `app/`, mã Python, `web/index.html`, proxy/nginx hay gọi API thật. Toàn bộ hành vi là mock qua interface; logic cắt subtitle client-side là ngoại lệ chạy thật theo fixture.

## Scope guard bắt buộc

Chỉ tạo/sửa trong `frontend/`, `scripts/visual-review/`, `.gitignore` (nếu cần bỏ ảnh capture), và báo cáo `plans/reports/`. Không thêm backend, auth/consent enforcement, MSE streaming, synth/transcribe/clone thật, TTS→SRT thật, hay thay UI cũ. Giữ Swiss/flat: Be Vietnam Pro, một accent indigo, không gradient/glass/emoji-icon. Mọi phase kiểm mobile-first, 44px touch target, không horizontal scroll; mọi chuỗi mới qua i18n VN/EN.

## Trình tự và cổng nghiệm thu

| Phase | Phụ thuộc | Checklist thực thi / bằng chứng đạt |
|---|---|---|
| 1 — nền tảng | — | Tạo SPA độc lập Vite React TS + Tailwind v4 CSS-first, port 5273 strict; tokens/font/theme no-FOUC có persist; VN/EN; shell + 3 route deep-link `/`, `/transcribe`, `/clone` với active nav; primitives có focus/disabled; `mockTtsApi` inject được và fixtures VI/EN/JP. Xác minh ở 375px và desktop, reload theme không nháy, không tràn ngang. |
| 2 — voice | 1 | Lọc ngôn ngữ/model, giới tính/nhóm, search bỏ dấu và reset; skeleton/empty/error demo được; preview audio singleton (đổi card dừng audio cũ); selection store và chip; mobile BottomSheet, desktop panel phải. Bằng chứng: thao tác nhanh nhiều preview không chồng tiếng. |
| 3 — compose TTS | 1, 2 | Editor + `.txt`, counter 1.200/20.000; controls phụ thuộc selected voice; mock buffered/stream progress, result player/download/regenerate; affordance SRT chỉ disabled/mock. Bằng chứng: trạng thái idle/generating/success/error và mobile đều rõ, preview/result không đá nhau. **Sau khi đạt phase 3: bắt buộc chạy vision-fix loop subset shell + TTS core, 375/768/1024/1440 × light/dark; capture → `agy` → sửa finding ≥ major → re-capture/review; hội tụ khi 0 finding ≥ major hoặc dừng cứng sau tối đa 4 vòng và báo finding còn lại.** |
| 4 — ASR | 1 | Mock upload/transcribe/error + fixture word timestamps; chunk cue client-side thật và test cases dài dòng/dấu câu/CPS/CJK; SRT/VTT/TXT preview, Blob download, copy; playback highlight. Bằng chứng: SRT có số + dấu phẩy, VTT có `WEBVTT` + dấu chấm; giới hạn cue đạt test. |
| 5 — cloning | 1, 2 | AuthGate demo; form name/sample + consent bắt buộc (không tick sẵn), progress/error, list/empty/delete confirm; clone feed về TTS selection. Bằng chứng: submit không thể khi thiếu sample/consent; clone hiển thị “Giọng của bạn”; UI nêu rõ mock/consent. |
| 6 — hoàn thiện | 2, 3, 4, 5 | UsageGuide/DonateCard không chặn flow; demo 429/quota/too-long với copy không upsell; sweep i18n, a11y, responsive cho đủ ba khu. Bằng chứng: không hard-code UI string, contrast ≥4.5 ở light/dark, keyboard/focus/reduced-motion, 375/768/1024/1440 và landscape không tràn. |
| 7 — E2E/vision | 6 | Build production rồi preview 4273 strict; capture deterministic (fonts ready, animation tắt) cho state cốt lõi của **cả TTS/ASR/Cloning** × 4 breakpoint × 2 theme; `agy` JSON schema (fallback ai-multimodal); report mỗi vòng có điểm, findings, sửa, verdict và ảnh trước/sau. **Bắt buộc vision-fix loop toàn bộ 3 khu, đúng tiêu chí dừng/4-vòng như checkpoint phase 3; không nới rubric/trần để đạt.** |

## Dependency gates

`1 → {2,4}; 2 → {3,5}; {2,3,4,5} → 6 → 7`. Không bắt đầu phase 4/5 trước foundation. Không đi phase 4–7 nếu checkpoint sau phase 3 chưa hội tụ; nếu đã chạm trần 4 vòng còn finding ≥ major thì dừng và báo user theo plan.

## Quy ước kiểm tra mỗi phase

1. Trước khi chạy, kiểm port 5273 và dừng **chỉ** server frontend stale do workflow này khởi tạo; dùng `strictPort`, không đổi port.
2. Chạy kiểm tra hẹp phù hợp phần vừa thêm (build/typecheck/test); sau đó mở `:5273` để kiểm thủ công các state của phase.
3. Chỉ sửa visual trong vision loop, chạy lại test hẹp vùng ảnh hưởng. Phase 7 chỉ dùng preview production 4273 để capture.

## Lưu ý kế hoạch

Không cần đổi trạng thái plan: cả 7 phase đang pending/todo và chưa có bằng chứng triển khai. Câu "phase 5 vision" trong risk của phase 6 không khớp kế hoạch; cổng vision chính xác là checkpoint sau phase 3 và phase 7.

## Câu hỏi mở

- QR Donate và liên kết BuyMeACoffee thật chưa được cung cấp; phase 6 phải giữ placeholder có nhãn rõ.

**Status:** DONE
**Summary:** Đã kiểm tra plan/repo và lập checklist thực thi 7 phase, dependency gates, scope guard, cùng hai vision loop tối đa 4 vòng.
**Concerns/Blockers:** Không có blocker; chỉ cần báo user nếu checkpoint vision sau phase 3 không hội tụ trong 4 vòng.

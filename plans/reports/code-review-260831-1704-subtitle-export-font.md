# Code review — sửa luồng tạo và xuất phụ đề

## Verdict

**REQUEST CHANGES.** Luồng chính đã sửa đúng các root cause trong plan, nhưng fallback khi thiếu word timestamps chưa đáp ứng contract `line | word` cho văn bản không có khoảng trắng. Đây là đường production có thật vì HTTP adapter cho phép `words` rỗng.

## Stage 1 — Spec compliance

| Yêu cầu | Kết quả | Evidence |
|---|---|---|
| Gỡ sample affordance TTS/transcription | PASS | `compose-panel.tsx` bỏ quick-fill; `audio-drop-zone.tsx` bỏ fetch/nút `mock-sample.mp3`; grep chỉ còn mock adapter, clone flow và fixture nội bộ đúng non-goal. |
| `line` gom nhiều từ/có wrap; `word` một cue/word timestamp | PASS cho timestamps thật; **FAIL fallback** | Hai nhánh tách rõ trong `chunk-cues.ts:55-67`, nhưng finding P1 bên dưới còn vi phạm khi `words=[]` và text không có khoảng trắng. |
| Selector ở TTS và transcription | PASS | `audio-result-card.tsx:88-135`; `subtitle-export-panel.tsx:62-109`. |
| VOICEVOX line native, word ASR | PASS | `use-generate-subtitle.ts:35-62`; unit và functional test bao phủ routing. |
| BOM UTF-8 và MIME theo format | PASS trên code path | `download.ts:6-16`; SRT/VTT/TXT mapping tại `subtitle-export-panel.tsx:34-36`; TTS SRT tại `use-generate-subtitle.ts:64`. |
| Không phá API/public contract | PASS | Không đổi backend request/response; đổi `SubtitleOptions` chỉ có caller nội bộ đã được cập nhật, không còn caller `sentence`. |
| Không ghi đè live-stats | PASS | Pending diff không chạm stats/API live-usage; `UsageStats` trong `api/types.ts` vẫn nguyên. |

## Findings

### [P1 — Important] Fallback thiếu word timestamps hỏng contract với Nhật/CJK/no-space

**File:** `frontend/src/lib/subtitle/chunk-cues.ts:16-24` (kèm `:27-35`, `:55-57`)

`timedWords()` dùng `segment.text.trim().split(/\s+/u)`. Khi backend trả segment Nhật/CJK nhưng không có `words`, toàn bộ câu trở thành một pseudo-word. Hệ quả:

- `word` tạo một cue cho cả segment thay vì từng từ;
- `line` không thể wrap pseudo-word; với token dài hơn `maxCharsPerLine`, `linesFor()` còn tạo `['', longText]`, tức dòng đầu rỗng và dòng sau vẫn overflow;
- đây không phải input giả định: `http-transcribe-api.ts:15` chủ động chấp nhận response không có `words` và trả các segment với `words: []`.

Test fallback hiện tại (`chunk-cues.test.ts:63-77`) chỉ dùng `Xin chào`, nên không bắt regression này. Cần segmentation fallback phù hợp text không có whitespace (ví dụ locale-aware word segmentation) và test tối thiểu cho Japanese/CJK ở cả `line` và `word`; riêng line phải đảm bảo không có dòng rỗng và không vượt wrap limit. Đây là sửa nguyên nhân ở boundary segmentation, không nên vá riêng output renderer.

### [P2 — Minor] Vòng đời Blob URL chưa được xác minh ngoài Chromium

**File:** `frontend/src/lib/download.ts:10-16`

Helper click link rồi revoke Blob URL đồng bộ ngay lập tức. Việc browser đã giữ resource trước khi revoke là engine-dependent; evidence hiện có chỉ nêu Playwright functional/visual và không chứng minh download trên Firefox/WebKit. Nên trì hoãn revoke sang task kế tiếp (và có thể gắn link vào DOM rồi dọn) hoặc thêm browser download smoke cho các engine được support. Không ảnh hưởng bytes/MIME của Blob đã unit-test, nhưng là rủi ro cross-browser của chính đường download mới dùng chung.

## Edge cases và chất lượng

- Concurrency/cancel của TTS subtitle dùng `requestId` + `AbortController`; stale request không tải file hay ghi đè state.
- Retry mới tạo request từ `result/params/options` hiện tại, không tái dùng request lỗi cũ; không thấy regression state contract.
- Các input số mới giữ `text-base md:text-sm`; layout mobile-first và selector có `min-h-11`.
- Hai locale thực có (`en`, `vi`) đều thêm/xóa key tương ứng; không còn dangling key production trong phạm vi review.
- Sample của clone và mock adapter được giữ nguyên đúng constraints.

## Verification evidence

Evidence do controller cung cấp: Vitest **23/23**, production build exit **0**, Playwright functional **8/8**, **40 screenshots**. Tester độc lập xác nhận Vitest 23/23 và preview HTTP 200 nhưng bị dừng trước các gate còn lại. Reviewer không chạy lại gate sau yêu cầu chốt ngay; vì vậy không nâng evidence này thành xác minh độc lập.

## Unresolved questions

- Product muốn fallback `word` cho Japanese/CJK dùng `Intl.Segmenter`, tokenizer backend, hay hạ cấp có thông báo sang `line`?
- Browser support chính thức có gồm Firefox/WebKit không? Nếu có, P2 nên được đưa vào gate trước merge.

**Status:** DONE_WITH_CONCERNS  
**Summary:** Các root cause chính đã được sửa, nhưng fallback thiếu word timestamps còn sai với CJK/no-space nên verdict là REQUEST CHANGES.  
**Concerns/Blockers:** P1 ở `chunk-cues.ts`; P2 là rủi ro download cross-browser chưa được gate hiện tại chứng minh.

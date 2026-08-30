---
type: brainstorm
title: TTS Frontend UI/UX Direction (all_voice)
date: 2026-08-30
status: proposed
skills: [ak-brainstorm, ak-ui-ux-pro-max]
inputs: [backend-scout, market-benchmark, ui-ux-design-database]
next: ak-plan -> /ak:cook
---

# Brainstorm — Lớp UI/UX cho website Text-to-Speech (all_voice)

> Định hướng thiết kế frontend cho một site TTS đơn giản, miễn phí, chia sẻ cộng đồng — bám sát backend thật (VieNeu / Kokoro / VOICEVOX) và benchmark từ các nền tảng TTS phổ biến. Không code ở bước này.

---

## 1. Brainstorm contract

**Outcome.** Một web UI single-page, sạch, hiện đại (không "AI slop"), Vietnamese-first (kèm EN/JP), miễn phí và không cần đăng nhập, cho phép: nhập/upload text → lọc & nghe thử voice → tạo audio → xem tiến độ → nghe + tải kết quả, với vị trí donate nhẹ nhàng và vài mẹo hướng dẫn. Đủ chi tiết để chuyển thẳng sang thiết kế hi-fi hoặc code frontend.

**Constraints.**
- Tiêu thụ **API hiện có nguyên trạng** (không giả định đổi backend): `/v1/voices`, `/v1/voices/{model}/{id}/preview`, `/v1/audio/speech`, `/v1/audio/stream`.
- Tôn trọng **giới hạn tier ANON**: buffered ≤ 1200 ký tự, stream ≤ 20.000 ký tự, 10 req/phút, 50.000 ký tự/ngày, audio ≤ 300s, concurrency thấp (2). UI phải xử lý 429/quota tử tế.
- Deploy khớp topology hiện tại (FastAPI + port-swap): build **static**, phục vụ **same-origin** để tránh CORS.
- KISS: không dashboard enterprise, không wizard nhiều bước, không login cho luồng chính.
- Không dùng thủ pháp "AI slop" (gradient tím, glass neon, hero 3-card Inter generic).

**Non-goals (ngoài phạm vi bản này).**
- UI voice cloning (endpoint cần auth/admin) → để dành khu "nâng cao"/tương lai.
- UI ASR/transcription (speech-to-text) → tính năng riêng, không thuộc site TTS đơn giản.
- Waveform/timeline editor, project/history có tài khoản, metering credit/thanh toán, đa trang dashboard, SSR.

**Acceptance criteria (bằng chứng quan sát được).** Người dùng, **không đăng nhập**, có thể: chọn model (ngôn ngữ/engine) → lọc & **nghe thử** voice → nhập hoặc thả `.txt` trong giới hạn tier → chọn style + tốc độ → bấm tạo → thấy **progress thật** → **nghe inline + tải MP3**, trên cả 3 ngôn ngữ, ở mobile lẫn desktop, với **empty/loading/error/success** được thiết kế rõ ràng và thông báo giới hạn ANON dễ hiểu.

---

## 2. Tóm tắt định hướng sản phẩm

Một "công cụ TTS gọn gàng, đáng tin" chứ không phải "studio". Toàn bộ tác vụ chính gói trong **một màn hình**: bên trái soạn/tạo, bên phải chọn giọng. Vietnamese-first (VieNeu là default), mở rộng sang EN (Kokoro) và JP (VOICEVOX) qua cùng một selector. Miễn phí, không tường đăng nhập — tối ưu cho "chia sẻ anh em dùng". Donate hiện diện rõ nhưng không chặn đường, không modal, không gắn với hạn mức. Nghe thử voice là first-class (backend đã có sẵn `preview_url`). Tiến độ trung thực: stream thì phát dần + progress; buffered thì trạng thái xử lý rõ ràng rồi "xong".

---

## 3. Frontend stack / hướng triển khai đề xuất

**Đề xuất: React + Vite + TypeScript + Tailwind CSS (SPA, build static, same-origin).**

| Lớp | Lựa chọn | Vì sao |
|---|---|---|
| Framework | **React + Vite + TS** | Component rõ ràng, dễ chia nhỏ, dễ mở rộng cho tính năng phức tạp về sau (đúng yêu cầu). Vite = dev nhanh, build static gọn, không cần SSR. |
| Styling | **Tailwind CSS** + design tokens | Kiểm soát grid/spacing/màu chặt → dễ đạt phong cách Swiss/flat, tránh slop. Không phụ thuộc theme lib nặng. |
| Primitives a11y | **Radix UI** (hoặc Headless UI) | Dropdown/slider/dialog/tooltip có sẵn keyboard + ARIA. Tự style để **không** ra "giao diện shadcn generic". |
| Icons | **Lucide** (SVG) | Nhất quán stroke, không dùng emoji làm icon. |
| Data/fetch | **TanStack Query** cho `/v1/voices` (cache, retry); state cục bộ cho editor; 1 hook audio player | Nhẹ, đủ dùng; không cần global store lớn. |
| Streaming | `fetch` + `ReadableStream` → phát dần qua MediaSource (hoặc blob khi xong) | Khai thác `/v1/audio/stream` (gapless MP3) cho văn bản dài. |
| Deploy | Build `dist/` static, mount qua FastAPI `StaticFiles` (thay `web/index.html` hiện tại) hoặc CDN same-origin | Không CORS, hợp topology port-swap. |

**Rationale ngắn cho site miễn phí/cộng đồng.** Backend đã là HTTP API thuần (OpenAI-compatible) + đã có `web/index.html` vanilla để tham chiếu hành vi. SPA static là cách rẻ nhất để host, dễ chia component để anh em cùng đóng góp, và sẵn sàng "gắn thêm" (favorites, history localStorage, cloning nội bộ) mà không phải dựng lại.

**Phương án thay thế (nếu muốn nhẹ hơn nữa):** *SvelteKit* (adapter-static) hoặc *Preact + HTM* — ít JS hơn, nhưng hệ sinh thái/skill routing của repo nghiêng React/TS nên React là mặc định thực dụng. *Giữ nguyên vanilla JS* chỉ hợp nếu quyết không mở rộng — mâu thuẫn với yêu cầu "sẵn sàng tính năng phức tạp về sau", nên loại.

---

## 4. Benchmark ngắn (rút gọn từ agent nghiên cứu)

**Nên học (adopt):**

| Pattern | Vì sao | Nguồn tham chiếu |
|---|---|---|
| 1 trang phẳng, không tường login | Đúng "đơn giản/miễn phí/cộng đồng", bỏ ma sát | TTSMaker |
| Text box + voice picker + nút Tạo = toàn bộ UI chính | KISS, học phí = 0 | TTSMaker |
| Filter chips: ngôn ngữ → nhóm/model → giới tính | Quét nhanh, không cần filter rail studio | ElevenLabs (taxonomy) rút gọn |
| Icon play nhỏ ngay trên voice card, toggle play/pause | Nghe thử không rời trang, rõ đang phát gì | Mọi site |
| Vùng thả file phủ **cùng** textarea (không phải bước riêng) | Một bề mặt nhập | TTSReader/Luvvoice |
| Char counter live gần input | Đặt kỳ vọng về giới hạn độ dài | Free tools |
| Progress bar thật (không spinner trần), nút đổi nhãn khi tạo | "Không bị đơ", phản hồi tức thì | UX 2026 |
| Player inline + nút Download ngay dưới input sau khi tạo | Không điều hướng, khớp mental model | TTSMaker, ElevenLabs demo |
| Link donate nhỏ, không modal, không tiers | Không phiền đúng brief | Donation UX best practice |
| Cố tình thiết kế empty/loading/error có copy thật | UI do AI dựng hay bỏ 3 state này | UX 2026 |

**Nên tránh (anti-pattern):**
- Bắt đăng nhập trước khi dùng (Vbee, Viettel AI) → giết use-case "share cho bạn".
- Vỏ dashboard enterprise / project / sidebar đa trang (Viettel, LOVO, Murf).
- Filter rail 6+ facet đồng thời (PlayHT) → thừa cho 3 ngôn ngữ.
- Bảng pricing/credit nhét chung trang công cụ (ElevenLabs) → mệt vì upsell trong khi ta không bán gì.
- Donate dạng modal/interstitial hoặc gắn với hạn mức.
- Spinner trần không nhãn/% cho tác vụ > ~2s → đọc như "treo".
- "AI slop": gradient tím→hồng, glass neon, hero Inter 3-card generic.
- Waveform/timeline editor (thuộc studio trả phí).

**Ghi chú audience Việt:**
- Người Việt quen lọc theo **vùng miền Bắc/Trung/Nam** (Vbee). `style` của VieNeu (`tu_nhien`/`tin_tuc`/`doc_truyen`) là **trục khác** (kiểu đọc) — nếu voice có metadata vùng miền thì nên đưa thành filter; nếu không, để nguyên style làm secondary control.
- Use-case cộng hưởng: video YouTube/TikTok, **sách nói**, bài giảng/học phát âm tiếng Anh, quảng cáo, hỗ trợ người khiếm thị → nhét 2–3 cái vào copy hướng dẫn cho cụ thể.
- **Chuẩn hoá văn bản tiếng Việt** (số, ngày, tiền, viết tắt, dấu) là điểm dễ đọc sai → thêm khối "Mẹo sử dụng" (collapsible, không modal) khuyên viết số/ngày dạng chuẩn để giảm bug report.

---

## 5. Information Architecture

**Một trang, hai vùng (desktop) / xếp chồng (mobile).**

```
Header  →  Workspace (Compose | Voice)  →  Usage tips  →  Donate  →  Footer
```

- **Header (sticky, mỏng):** logo/tên • badge ngôn ngữ hiện tại • link "Mẹo" • nút "Ủng hộ dự án" • (tùy chọn) theme toggle.
- **Workspace — Compose panel (trái ~60%):** editor text + vùng thả `.txt` + char counter → hàng control (Model/Ngôn ngữ · Style · Tốc độ · Định dạng) → nút **Tạo giọng nói** → **ProgressStatus** → **AudioResultCard**. Chip "Giọng đang chọn" phản chiếu lựa chọn bên phải.
- **Workspace — Voice panel (phải ~40%):** filter bar (ngôn ngữ/model → giới tính/nhóm → search) → lưới **VoiceCard** (tên, tag, nút nghe thử, trạng thái chọn).
- **Usage guide:** khối "Mẹo sử dụng" collapsible (chuẩn hoá text VN + 2–3 use-case).
- **Donate:** một card/link tĩnh, nhẹ, dismissible — không tiers, không chặn.
- **Footer:** giấy phép/nguồn, GitHub, "miễn phí — không watermark", giới hạn tier tóm tắt.

**Ánh xạ backend (IA ↔ API):** Model select ↔ `model` (vieneu/kokoro/voicevox = VI/EN/JP) · Voice grid ↔ `GET /v1/voices?model=` · Nghe thử ↔ `GET /v1/voices/{model}/{id}/preview` · Style ↔ `voice.styles` · Tạo (ngắn) ↔ `POST /v1/audio/speech` · Tạo (dài) ↔ `POST /v1/audio/stream` · Speed ↔ `speed` (0.25–4.0) · Format ↔ `response_format`.

---

## 6. Phân rã component

Ký hiệu state: `idle · loading · empty · error · success · disabled`.

| Component | Vai trò | Dữ liệu nhận (props) | Trạng thái | Hành vi chính |
|---|---|---|---|---|
| **AppShell** | Khung layout, theme, responsive grid | children; theme | idle | Chia 2 vùng ở ≥1024px, stack ở <1024px |
| **Header** | Nhận diện + lối tắt | appName; currentModel; onOpenTips; onDonate | idle | Sticky; badge ngôn ngữ; nút donate không phô trương |
| **ComposePanel** | Vùng làm việc chính | selectedVoice; limits(tier) | idle/loading/error/success | Điều phối editor→controls→generate→progress→result |
| **TextEditor** | Nhập nội dung | value; maxChars; onChange | idle/disabled | Auto-grow; disable khi đang tạo; placeholder = hướng dẫn ngắn |
| **CharCounter** | Đếm ký tự + cảnh báo giới hạn | count; softLimit(1200); hardLimit(20000) | ok/warn/over | Đổi màu gần ngưỡng; báo "sẽ dùng chế độ stream" khi > buffered |
| **FileDropZone** | Nạp `.txt` vào editor | accept=[.txt]; onText | idle/dragover/error | Kéo-thả **đè** textarea → auto-fill; báo lỗi định dạng inline |
| **SynthControls** | Cụm tham số tạo | model; styles; speed; format | idle/disabled | ModelSelect (ngôn ngữ/engine) · StyleSelect (theo voice) · SpeedSlider 0.25–4.0 · FormatSelect (mp3 mặc định) |
| **GenerateButton** | Kích hoạt tạo | disabled; isGenerating | idle/loading/disabled | Nhãn đổi "Tạo giọng nói"→"Đang tạo…"→✓; disable khi rỗng/quá hạn |
| **ProgressStatus** | Phản hồi tiến độ | mode(stream\|buffered); percent?; elapsed | loading/success/error | Stream: bar theo chunk + phát dần; Buffered: bar animate → done; tôn trọng reduced-motion |
| **AudioResultCard** | Kết quả audio | src; format; fileName | success/empty | `<audio>` controls + **Download** + Tạo lại + copy link |
| **VoicePanel** | Chọn giọng | voices; filters; selectedId | loading/empty/error/success | Điều phối filter→grid→preview→select |
| **VoiceFilterBar** | Lọc giọng | languages/models; genders/groups; query | idle | Chips ngôn ngữ→model→giới tính + ô search; reset |
| **VoiceGrid** | Danh sách giọng | voices[]; selectedId | loading(skeleton)/empty/success | Lưới card scannable; virtualize nếu >50 |
| **VoiceCard** | 1 giọng | voice{id,name,model,language,styles}; isSelected; isPreviewing | idle/selected/previewing | Click = chọn; hiện tag ngôn ngữ/giới tính/style |
| **VoicePreviewButton** | Nghe thử | previewUrl; isPreviewing; onToggle | idle/loading/playing | Icon play↔pause; chỉ 1 preview phát tại một thời điểm |
| **SelectedVoiceChip** | Phản chiếu giọng đang chọn (trong Compose) | voice; onClear | idle | Hiện tên+style; trên mobile thay cho việc mở cả 2 panel |
| **UsageGuide** | Mẹo dùng | tips[] | collapsed/expanded | Collapsible; nội dung chuẩn hoá text VN + use-case |
| **DonateCard** | Ủng hộ | method(QR/link); onDismiss | idle/dismissed | Tĩnh, nhẹ; không modal, không tiers |
| **Toast** | Thông báo tạm | type; message | show/hide | aria-live=polite; tự ẩn 3–5s; không cướp focus |
| **ErrorState** | Lỗi cạnh ngữ cảnh | code; message; onRetry | error | Inline gần nút; nêu nguyên nhân + cách khắc phục (429/quota/quá dài) |
| **EmptyState** | Chưa có gì | context(editor\|voices\|result) | empty | Copy hướng dẫn thay vì trắng trơn |
| **LoadingSkeleton** | Chờ tải | shape | loading | Placeholder pulse cho voice grid/result |

---

## 7. User flow

1. **Land** → editor có placeholder hướng dẫn ("Dán văn bản, chọn giọng, bấm Tạo"); voice mặc định = VieNeu Vietnamese `tu_nhien`; voice grid load (skeleton→cards).
2. **Nhập/Upload** → gõ hoặc thả `.txt`; CharCounter cập nhật. Vượt 1200 → tự chuyển sang **chế độ stream** (báo nhẹ), vượt 20.000 → chặn + gợi ý rút gọn (tier ANON).
3. **Chọn giọng** → (tuỳ chọn) lọc theo ngôn ngữ/model/giới tính → **nghe thử** bằng icon play trên card → chọn → SelectedVoiceChip cập nhật; chỉnh Style + Tốc độ.
4. **Tạo** → bấm "Tạo giọng nói" → nút đổi nhãn + ProgressStatus (stream: phát dần + bar; buffered: bar → ✓).
5. **Kết quả** → AudioResultCard hiện inline → Nghe + **Download MP3** + Tạo lại.
6. **Donate (tuỳ chọn)** → nếu thấy hữu ích.

**Nhánh lỗi/giới hạn:** 429 rate-limit → "Thử lại sau vài giây"; vượt quota ngày → giải thích 50k ký tự/ngày; text quá dài cho tier → nêu giới hạn; preview/generate fail → ErrorState + Retry.

---

## 8. Wireframe (text-based)

**Desktop (≥1024px):**
```
┌───────────────────────────────────────────────────────────────────────┐
│  🎙 all_voice        [VI ▾]              Mẹo   ·   ☕ Ủng hộ dự án        │  Header
├──────────────────────────────────────┬────────────────────────────────┤
│  SOẠN & TẠO                           │  CHỌN GIỌNG                     │
│ ┌──────────────────────────────────┐ │  [VI] [EN] [JP]  [Nữ][Nam] 🔍  │  filter chips
│ │ Dán văn bản… (kéo-thả .txt)       │ │ ┌────────────┐ ┌────────────┐  │
│ │                                   │ │ │ ▶ Mai      │ │ ▶ Lan   ✓  │  │  voice cards
│ │                                   │ │ │ VI·Nữ·news │ │ VI·Nữ·natu │  │
│ └──────────────────────────────────┘ │ └────────────┘ └────────────┘  │
│  1180 / 1200 ký tự (buffered)         │ ┌────────────┐ ┌────────────┐  │
│  Model:[VieNeu ▾] Style:[Tự nhiên ▾]  │ │ ▶ Minh     │ │ ▶ Huy      │  │
│  Tốc độ:[——●——] 1.0x  Định dạng:[MP3] │ │ VI·Nam     │ │ VI·Nam     │  │
│  ┌──────────────────────────────┐     │ └────────────┘ └────────────┘  │
│  │      ▶  Tạo giọng nói         │     │                                │
│  └──────────────────────────────┘     │                                │
│  ▓▓▓▓▓▓▓▓░░░░░░  Đang tạo… 60%         │  Giọng đang chọn: Lan (Tự nhiên)│
│  ┌──────────────────────────────┐     │                                │
│  │ ◀◀ ▶ ▬▬▬▬●▬▬ 00:12  ⬇ Tải MP3 │     │                                │
│  └──────────────────────────────┘     │                                │
├──────────────────────────────────────┴────────────────────────────────┤
│  ▸ Mẹo sử dụng: viết số/ngày dạng chuẩn, VD "2026" → "hai không hai sáu"│
│  ☕ Ủng hộ dự án để duy trì server miễn phí   ·   miễn phí, không watermark│  Donate + Footer
└───────────────────────────────────────────────────────────────────────┘
```

**Mobile (<1024px, xếp chồng):**
```
┌───────────────────────────┐
│ 🎙 all_voice   [VI ▾]  ☰   │
├───────────────────────────┤
│ Dán văn bản… (thả .txt)    │
│ ┌───────────────────────┐ │
│ │                       │ │
│ └───────────────────────┘ │
│ 1180/1200 ký tự           │
│ Giọng: [ Lan · Tự nhiên ▾]│ ← chip mở bottom-sheet chọn giọng
│ Style:[Tự nhiên] Tốc độ●  │
│ ┌───────────────────────┐ │
│ │   ▶ Tạo giọng nói      │ │
│ └───────────────────────┘ │
│ ▓▓▓▓▓░░░ Đang tạo… 60%     │
│ ┌───────────────────────┐ │
│ │ ▶ ▬▬●▬▬ 00:12  ⬇ Tải   │ │
│ └───────────────────────┘ │
│ ▸ Mẹo sử dụng             │
│ ☕ Ủng hộ dự án            │
└───────────────────────────┘
   [ Bottom-sheet: filter chips + voice grid + nghe thử ]
```

---

## 9. UI style direction

**Phong cách:** Swiss Modernism / flat editorial — grid 8px chặt, nhiều whitespace, **một** màu nhấn, không gradient/glass. Cảm giác: *gọn gàng, tập trung, đáng tin*, không loè loẹt.

**Color tokens (light):**
| Token | Hex | Dùng cho |
|---|---|---|
| bg | `#F8FAFC` | nền trang |
| surface | `#FFFFFF` | card/panel |
| border | `#E2E8F0` | viền/divider |
| text | `#0F172A` | chữ chính/heading |
| text-muted | `#475569` | chữ phụ |
| **primary** | `#4F46E5` | CTA, active, focus, thanh progress |
| primary-hover | `#4338CA` | hover CTA |
| success | `#059669` | done/hợp lệ |
| warning | `#D97706` | gần giới hạn ký tự |
| danger | `#DC2626` | lỗi/vượt hạn |

*Single-accent indigo* để "Swiss" và ít slop. Muốn nhiều năng lượng hơn: giữ indigo làm brand, CTA đổi amber `#F97316` — nhưng khuyến nghị single-accent cho cohesion. **Dark mode (tuỳ chọn):** bg `#0F172A`, surface `#1E293B`, text `#F1F5F9`, primary `#818CF8`, viền/interaction phải phân biệt được ở cả 2 theme.

**Typography:** **Be Vietnam Pro** (Google Font, thiết kế riêng cho dấu tiếng Việt → đẹp, hiện đại, không "Inter generic") cho UI + heading; body cũng Be Vietnam Pro để nhất quán. Số/counter dùng `font-variant-numeric: tabular-nums`. Scale: 12/14/16/18/20/24/32 (base 16), line-height body 1.6 / heading 1.2, weight 400 body · 500 label · 600–700 heading.

**Spacing & shape:** thang 4/8/12/16/24/32/48. Radius: control 8px · card 12px · icon-button tròn. Elevation **một cấp**: shadow mềm `0 1px 3px rgba(15,23,42,.1)`, ưu tiên phân tách bằng border.

**Motion:** 150–300ms, ease-out vào / ease-in ra. Chỉ animate 1–2 phần tử/khung (progress bar, pulse "đang tạo"). Tôn trọng `prefers-reduced-motion` (tắt pulse, giữ trạng thái đọc được ngay). Không animate width/height — chỉ transform/opacity.

**Icon:** Lucide, stroke 1.5–2px nhất quán, không emoji làm icon cấu trúc.

---

## 10. Các trạng thái UX cần thiết

| Vùng | Empty | Loading | Error | Success |
|---|---|---|---|---|
| **Voice grid** | "Không có giọng khớp bộ lọc" + nút reset | Skeleton cards | "Không tải được danh sách giọng" + Retry | Lưới card + card chọn nổi bật |
| **Nghe thử** | — | Icon → spinner nhỏ | "Không phát được bản nghe thử" (tooltip) | Icon → pause, sóng nhẹ |
| **Editor** | Placeholder hướng dẫn (không trắng trơn) | disable khi đang tạo | Counter đỏ khi vượt hạn + gợi ý | — |
| **Generate/Progress** | Nút disabled khi rỗng | Bar (%/animate) + nhãn "Đang tạo…" | Inline gần nút: 429 "thử lại sau", quota, "quá dài cho tier" + Retry | Bar → ✓, chuyển sang result |
| **Result** | Chưa tạo → vùng gợi ý | (như progress) | "Tạo thất bại" + Tạo lại | Player + Download hiện inline |

**Đặc thù tier ANON cần thiết kế riêng:** thông báo **rate-limit (10/phút)**, **quota ngày (50k ký tự)**, **giới hạn độ dài** (1200 buffered / 20k stream), **audio ≤ 300s** — dùng ngôn từ thân thiện, giải thích vì sao và hướng khắc phục, không dùng giọng "upgrade/mua thêm credit" (sản phẩm không bán gì).

---

## 11. Checklist sẵn sàng chuyển sang thiết kế/code

**Design ready**
- [ ] Chốt màu accent (indigo single-accent vs indigo+amber CTA) và light-only vs light+dark.
- [ ] Nhúng Be Vietnam Pro; định nghĩa type scale + tabular-nums cho counter.
- [ ] Design tokens (color/spacing/radius/shadow/motion) thành biến (CSS vars/Tailwind config).
- [ ] Vẽ hi-fi: Compose, Voice panel, 4 nhóm state (empty/loading/error/success) + màn 429/quota.
- [ ] Chốt cơ chế donate (Momo/QR ngân hàng/Ko-fi/BuyMeACoffee).

**Build ready**
- [ ] Scaffold React+Vite+TS+Tailwind; Radix + Lucide + TanStack Query.
- [ ] Ánh xạ component ↔ endpoint (§5) thành API client typed.
- [ ] Hook audio: preview (single-instance) + player kết quả; chiến lược stream (MediaSource) vs buffered.
- [ ] Logic tier: char limits, auto stream-mode, xử lý 429/quota; đọc `voice.styles` để dựng StyleSelect động.
- [ ] Build static + phục vụ same-origin (thay `web/index.html`); kiểm tra CORS/none.

**Quality gates (từ ak-ui-ux-pro-max)**
- [ ] Contrast ≥ 4.5:1; focus ring rõ; keyboard nav đủ; aria-label cho icon-only.
- [ ] Touch target ≥ 44px; không dựa vào hover; feedback ≤ 100ms.
- [ ] Responsive 375/768/1024/1440; không cuộn ngang; reduced-motion.
- [ ] Không emoji-icon; single elevation; state hover/press/disabled phân biệt.

---

## 12. Câu hỏi chưa chốt (unresolved)

1. **Cơ chế donate** cụ thể (Momo, QR ngân hàng, Ko-fi, BuyMeACoffee)? Ảnh hưởng DonateCard.
2. **Phục vụ frontend** qua FastAPI `StaticFiles` (same-origin, thay `web/index.html`) hay host tách CDN? Ảnh hưởng CORS/deploy.
3. **Default khi load**: mặc định VieNeu Vietnamese `tu_nhien` — đúng ý chứ?
4. **FormatSelect**: lộ cho người dùng phổ thông hay mặc định MP3 và giấu "nâng cao"?
5. **Theme**: light-only cho MVP hay làm luôn light+dark?
6. **Streaming progressive playback** (MediaSource) làm ngay MVP hay tạm buffered-only + progress bar rồi bổ sung sau?
7. **Vùng miền voice VI**: VieNeu có metadata Bắc/Trung/Nam để lọc không? (Nếu có, thêm 1 hàng chip.) — cần xác nhận từ catalog voice.
8. (Minor) 3 chi tiết benchmark chưa verify được do bot-block: cách đặt donate/ad của TTSMaker, layout in-app ElevenLabs/PlayHT pixel-level, màn sau login Vbee/Viettel — nên tự xem trực tiếp nếu cần bản hi-fi sát.

---

## 13. Next step (handoff)

Đây là bản **exploration/định hướng** — không code. Khi bạn chốt các câu hỏi §12, chuyển tiếp:
- **`ak-plan`** → phân phase (scaffold → design tokens → Voice panel → Compose+generate → states/limits → polish/a11y) → **`/ak:cook`** để implement.
- Hoặc dựng **mockup HTML annotated** trước khi plan nếu muốn xem trực quan (`ak:brainstorm --html` / `ak:preview`).

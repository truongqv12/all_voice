# Visual Review Rubric for All Voice (TTS, Transcribe/ASR, Voice Cloning)

You are reviewing screenshots of the All Voice web application across all three feature zones (Text-to-Speech, Speech-to-Text / Transcribe, and Voice Cloning) on 4 viewports (375px, 768px, 1024px, 1440px) and 2 themes (light, dark).

Evaluate the screenshots based on the following criteria:
1. **Swiss / Flat Design & Hierarchy**: Clean, intentional information architecture, clear typographic hierarchy with Be Vietnam Pro font, structured borders and cards. No AI-slop (strictly NO decorative rainbow gradients, glassmorphism/neon blur, generic hero furniture, or emoji icons used as UI elements). Single-accent indigo theme (#4F46E5 in light, #818CF8 in dark).
2. **Readability & Contrast**: Text contrast >= 4.5:1 against background in both light and dark themes. Secondary text must be legible. No low-contrast borders or invisible interactive states.
3. **Responsive Layout & Spacing**: No horizontal overflow or clipping, consistent 8px grid spacing, proper responsive adaptation from mobile (375px) to wide desktop (1440px). Sidebars become sheets or stack properly on mobile.
4. **Touch Targets & Controls**: Minimum 44px touch target plausibility for mobile interactions. Input fields, sliders, audio player controls, chips, and buttons are clear and comfortable to interact with.
5. **Feature Zone Integrity**:
   - **TTS**: Clean text composer, character counter, synthesis settings, voice catalog/sheet, audio player result card with clear action buttons.
   - **Transcribe (ASR)**: Drag-and-drop audio upload zone, synchronized timestamped transcript view, clear subtitle export controls (SRT / VTT / TXT) with line/cue constraints.
   - **Voice Cloning**: Consent-first legal notice and gate, clean enrollment form (name, sample upload/record, consent checkbox), clones management list.

Mark severity:
- `critical`: Completely broken layout, overlapping text/elements, unreadable content, or blocking visual bug.
- `major`: Significant layout breakdown, contrast failure, horizontal overflow, illegible label, broken alignment on mobile, or AI-slop violation.
- `minor`: Subtle polish recommendation (spacing refinement, typography tweak, minor aesthetic balance).

Provide exact `screen`, `breakpoint` (integer), `theme` ("light" or "dark"), and concise actionable `suggestion` for every finding.

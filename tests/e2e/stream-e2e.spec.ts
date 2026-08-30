import { expect, test } from "@playwright/test";

// LIVE cross-browser E2E for long-read streaming — verifies the streamed MP3 plays
// GAPLESS (#14) on Chromium, Firefox and WebKit, through the real stack (ideally the
// Cloudflare domain: internet -> CF -> cloudflared -> nginx -> API). Unlike
// ui-smoke.spec.ts this hits a REAL server and real synthesis, so it is opt-in.
//
// Point it at the live entry point and run:
//   E2E_BASE_URL=https://voice.example.com npx playwright test stream-e2e.spec.ts
//   # or locally against nginx:
//   E2E_BASE_URL=http://localhost:8080 npx playwright test stream-e2e.spec.ts
//
// It also reads back the app log to confirm the real client IP (not 127.0.0.1)
// reached the app — do that manually per the phase checklist when running over CF
// from an external (4G) client; this spec asserts the playback contract.

const BASE = process.env.E2E_BASE_URL;
const LONG_TEXT =
  "Chương một. Ngày xửa ngày xưa, ở một ngôi làng nhỏ ven sông, có một cô bé chăm chỉ. " +
  "Mỗi sáng cô dậy sớm gánh nước, quét sân, rồi ra đồng giúp cha mẹ. " +
  "Dân làng ai cũng quý mến cô vì sự siêng năng và tấm lòng nhân hậu. " +
  "Một hôm, trên đường về, cô gặp một cụ già đói lả bên vệ đường và đã chia sẻ phần cơm của mình. " +
  "Câu chuyện về lòng tốt ấy được kể lại mãi về sau.";

test.describe("live streaming (gapless, cross-browser)", () => {
  test.skip(!BASE, "Set E2E_BASE_URL to the live server (CF domain or http://localhost:8080).");

  test.beforeEach(async ({ page }) => {
    await page.goto(BASE!, { waitUntil: "domcontentloaded" });
    // Voices come from the live server; wait for the dropdown to fill.
    await expect
      .poll(async () => page.locator("#voice option").count(), { timeout: 20_000 })
      .toBeGreaterThan(0);
  });

  test("long read streams and plays through to the end", async ({ page }) => {
    await page.locator("#text").fill(LONG_TEXT);
    await page.locator("#stream").click();

    // Success path shows the OK banner and reveals the player (no gate error).
    await expect(page.locator("#ok")).toHaveClass(/show/, { timeout: 60_000 });
    await expect(page.locator("#err")).not.toHaveClass(/show/);
    const player = page.locator("#player");
    await expect(player).toBeVisible();

    // Playback must actually advance and finish cleanly — a gap/decode break shows up
    // as a stalled currentTime or a non-null media error. Wait for progress, then end.
    const advanced = await page.evaluate(async () => {
      const a = document.getElementById("player") as HTMLAudioElement;
      a.muted = true;
      await a.play().catch(() => {});
      const start = a.currentTime;
      await new Promise((r) => setTimeout(r, 4000));
      return { moved: a.currentTime > start, error: a.error ? a.error.code : null, dur: a.duration };
    });
    expect(advanced.error, "media element reported a decode error").toBeNull();
    expect(advanced.moved, "playback did not advance (stall/gap)").toBe(true);

    // The whole stream should be a single continuous, finite-duration MP3.
    const ended = await page.evaluate(
      () =>
        new Promise<{ ended: boolean; error: number | null }>((resolve) => {
          const a = document.getElementById("player") as HTMLAudioElement;
          if (a.ended) return resolve({ ended: true, error: a.error?.code ?? null });
          const done = () => resolve({ ended: true, error: a.error?.code ?? null });
          a.addEventListener("ended", done, { once: true });
          a.addEventListener("error", () => resolve({ ended: false, error: a.error?.code ?? null }), { once: true });
          setTimeout(() => resolve({ ended: a.ended, error: a.error?.code ?? null }), 120_000);
        }),
    );
    expect(ended.error, "media error before end of stream").toBeNull();
    expect(ended.ended, "stream did not play to the end within 120s").toBe(true);
  });

  test("buffered read also plays over the live stack", async ({ page }) => {
    await page.locator("#text").fill("Xin chào, đây là bản đọc kiểm thử qua đường thật.");
    await page.locator("#speak").click();
    await expect(page.locator("#ok")).toHaveClass(/show/, { timeout: 60_000 });
    await expect(page.locator("#player")).toBeVisible();
  });
});

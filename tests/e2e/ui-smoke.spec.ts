import { expect, test } from "@playwright/test";

// Smoke test for web/index.html — verifies the test UI's wiring end-to-end without
// a live API: /v1/* is mocked in-page. Checks (from the phase success criteria):
// voices dropdown loads, "Đọc" (buffered) plays, "Đọc file dài" (stream) plays,
// and a 429 surfaces as a visible error.

const VOICES = {
  object: "list",
  data: [
    { id: "vieneu-truc-ly", name: "Trúc Ly", model: "vieneu", language: "vi", styles: ["tu_nhien", "doc_truyen"], preview_url: "/v1/voices/vieneu/vieneu-truc-ly/preview" },
    { id: "af_heart", name: "Kokoro Heart", model: "kokoro", language: "en", styles: [], preview_url: "" },
  ],
};

// A few bytes are enough — the UI wraps the response in a Blob URL; the test asserts
// the <audio> gets a blob: src, not that it decodes.
const FAKE_AUDIO = Buffer.from([0xff, 0xf3, 0x00, 0x00, 0x00, 0x00]);

async function mockVoices(page) {
  await page.route("**/v1/voices**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(VOICES) }),
  );
}

test("voices load into the dropdown", async ({ page }) => {
  await mockVoices(page);
  await page.goto("/index.html");
  const voice = page.locator("#voice");
  await expect(voice.locator("option")).toHaveCount(VOICES.data.length);
  await expect(voice.locator("option").first()).toHaveText("Trúc Ly — vieneu (vi)");
  // Selecting a voice with styles populates the style dropdown.
  await expect(page.locator("#style option")).toContainText(["tu_nhien", "doc_truyen"]);
});

test("buffered read (Đọc) calls /v1/audio/speech and plays", async ({ page }) => {
  await mockVoices(page);
  let called = false;
  await page.route("**/v1/audio/speech", async (route) => {
    called = true;
    const body = JSON.parse(route.request().postData() || "{}");
    expect(body.model).toBe("vieneu");
    expect(body.voice).toBe("vieneu-truc-ly");
    expect(body.input.length).toBeGreaterThan(0);
    await route.fulfill({ status: 200, contentType: "audio/mpeg", body: FAKE_AUDIO });
  });

  await page.goto("/index.html");
  await page.locator("#speak").click();

  await expect(page.locator("#ok")).toHaveClass(/show/);
  expect(called).toBe(true);
  const player = page.locator("#player");
  await expect(player).toBeVisible();
  const src = await player.evaluate((el) => (el as HTMLAudioElement).src);
  expect(src).toContain("blob:"); // audio wired to the fetched response
});

test("long read (Đọc file dài) calls /v1/audio/stream and plays", async ({ page }) => {
  await mockVoices(page);
  let called = false;
  await page.route("**/v1/audio/stream", async (route) => {
    called = true;
    await route.fulfill({ status: 200, contentType: "audio/mpeg", body: FAKE_AUDIO });
  });

  await page.goto("/index.html");
  await page.locator("#stream").click();

  await expect(page.locator("#ok")).toHaveClass(/show/);
  expect(called).toBe(true);
  await expect(page.locator("#player")).toBeVisible();
});

test("a 429 from the gate surfaces as a visible error", async ({ page }) => {
  await mockVoices(page);
  await page.route("**/v1/audio/speech", (route) =>
    route.fulfill({
      status: 429,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "vượt hạn mức hôm nay", type: "rate_limit_error", code: "quota_exceeded" } }),
    }),
  );

  await page.goto("/index.html");
  await page.locator("#speak").click();

  const err = page.locator("#err");
  await expect(err).toHaveClass(/show/);
  await expect(err).toContainText("429");
  await expect(page.locator("#ok")).not.toHaveClass(/show/);
});

import { defineConfig, devices } from "@playwright/test";

// The smoke test serves web/index.html statically and mocks /v1/* in-page, so it
// needs no running API/nginx — it runs on any dev machine or CI. `python3 -m
// http.server` gives the page a real http:// origin (relative fetch to /v1 works
// and page.route can intercept it).
const PORT = 8099;

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
  },
  // Cross-browser: the gapless streaming check (#14) must hold on all three engines.
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: {
    command: `python3 -m http.server ${PORT} --directory ../../web`,
    url: `http://127.0.0.1:${PORT}/index.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 20_000,
  },
});

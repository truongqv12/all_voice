// Shared config + helpers for the k6 load scenarios.
//
// k6 is a single standalone binary (no npm). Install: https://k6.io/docs/get-started/installation/
//   # Debian/Ubuntu
//   sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
//   echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
//   sudo apt update && sudo apt install k6
//
// Run a scenario:
//   BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/throughput.js
//
// Target the box through nginx (default :8080), NOT the loopback API directly, so
// the CF-Connecting-IP header is trusted (nginx is the loopback peer) exactly like
// production. Run the abusive scenarios LOCAL / from another LAN machine — never at
// the public CF domain, or Cloudflare will (correctly) treat it as an attack.
//
// Env knobs (all optional): BASE_URL, MODEL, VOICE, API_KEY (set = TRUSTED tier,
// bypasses the gate — leave empty to exercise the anon gate).

export const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8080";
export const MODEL = __ENV.MODEL || "vieneu";
export const VOICE = __ENV.VOICE || "Trúc Ly";
const API_KEY = __ENV.API_KEY || "";

// A random-ish public IP so each VU/iteration can look like a distinct client to the
// per-IP gate. Kept out of private ranges so nothing is filtered as bogon.
export function fakeIp() {
  const o = () => 1 + Math.floor(Math.random() * 254);
  return `${11 + Math.floor(Math.random() * 200)}.${o()}.${o()}.${o()}`;
}

// Headers for a JSON TTS request. `ip` sets CF-Connecting-IP (trusted only on the
// loopback hop, i.e. via nginx). A real API key promotes to the TRUSTED tier.
export function jsonHeaders(ip) {
  const h = { "Content-Type": "application/json" };
  if (ip) h["CF-Connecting-IP"] = ip;
  if (API_KEY) h["Authorization"] = `Bearer ${API_KEY}`;
  return h;
}

// Build a speech body whose `input` is exactly `chars` long (repeated Vietnamese
// text so real synthesis cost scales with the char budget).
export function speechBody(chars, extra = {}) {
  const seed = "Xin chào, đây là một câu kiểm thử tải cho hệ thống đọc văn bản. ";
  let input = "";
  while (input.length < chars) input += seed;
  input = input.slice(0, chars);
  return JSON.stringify({ model: MODEL, input, voice: VOICE, ...extra });
}

export const isTrusted = !!API_KEY;

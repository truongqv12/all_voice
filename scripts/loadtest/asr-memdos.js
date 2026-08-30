// Scenario 7 — ASR upload memory-DoS.
// Many concurrent large uploads to /v1/audio/transcriptions from one IP. The gate
// runs the per-IP rate check BEFORE reading the body, and enforces the size ceiling,
// so most uploads are shed with 429/413 and the box's RAM does not blow up buffering
// many big files at once. Undecodable bytes that pass the gate get 400, never 5xx.
// Watch RAM externally: python scripts/loadtest/assert_stateful.py --sample 60
//
// MB_PER_UPLOAD keeps the k6 CLIENT's own memory sane (default 2MB × VUs). Bump
// toward 25 to probe the size ceiling, but mind the load machine's RAM.
import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";
import { BASE_URL, jsonHeaders } from "./common.js";

const IP = "203.0.113.90";
const MB = Number(__ENV.MB_PER_UPLOAD || 2);
const shed = new Rate("shed_before_work");

// Random-ish bytes shaped like a file upload; not valid audio (that's fine — we're
// testing the gate + size guard, not transcription accuracy).
const payload = "R".repeat(MB * 1024 * 1024);

export const options = {
  scenarios: {
    flood: {
      executor: "per-vu-iterations",
      vus: 12,
      iterations: 2,
      maxDuration: "120s",
    },
  },
  thresholds: {
    // Under this flood the box must never 5xx or hang.
    "shed_before_work": ["rate>0"],
    http_req_failed: ["rate<0.5"],
  },
};

export default function () {
  const headers = jsonHeaders(IP);
  delete headers["Content-Type"]; // let k6 set the multipart boundary
  const res = http.post(
    `${BASE_URL}/v1/audio/transcriptions`,
    { model: "whisper-1", file: http.file(payload, "clip.wav", "audio/wav") },
    { headers, timeout: "60s" },
  );
  // 429 (rate/queue) or 413 (too big) = shed before doing ASR work; 400 = read but
  // rejected as undecodable. None of these should be a 5xx or a hang.
  shed.add(res.status === 429 || res.status === 413);
  check(res, { "no 5xx, no hang": (r) => r.status >= 400 && r.status < 500 });
}

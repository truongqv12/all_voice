// Scenario 1 — legitimate concurrent load.
// N clients POST buffered TTS (~1200 chars) at once. Goal: no OOM, no hang, and the
// event loop stays responsive — /v1/models keeps answering fast WHILE synth runs
// (proves CPU work is off-thread, not blocking the loop). Sample CPU/RAM alongside
// with: python scripts/loadtest/assert_stateful.py --sample 90
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";
import { BASE_URL, fakeIp, jsonHeaders, speechBody } from "./common.js";

const healthLatency = new Trend("health_latency", true);

export const options = {
  scenarios: {
    // Ramp legitimate synth load. Each VU is a distinct IP so the per-IP gate does
    // not throttle them (we're testing throughput, not the rate limit — see rate-limit.js).
    synth: {
      executor: "ramping-vus",
      exec: "synth",
      startVUs: 1,
      stages: [
        { duration: "30s", target: 4 },
        { duration: "1m", target: 8 },
        { duration: "30s", target: 0 },
      ],
    },
    // Independent liveness probe: the API must keep answering during synth.
    health: {
      executor: "constant-arrival-rate",
      exec: "health",
      rate: 2,
      timeUnit: "1s",
      duration: "2m",
      preAllocatedVUs: 2,
    },
  },
  thresholds: {
    // Tune to the box after a first run; these are the drafted acceptance bars.
    http_req_failed: ["rate<0.05"],
    health_latency: ["p(95)<500"], // loop responsive: discovery < 500ms during synth
  },
};

export function synth() {
  const res = http.post(`${BASE_URL}/v1/audio/speech`, speechBody(1200), {
    headers: jsonHeaders(fakeIp()),
    timeout: "120s",
  });
  check(res, {
    "synth 200": (r) => r.status === 200,
    "got audio": (r) => (r.headers["Content-Type"] || "").includes("audio"),
  });
}

export function health() {
  const res = http.get(`${BASE_URL}/v1/models`);
  healthLatency.add(res.timings.duration);
  check(res, { "models 200": (r) => r.status === 200 });
  sleep(0.1);
}

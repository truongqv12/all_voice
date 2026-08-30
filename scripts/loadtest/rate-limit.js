// Scenario 2 — exceed the per-IP rate limit.
// ONE IP fires far more than anon_rate_per_min. Expect: after the burst allowance,
// requests get 429 IMMEDIATELY (not queued/hung) with the OpenAI error envelope.
import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";
import { BASE_URL, jsonHeaders, speechBody } from "./common.js";

const got429 = new Rate("got_429");
const fast429 = new Rate("fast_429");

// One fixed IP for the whole test so the bucket belongs to a single client.
const IP = "203.0.113.77";

export const options = {
  scenarios: {
    burst: {
      executor: "constant-arrival-rate",
      rate: 30, // 30 req/s from one IP — well over a per-minute allowance
      timeUnit: "1s",
      duration: "20s",
      preAllocatedVUs: 20,
      maxVUs: 40,
    },
  },
  thresholds: {
    got_429: ["rate>0.5"], // most requests should be rejected once the bucket drains
    fast_429: ["rate>0.99"], // rejections must be immediate, never a hang
  },
};

export default function () {
  const res = http.post(`${BASE_URL}/v1/audio/speech`, speechBody(200), {
    headers: jsonHeaders(IP),
    timeout: "10s",
  });
  const is429 = res.status === 429;
  got429.add(is429);
  if (is429) {
    fast429.add(res.timings.duration < 1000); // a real rate-limit reject returns at once
    check(res, {
      "429 has OpenAI envelope": (r) => {
        try { return !!JSON.parse(r.body).error.message; } catch (e) { return false; }
      },
    });
  }
}

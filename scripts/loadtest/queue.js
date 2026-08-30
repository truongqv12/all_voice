// Scenario 4 — saturate admission control.
// Many requests from the SAME IP arrive at once, past anon_max_concurrent_per_ip +
// max_queue_waiters. Expect: overflow returns 429 IMMEDIATELY (Overloaded), and NO
// request ever hangs longer than request_timeout_s — the box sheds load, never wedges.
import http from "k6/http";
import { check } from "k6";
import { Rate, Trend } from "k6/metrics";
import { BASE_URL, jsonHeaders, speechBody } from "./common.js";

const IP = "203.0.113.200";

const overloaded = new Rate("overloaded_429");
const waitTime = new Trend("wait_time", true);
const neverHung = new Rate("never_hung");

export const options = {
  scenarios: {
    // A hard simultaneous spike: 40 arrivals in a 1s window from one IP.
    spike: {
      executor: "per-vu-iterations",
      vus: 40,
      iterations: 1,
      maxDuration: "120s",
    },
  },
  thresholds: {
    overloaded_429: ["rate>0"], // some requests must be shed once the queue fills
    never_hung: ["rate>0.99"], // nothing exceeds the server-side timeout ceiling
  },
};

export default function () {
  const res = http.post(`${BASE_URL}/v1/audio/speech`, speechBody(1200), {
    headers: jsonHeaders(IP),
    timeout: "150s",
  });
  waitTime.add(res.timings.duration);
  overloaded.add(res.status === 429);
  // request_timeout_s defaults to 90s; allow slack for synth + transport.
  neverHung.add(res.timings.duration < 140000 && res.status !== 0);
  check(res, { "200 or 429, never 5xx/timeout": (r) => r.status === 200 || r.status === 429 });
}

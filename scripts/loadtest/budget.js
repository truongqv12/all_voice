// Scenario 3 — exhaust the per-IP daily character budget.
// ONE IP pumps characters toward anon_chars_per_day. Once the day's budget is spent
// the IP gets 429 even though the short-term rate bucket has room — proving the gate
// bills by REAL COST (characters), not request count.
//
// Day reset is by UTC date: to verify reset, either wait past 00:00 UTC or clear the
// row —  sqlite3 data/quota.db "DELETE FROM usage WHERE ip='198.51.100.9';"
// (assert_stateful.py can also inspect the row).
import http from "k6/http";
import { check } from "k6";
import { Counter, Rate } from "k6/metrics";
import { BASE_URL, jsonHeaders, speechBody } from "./common.js";

const IP = "198.51.100.9";
const CHARS = Number(__ENV.CHARS_PER_REQ || 1000);

const charsSent = new Counter("chars_sent");
const budget429 = new Rate("budget_429");

export const options = {
  // Serial-ish spend so we can watch the budget cross its ceiling. Small VU count;
  // the point is total characters over time, not concurrency.
  scenarios: {
    spend: {
      executor: "constant-vus",
      vus: 2,
      duration: __ENV.DURATION || "2m",
    },
  },
  thresholds: {
    // By the end of the run the IP should be hitting the daily cap.
    budget_429: ["rate>0"],
  },
};

export default function () {
  const res = http.post(`${BASE_URL}/v1/audio/speech`, speechBody(CHARS), {
    headers: jsonHeaders(IP),
    timeout: "120s",
  });
  if (res.status === 200) charsSent.add(CHARS);
  const is429 = res.status === 429;
  budget429.add(is429);
  check(res, { "200 or 429 (never 5xx)": (r) => r.status === 200 || r.status === 429 });
}

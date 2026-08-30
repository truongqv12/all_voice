// Scenario 10 — soak / endurance.
// Moderate mixed load (buffered + streaming) held for 30–60 min from rotating IPs.
// Goal: no memory leak (the in-memory IP map has a TTL, #9), the result cache stays
// under result_cache_max_mb, no crash-loop. Pair with a long RAM/CPU sample:
//   python scripts/loadtest/assert_stateful.py --sample 3600 --interval 10 --out soak.csv
// and afterwards check: du -sh data/cache  (must stay under RESULT_CACHE_MAX_MB).
import http from "k6/http";
import { check } from "k6";
import { BASE_URL, MODEL, VOICE, fakeIp, jsonHeaders, speechBody } from "./common.js";

export const options = {
  scenarios: {
    steady: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.RATE || 3), // requests/sec — moderate, not a flood
      timeUnit: "1s",
      duration: __ENV.DURATION || "45m",
      preAllocatedVUs: 10,
      maxVUs: 20,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.1"],
  },
};

function longBody() {
  const s = "Ngày hôm nay trời đẹp, chúng tôi cùng nhau đi dạo trong công viên và trò chuyện vui vẻ. ";
  let input = "";
  for (let i = 0; i < 12; i++) input += s;
  return JSON.stringify({ model: MODEL, input, voice: VOICE });
}

export default function () {
  const ip = fakeIp();
  // ~1 in 4 iterations exercises the streaming path; the rest are buffered.
  if (Math.random() < 0.25) {
    const res = http.post(`${BASE_URL}/v1/audio/stream`, longBody(), {
      headers: jsonHeaders(ip),
      timeout: "180s",
    });
    check(res, { "stream ok/limited": (r) => r.status === 200 || r.status === 429 });
  } else {
    // Half the buffered calls reuse a fixed short text so the result cache gets hits.
    const body = Math.random() < 0.5 ? speechBody(300) : speechBody(800);
    const res = http.post(`${BASE_URL}/v1/audio/speech`, body, {
      headers: jsonHeaders(ip),
      timeout: "120s",
    });
    check(res, { "buffered ok/limited": (r) => r.status === 200 || r.status === 429 });
  }
}

// Scenario 6 — too many concurrent streams from one IP.
// ONE IP opens more long-read streams than anon_max_streams_per_ip at once. Expect:
// the excess streams get 429 (stream cap), and RAM stays FLAT — the server yields
// mp3 sentence-by-sentence from a single container, it does not buffer whole files.
// Watch RAM externally: python scripts/loadtest/assert_stateful.py --sample 60
import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";
import { BASE_URL, MODEL, VOICE, jsonHeaders } from "./common.js";

const IP = "203.0.113.150";
const streamRejected = new Rate("stream_429");

// A long multi-sentence passage so each accepted stream stays open a while.
function longBody() {
  const s = "Chương một. Ngày xửa ngày xưa, ở một ngôi làng nhỏ ven sông, có một cô bé rất chăm chỉ. ";
  let input = "";
  for (let i = 0; i < 40; i++) input += s;
  return JSON.stringify({ model: MODEL, input, voice: VOICE });
}

export const options = {
  scenarios: {
    manyStreams: {
      executor: "per-vu-iterations",
      vus: 8, // > anon_max_streams_per_ip (default 2) from one IP
      iterations: 1,
      maxDuration: "180s",
    },
  },
  thresholds: {
    stream_429: ["rate>0"], // streams beyond the cap must be rejected
  },
};

export default function () {
  const res = http.post(`${BASE_URL}/v1/audio/stream`, longBody(), {
    headers: jsonHeaders(IP),
    timeout: "180s",
  });
  streamRejected.add(res.status === 429);
  check(res, {
    "200 or 429": (r) => r.status === 200 || r.status === 429,
    "200s are audio": (r) => r.status !== 200 || (r.headers["Content-Type"] || "").includes("audio"),
  });
}

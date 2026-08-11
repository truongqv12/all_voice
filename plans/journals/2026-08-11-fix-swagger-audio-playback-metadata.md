---
title: Fix Swagger audio playback metadata
date: 2026-08-11
summary: Declare audio responses as binary and decode real containers in E2E tests.
---

# Fix Swagger audio playback metadata

## What happened
Swagger received valid audio/mpeg bytes but displayed 0:00 because the OpenAPI media entries had no binary schema.

## Root cause
The response metadata used empty media-type objects and documented PCM as application/octet-stream although runtime returns audio/pcm. PyAV proved the MP3 payload itself decoded to 2.8 seconds.

## Decision
Declare all six audio media types as OpenAPI binary strings. Keep runtime encoding and endpoint behavior unchanged. Strengthen E2E tests by decoding every container format.

## Verification
Schema test failed before the fix and passed afterward. Full E2E passed 18 tests. Synthetic and API MP3 responses decoded with non-zero samples/duration.

## Next steps
Commit/push when requested, deploy, restart the service, and retry Swagger playback.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

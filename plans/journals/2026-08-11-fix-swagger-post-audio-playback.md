---
title: Fix Swagger POST audio playback
date: 2026-08-11
summary: Render speech POST responses from Blob URLs instead of replaying the endpoint with GET.
---

# Fix Swagger POST audio playback

## What happened
Swagger still displayed audio as 0:00 after binary response schemas were added. The server logs showed a successful POST followed by GET /v1/audio/speech returning 405.

## Root cause
Swagger UI 5's built-in ResponseBody component renders audio with the request URL as the source instead of the response Blob. That works for GET audio resources but cannot replay a POST-only synthesis endpoint. The earlier OpenAPI schema fix made the binary response explicit but did not change this renderer behavior.

## Decision
Serve a customized Swagger UI at /docs. Pin swagger-ui-dist 5.32.6 and wrap only the audio response component so it creates and revokes Blob object URLs from the POST response. Preserve the OpenAI-compatible endpoint, raw audio bytes, OpenAPI schema, Redoc, and non-audio renderers.

The visible application version was bumped to 0.1.1 in package and OpenAPI metadata so deployments can be distinguished directly in the Swagger header and startup log.

## Verification
The regression test failed before the custom docs route and passed afterward. Browser smoke executed speech twice: both POST requests returned 200, both players used blob URLs, durations were 4.920s and 6.672s, and no GET request was sent to /v1/audio/speech. A GET /health response still rendered correctly. Swagger visibly showed all-voice 0.1.1 and OAS 3.1. Full E2E passed 20 tests.

## Next steps
Commit and push when requested, deploy, restart the service, and hard-refresh /docs.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

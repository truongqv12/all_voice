---
title: Fix Swagger bearer authentication
date: 2026-08-11
summary: Model API-key authentication as an OpenAPI Bearer security scheme.
---

# Fix Swagger bearer authentication

## What happened
Swagger exposed `authorization` as a per-operation header parameter. Generated requests could omit it, while runtime required `Authorization: Bearer <key>` and returned 401.

## Root cause
`app.auth.require_api_key` used FastAPI `Header` directly, which documents a normal operation parameter instead of an OpenAPI security scheme.

## Decision
Use `HTTPBearer` with a named `BearerAuth` scheme and keep the existing key validation and OpenAI-style error envelope. `/health` remains public.

## Verification
The OpenAPI regression test failed before the change and passed afterward. The generated schema now contains `BearerAuth`, every `/v1/*` operation references it, and no raw authorization parameter remains. Full E2E passed 17 tests.

## Next steps
Deploy or pull the pushed commit on the server, restart the service, then use Swagger's Authorize button with the API key value.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

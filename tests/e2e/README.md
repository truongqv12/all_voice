# UI smoke test (Playwright)

Verifies the test UI (`web/index.html`) wiring on a dev machine or CI — **not run on
the prod box**. It serves `web/` with `python3 -m http.server` and mocks `/v1/*`
in-page, so no API/nginx needs to be running.

## Run

```bash
cd tests/e2e
npm install
npx playwright install chromium     # first time only
npm test                            # runs ui-smoke.spec.ts
```

## What it checks

- `GET /v1/voices` populates the voice dropdown (and style dropdown per voice).
- "Đọc" posts to `/v1/audio/speech` and the `<audio>` player starts (blob src).
- "Đọc file dài" posts to `/v1/audio/stream` and plays.
- A `429` from the gate shows a visible error and no success message.

## Against a real server (optional)

To smoke the real stack instead of mocks, start the API + nginx (see
`docs/deployment.md`), point a browser at `http://localhost:8080`, and read text
aloud manually. The mocked spec here is the automated gate; the live check is a
one-off during deploy.

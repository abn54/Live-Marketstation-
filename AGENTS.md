# Agent instructions

## Scope

Implement and maintain Assignment 4 Part 4.1: genuine Yahoo live data, a working client/server dashboard, WebSockets, SQLite persistence/replay, and submission evidence. CSV loading is optional class practice. Do not expand into trading, portfolios, order execution, or subsequent assignment parts.

## Development

- Use Node >=24 and npm. Run `npm ci`, `npm run db:init`, and `npm run dev` from the repository root. `npm run build` typechecks and builds; `npm start` serves that production build.
- Keep the SQLite schema in `server/schema.sql`, ingestion in `server/store.js`, provider logic in `server/yahoo.js`, HTTP/WS transport in `server/app.js`, and UI in `client/`.
- Use loopback by default. `.env` and `data/` runtime contents are ignored. Never commit credentials, local databases, WAL files, node_modules, or build outputs. No Yahoo API key is needed.
- Existing records must survive normal restarts. Never reset the working database to fix a UI problem. Use in-memory or isolated temporary databases in tests.

## Invariants

- Never generate or substitute prices in live mode. Recorded data must remain visibly recorded/stale. Do not call cached chart history a live source demonstration.
- Preserve provider provenance, logical identity, source/receipt times, all distinct revisions, duplicate receipt identities, and candle completeness. Receipt order is local receipt ID order; source time must not be rewritten to receipt time.
- Commit an observation and its receipt atomically before broadcasting. Advance the ordering watermark for a newer duplicate. Older request responses cannot overwrite newer accepted heads.
- Keep OHLCV from Yahoo Chart. Do not infer candle volume from Yahoo's daily/rolling volume counters. Do not replace unknown volume with zero or silently fill missing candles.
- Replay is a read-only receipt log with a frozen high watermark and explicit `applied` flags. Keep it independent from live ingestion.
- An outage must stop real upstream collection and retain stored chart history. Demo controls are opt-in and same-origin. Resume must be idempotent; ignore responses from a prior connection generation.
- Update README, design notes, and relevant verification notes when schema, ordering, startup, or provider behavior changes.

## Verification and submission

Run `npm test` and `npm run build` for relevant implementation changes. Tests must cover real behavioral invariants, including duplicates, revisions, out-of-order responses, replay, restart persistence, provider failures, and commit-before-broadcast. Unit/integration tests must not contact Yahoo. `npm run evidence` deliberately contacts Yahoo and briefly interrupts the local demo feed; use it only on a demo-enabled local server.

Use supported browser tools to inspect actual chart rendering, replay, outage/recovery, desktop/mobile layouts, and browser errors. Save evidence from the working app. Do not fabricate verification output or misrepresent synthetic fixtures as live capture. Keep demo video between 30 and 60 seconds and verify the final public links.

Canvas receives only `report.md`; source code and the video remain in the accessible GitHub repository. The report must identify the submitted implementation commit, summarize design/verification/limitations, and link supporting documents and the single video.

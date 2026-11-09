# Agent instructions

## Scope and required stack

Implement Assignment 4 Part 4.1 only: genuine Yahoo live data, Vue 3 frontend, Python FastAPI backend, WebSockets, SQLite persistence/replay, and evidence. The full overview supplied by the user explicitly requires Vue + FastAPI + SQLite on localhost. The previous React/Express implementation is a documented revised approach, not the accepted stack. Do not add indicators, trading, AI model integration, or later assignment parts. CSV loading is ungraded practice; deployment and mobile builds are not required.

## Development

- Use Python >=3.12 and Node >=24. Create `.venv`, install `requirements.txt`, run `npm ci`, `npm run db:init`, and `npm run dev`. Development starts Vite on 3000 and FastAPI on 8000 with same-origin API/WS proxying. `npm run build` typechecks Vue and builds; `npm start` serves the built Vue client directly from FastAPI on 3000.
- Keep SQLite schema in `server/schema.sql`, ingestion in `server/store.py`, provider code in `server/yahoo.py`, FastAPI HTTP/WS routes in `server/main.py`, and Vue components in `client/`. Node scripts are launchers and an independent verification client, not the application backend.
- Default to loopback. Never commit `.venv`, `.env`, SQLite/WAL files, node_modules, or build outputs. Yahoo requires no API credentials. Validate TLS using trusted certificate roots; never disable certificate verification to make a feed work.
- Preserve existing records through migration and restart. Schema v1 is shared with the prior implementation. Semantic payload equality prevents numeric JSON formatting (1 versus 1.0) from creating false migration revisions. Never reset a user's database to fix code; tests use in-memory or isolated temporary databases.

## Data invariants

- Never generate prices in live mode. Recorded/stale data must remain labeled. A refreshing screen or connected socket does not establish current source data.
- Preserve logical provider identity, source/receipt times, immutable revisions, every duplicate receipt, and candle completeness. Keep original source time separate from local receipt order.
- Commit observation, head, and receipt atomically before broadcast. A newer duplicate advances the ordering watermark. Older request responses cannot overwrite newer accepted heads.
- Keep OHLCV/volume from Yahoo Chart. Do not infer minute volume from daily/rolling quote volume; unknown volume is null, reported zero is zero, gaps are not filled.
- Replay is read-only, frozen at a receipt watermark, and applies only records with `applied=true`. Browser replay uses a bounded recent window and a checkpoint computed from applied receipts before that window. Keep the full paginated history available. Live collection remains independent.
- Demo outage controls are opt-in, same-origin, stop real collection, retain history, and ignore prior-generation responses. Reconnect is idempotent.
- Update README, design notes, verification notes, AI-USE.md, and the curated evidence log when behavior, dependencies, tooling, or requirements change.

## Verification and submission

Run `npm test` (pytest behavioral and FastAPI WebSocket tests) and `npm run build`. Run checks from a clean checkout before the submitted version. GitHub Actions runs Python tests and the Vue build on pushes/PRs. Network tests are separate: `npm run evidence` requires a local demo-enabled server, contacts real Yahoo endpoints, and briefly disconnects/reconnects them. Never misrepresent injected failures or synthetic test values as live market observations.

Use supported browser tools for the actual Vue chart, ledger, replay, and outage/recovery. Do not access restricted browser pages. The user will record and speak the single combined demonstration/process video themselves. Keep recording preparation local and untracked. Generate narration or a replacement video only if explicitly requested. Their recording must be 30–60 seconds and identify a design or verification decision. Keep the report video status pending until their actual accessible recording link is supplied. Disclose coding agents, models (only known identifiers), tools, and revised approaches in AI-USE.md. Curated evidence entries must connect intent/prompt excerpt, artifact, test/browser observation, decision, and uncertainty, including at least one failed/revised approach. Redact credentials and private information. Keep full chat exports out of Git.

Canvas receives only `report.md`, with repository URL, submitted implementation commit, single accessible video, completed work, design, verification, limitations, and supporting links. Source and media remain in the public GitHub repository. Keep report links pinned to the submitted implementation/evidence commit; a following report-only commit is acceptable and must be described honestly.

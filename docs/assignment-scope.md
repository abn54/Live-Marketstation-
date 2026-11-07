# Assignment overview → Part 4.1 scope

The user supplied the complete Assignment 4 overview as pasted text after the initial implementation. This document records the applicable requirements without publishing the full course page or private authentication/session content.

| Requirement for this submission | Implementation / evidence |
| --- | --- |
| Vue frontend + FastAPI backend + SQLite on localhost | `client/App.vue`, `server/main.py`, `server/store.py`; running stack asserted by live verification and clean-checkout smoke. React/Express prototype removed from current source and disclosed as a revised approach. |
| Yahoo live streaming and charting-library price/volume visualization | Yahoo pricing WSS + chart OHLCV; FastAPI `/ws` → Vue → TradingView candlesticks/histogram. Current source ages and feed states visible. |
| Identity, source/receipt times, revisions, completion | Immutable schema-v1 observations, receipt audit log, accepted heads, fetched interval-end completeness. Data survives migration/restart. |
| Duplicate/revised/out-of-order handling and replay | Store tests; frozen receipt-order read-only replay; genuine market-closed development recording. |
| Source → backend → chart/database and unavailable-feed evidence | Independent live WebSocket/SQLite comparisons, actual Vue captures, real upstream pause/recovery, combined video. |
| README, agent instructions, design/schema/startup | Repository root README/AGENTS, `docs/design.md`, `server/schema.sql`, pinned dependencies, idempotent initialization, no required credentials. |
| Continue Git/GitHub, browser tests, AI-use/process evidence | Git history; actual local-browser checks; `AI-USE.md`; `docs/evidence-log.md` with revised stack, TLS failure, generated code, tests, and uncertainty; clean checkout and push/PR checks. |
| Canvas packaging | Only `report.md`, with repository URL, submitted implementation/evidence commit, accessible single 30–60 second combined demonstration/process video, results, decisions, limitations, and support links. |

The overview's final-submission disclosure/process practices are established now so they can be maintained through the cumulative parts. The current video includes a verification/design decision; the report and curated log explain the revised approach and relevant generated code. There is no separate process recording or complete chat export.

## Deferred to later parts

Part 4.2 adds two SMAs/crossovers, simulated accounting/execution, and historical backtesting. Part 4.3 adds checked AI decisions, automated simulated actions, a grounded chatbot, chart-image interpretation, and two-way live audio. Part 4.4 is the assigned in-class presentation. None of these later capabilities is claimed complete in Part 4.1. CSV loading is ungraded practice; deployment and a mobile build are not required.

Completeness is already preserved to support later provisional/completed-bar decisions, but there are no indicators or signals in this deliverable. The current backend does not call a model or live-audio provider and needs no model credentials. A responsive layout check is merely a browser check, not a claimed mobile build.

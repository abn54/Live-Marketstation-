# Assignment overview → Parts 4.1–4.2 scope

The user supplied the complete Assignment 4 overview as pasted text after the initial implementation. This document records the applicable requirements without publishing the full course page or private authentication/session content.

| Requirement for this submission | Implementation / evidence |
| --- | --- |
| Vue frontend + FastAPI backend + SQLite on localhost | `client/App.vue`, `server/main.py`, `server/store.py`; running stack asserted by live verification and clean-checkout smoke. React/Express prototype removed from current source and disclosed as a revised approach. |
| Yahoo live streaming and charting-library price/volume visualization | Yahoo pricing WSS + chart OHLCV; FastAPI `/ws` → Vue → TradingView candlesticks/histogram. Current source ages and feed states visible. |
| Identity, source/receipt times, revisions, completion | Immutable schema-v1 observations, receipt audit log, accepted heads, fetched interval-end completeness. Data survives migration/restart. |
| Duplicate/revised/out-of-order handling and replay | Store tests; frozen receipt-order read-only replay; genuine market-closed development recording. |
| Source → backend → chart/database and unavailable-feed evidence | Independent live WebSocket and SQLite comparisons, Vue captures, and real upstream pause and recovery in the student-recorded demonstration. |
| README, agent instructions, design/schema/startup | Repository root README/AGENTS, `docs/design.md`, `server/schema.sql`, pinned dependencies, idempotent initialization, no required credentials. |
| Continue Git/GitHub, browser tests, AI-use/process evidence | Git history; actual local-browser checks; `AI-USE.md`; `docs/evidence-log.md` with revised stack, TLS failure, generated code, tests, and uncertainty; clean checkout and push/PR checks. |
| Canvas packaging | Only `report.md`, with repository URL, submitted implementation/evidence commit, accessible single 30–60 second combined demonstration/process video, results, decisions, limitations, and support links. |

The overview's disclosure and evidence practices apply across the cumulative parts. The student explains the SQLite commit before WebSocket delivery in the combined recording. The report and curated log explain the revised approach and relevant generated code.

## Part 4.2

The user supplied the Part 4.2 submission requirements on November 15. The workstation now plots configurable SMA 9/21 lines and completed-bar crossover arrows. The simulated account applies those signals and persists orders, fills, cash, position, fees, realized and unrealized P&L. Historical backtests consume stored receipts through a frozen watermark. Tests compare Python batch and incremental averages and Vue calculations against pandas, check known account examples, and verify restart and causality rules. [Design and assumptions](part-4-2-design.md) · [Verification](part-4-2-verification.md)

## Deferred to later parts

Part 4.3 adds checked AI decisions, automated actions that incorporate those decisions, a grounded chatbot, chart-image interpretation, and two-way live audio. Part 4.4 is the assigned in-class presentation. CSV loading is ungraded practice. Deployment and mobile builds are outside the requested scope.

Part 4.2's signals use persisted completed candles. Part 4.3 will introduce model and live-audio providers.

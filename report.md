# IST 402 — Assignment 4, Part 4.1

**Market Data and the Dashboard**  
**Student:** abn54  
**Date:** November 7, 2026

- **GitHub repository:** [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-) — public.
- **Submitted implementation and evidence:** [`020950785a75f4e8d092203108a375f9387d667f`](https://github.com/abn54/Live-Marketstation-/commit/020950785a75f4e8d092203108a375f9387d667f). This report is distributed separately; all implementation/evidence links below are pinned to that commit.
- **Short video:** [Download/play the 45-second narrated MP4](https://raw.githubusercontent.com/abn54/Live-Marketstation-/020950785a75f4e8d092203108a375f9387d667f/evidence/part-4-1-demo.mp4) — public, no university or repository login required. [Transcript](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/demo-transcript.md).

## Completed

Marketstation is a working React/TypeScript client and Node/Express server with TradingView Lightweight Charts. It connects to Yahoo Finance's actual pricing WebSocket for live quotes and obtains one-minute OHLCV from Yahoo's Chart endpoint every 15 seconds. The server commits observations to SQLite before pushing them through its own WebSocket to the dashboard. Updating candlesticks and corresponding volume share a UTC axis. BTC-USD, ETH-USD, SPY, and AAPL are selectable.

The dashboard exposes the provider, separate quote/candle ages, receipt age, channel status, source timestamps, forming/completed candles, and persistent storage counters. Closed US equities are marked stale while cryptocurrency can stream on weekends. No generated prices or CSV files substitute for the live source demonstration.

SQLite retains observations and their revisions, every normalized receipt including duplicates, accepted current heads, and feed transitions. The observation ledger exposes receipt identity, source/receipt times, revision number, and disposition. Recorded playback supports play/pause, seeking, restart, and receipt-per-second speed, remains labeled **RECORDED REPLAY**, and does not write observations back into storage.

The outage control terminates the real upstream WebSocket, aborts in-flight HTTP requests, and suspends collection. Both channels become unavailable, data ages increase, counts stop growing, and the existing chart remains. Reconnection resumes genuine Yahoo collection. This control is opt-in and disabled by default.

## Design decisions

**Preserve provenance and ordering.** A logical candle identity consists of source, kind, symbol, interval, and UTC minute start. Immutable observations preserve provider time, first receipt time, payload, and local revision; a separate receipt log preserves each arrival. Chart request start time orders snapshots because Yahoo does not provide a reliable candle revision timestamp. It is explicitly a local ordering token, not a claimed provider timestamp.

| Case | Behavior |
| --- | --- |
| Duplicate | Add a receipt referencing existing content; do not create a false revision or double volume. A newer duplicate advances the ordering watermark. |
| Revised candle | Append an immutable revision, retain prior content, and update the accepted head if request order permits. A newer return to an earlier value remains a legitimate revision. |
| Out-of-order response | Preserve differing older content as superseded; do not overwrite a newer accepted snapshot. Late older minutes are stored under their own identities and sorted by source time. |
| Candle completion | Persist completeness as content. Finalize conservatively after a later minute is observed; an older partial cannot reopen the completed head. |

**Keep candle volume authoritative.** Candles use Yahoo's reported OHLCV rather than estimating minute volume from a daily/rolling quote counter. Missing volume remains null; reported zero stays zero. Live quote price and the most recent candle close may differ between chart refreshes, with their times shown separately.

**Replay what was observed.** Read-only replay freezes a receipt watermark and folds accepted updates in original receipt order. Duplicates and superseded revisions remain inspectable. A genuine captured BTC recording supports development when the market is closed; the live demonstration and verification use actual Yahoo network traffic.

## Verification

| Check | Result and evidence |
| --- | --- |
| Automated behavioral tests | **25 passed, 0 failed.** Covers duplicates, revisions, reversions, late/out-of-order data, completion, atomic validation, disk persistence after reopening, protocol decoding, HTTP 429, in-flight outages, idempotent reconnect, replay pagination, and commit-before-broadcast. [Actual output](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/test-results.txt) · [tests](https://github.com/abn54/Live-Marketstation-/tree/020950785a75f4e8d092203108a375f9387d667f/tests). |
| Production build | TypeScript checking and Vite build passed. [Build output](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/build-results.txt). |
| Genuine live data path | **11 checks passed.** A real client WebSocket received Yahoo quote/candle observations whose IDs, times, and values matched an independent read-only SQLite connection. [Structured evidence](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/live-verification.json). |
| Outage/recovery | Collection stopped without invented records, stored candles remained available, and real Yahoo collection resumed. [Outage screenshot](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/feed-unavailable.jpg) and the video demonstrate the condition. |
| Replay correctness | **11,728 BTC receipts** up to a frozen watermark reconstructed all **360 displayed candles** exactly, including observation IDs, closes, volumes, and completeness. Replay did not change the observation count. [Evidence](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/live-verification.json). |
| Browser and video | Desktop/mobile rendering, closed-market stale labeling, playback, seeking, speed, and refresh recovery passed; no production console errors were observed. The MP4 is **45.000 seconds**, H.264 with AAC narration, and fully decoded successfully. [Browser QA](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/browser-qa.json) · [video metadata](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/evidence/video-metadata.json). |

At the recorded live recovery checkpoint, SQLite contained **3,461 observations, 104 revisions, 31,629 receipts, and 28,168 duplicate receipts**. These are captured live counts, not constants displayed by the UI. Out-of-order behavior was tested deterministically; the live source capture did not happen to produce an out-of-order response.

The video shows live updates (00–12s), receipt/revision history (12–17s), the data path (17–22s), unavailable upstream feeds with retained data (22–30s), recovery (30–35s), and recorded replay (35–45s). It is an edited capture of actual app screenshots at two per second with synthesized narration; pauses between scenes were removed. No market values, chart pixels, counters, or status indicators were fabricated.

## Supporting documentation and startup

- [README and startup/database initialization](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/README.md): Node >=24; `npm ci`, `npm run db:init`, and `npm run dev`, then open `http://127.0.0.1:3000`. Initialization is idempotent and startup also creates a missing database. No API keys or credentials are required; local environment/database files are ignored by Git.
- [Agent instructions](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/AGENTS.md): scope, development commands, data invariants, testing, and submission rules.
- [Design notes and SQLite schema explanation](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/docs/design.md) · [schema SQL](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/server/schema.sql).
- [Detailed verification, evidence links, and limitations](https://github.com/abn54/Live-Marketstation-/blob/020950785a75f4e8d092203108a375f9387d667f/docs/verification.md).

## Remaining limitations

Yahoo's unofficial public feed can be delayed, unavailable, or rate limited. Quotes stream upstream, while candles are polled at 15-second intervals. Candle completion is conservative and does not use a full exchange calendar. Recent polls overlap three minutes; older provider corrections need a full backfill. SQLite has no automatic retention policy, the chart displays 360 bars, and browser replay is bounded to 200,000 receipts per symbol. This is a local single-user workstation; public server deployment, trading, later assignment parts, and CSV practice are outside this deliverable.

The linked Canvas overview required university authentication and could not be independently read; packaging follows the Part 4.1 submission requirements provided with the task. **Only this `report.md` is intended for Canvas. Source code and the single video remain in the linked public repository.**

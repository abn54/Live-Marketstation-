# Verification and evidence

Verified November 7, 2026 on Node v26.7.0, using the production build and real Yahoo Finance connections. The application requires Node >=24. Quotes and candles in the screenshots, recording, and live verification were received from Yahoo; there is no generated-price fallback.

## Results

| Verification | Result | Evidence |
| --- | --- | --- |
| Behavioral unit/integration tests | **25 passed, 0 failed** | [Actual test output](../evidence/test-results.txt), [test source](../tests/) |
| TypeScript and production build | **Passed** | [Build output](../evidence/build-results.txt) |
| Live source → backend → client WS → SQLite | **11 checks passed** | [Structured verification](../evidence/live-verification.json), [run output](../evidence/live-run-results.txt), [repeatable script](../scripts/capture-evidence.js) |
| Browser interaction and layout | **Passed** | [Browser QA](../evidence/browser-qa.json), [desktop](../evidence/live-dashboard.jpg), [mobile](../evidence/mobile-dashboard.jpg) |
| Outage and recovery | **Passed** | [Unavailable feed](../evidence/feed-unavailable.jpg), live verification, video |
| Closed-market freshness | **Passed** | [SPY correctly labeled stale](../evidence/market-closed.jpg) |
| Recorded playback and seek | **Passed** | [Replay screenshot](../evidence/recorded-replay.jpg), browser QA, live replay reconstruction |
| Genuine recording import to separate disk database | **Passed; integrity `ok`** | [Import smoke output](../evidence/import-results.txt), [recording](../evidence/btc-recording.json) |
| Video duration, audio, and decoding | **45.000 seconds; H.264 + AAC; full decode passed** | [Video](../evidence/part-4-1-demo.mp4), [ffprobe metadata](../evidence/video-metadata.json) |

The final live verification began at **2026-11-07 19:11:56 UTC (2:11:56 PM Eastern)**. At its recovery checkpoint SQLite contained **3,461 immutable observations, 104 revisions, 31,629 receipts, 28,168 duplicate receipts, and 3,088 current candles** across the four symbols. Counts continue changing while the app runs; these are captured checkpoints, not hardcoded UI values. The live capture did not happen to receive an out-of-order request response; that behavior is explicitly exercised in deterministic tests.

The script obtained genuine quotes and candle receipts through an actual browser-facing WebSocket, then looked up their observation IDs directly through an independent read-only SQLite connection and compared logical identities, provider timestamps, and price/close values. This establishes the data path without relying on a screenshot alone. The browser screenshots and video demonstrate actual TradingView candlestick and volume rendering from those endpoints.

During a deliberate real upstream disconnection, both feed channels were unavailable, no market observations were generated, and stored candles remained retrievable. Recovery restored Yahoo streaming and chart fetching. SQLite `PRAGMA integrity_check` returned `ok`.

Replay read **11,728 BTC receipts** up to a frozen global receipt watermark of **31,611** and reconstructed the current **360 displayed candles**, including their observation IDs, close, volume, and completeness, exactly. Reading replay did not change the observation count.

## Meaningful test coverage

The tests use in-memory or isolated temporary SQLite databases and local real client/server sockets. They do not contact Yahoo or the working database.

- Exact duplicates preserve one observation and multiple receipt identities. Payload property order cannot cause false revisions.
- Changed OHLCV creates immutable revisions. A newer return to an earlier payload is a genuine revision.
- An older request response is retained as superseded and cannot replace a newer head. A newer duplicate advances the request watermark, preventing a slow older response from overwriting it.
- An older minute is inserted in chronological order; a late older quote cannot move the latest price backward.
- Candle completion is a persisted revision, and an older partial cannot reopen it.
- Invalid batches cannot partially commit; missing volume remains null.
- Receipt-order replay preserves original receipt timestamps/order, includes duplicates and superseded records, and honors a frozen high watermark.
- A disk database survives close/reopen with valid records and integrity.
- The Yahoo envelope/protobuf decoder and candle normalizer are exercised, including the appended unaligned last-price row.
- HTTP 429 becomes unavailable, retains existing data, and recovers. An outage during an in-flight HTTP request cannot leak new data or a healthy status.
- The upstream socket commits before `onData`; closure shows retry status. Repeated reconnection is idempotent.
- HTTP input validation, same-origin/disabled fault controls, snapshot delivery, persisted WebSocket updates, REST retrieval, and replay are exercised end to end.

## Short video

[Download/play the single 45-second narrated demo](../evidence/part-4-1-demo.mp4). [Transcript](../evidence/demo-transcript.md).

| Time | Demonstration |
| --- | --- |
| 00–12s | Actual Yahoo streaming prices, updating one-minute OHLCV, feed age/status, and storage counters. |
| 12–17s | Receipt identities, source/receipt times, duplicate arrivals, and candle revisions in the ledger. |
| 17–22s | Source → SQLite commit → server WebSocket → chart data path. |
| 22–30s | Real upstream connections stopped; both channels unavailable; chart retained. |
| 30–35s | Actual Yahoo collection resumes. |
| 35–45s | Clearly labeled recorded SQLite playback and replay controls. |

The video is an edited capture of the real app at two browser screenshots per second, encoded at 24 fps, with local synthesized narration. It removes pauses between segments, so the UTC clock can jump between scenes. Market values, chart pixels, receipt counts, and statuses are genuine, unmodified UI captures. The video is 1,517,788 bytes and includes an audio track. `scripts/render-demo.py` documents the assembly; generating a new video requires a fresh set of supported-browser captures.

## Browser checks

The desktop layout was inspected at 1440 × 1080. The mobile viewport was 390 × 844; document width remained 390, the chart rendered, and the table's horizontal scroll stayed within the table. Play/pause, speed selection, seeking to both ends, switching symbols, returning to live mode, and persisted snapshot restoration after refresh were exercised. Production console errors since 19:05 UTC: **none**. A prior development-only HMR warning was resolved by keeping the React root stable across module refreshes.

## Verification boundaries and remaining limits

- Yahoo is an unofficial public feed with no freshness/availability guarantee. Candles refresh through HTTP polling, not a tick-level bar builder. Yahoo data can be delayed, sparse, zero-volume, revised, or rate limited.
- The newest candle conservatively remains incomplete until a later minute appears. There is no exchange-session finalization calendar; completion does not promise immunity from later corrections.
- After the one-day bootstrap, three-minute overlap polling catches recent corrections. Older corrections require another full backfill. Missing candles are not filled.
- SQLite retains the full log without automatic compaction. The chart shows 360 candles; browser replay is capped at 200,000 receipts per symbol. Playback uses receipts/second rather than original wall-clock cadence.
- This is a local, single-user application. The repository and video are shareable; an internet-facing running server, authentication, trading, CSV practice, and later assignment parts are outside scope.
- The linked Canvas overview redirected to university authentication and was not independently readable. Browser interaction was subsequently stopped on a restricted page. Submission packaging follows the detailed Part 4.1 requirements supplied in the request: **only `report.md` is uploaded to Canvas**, with repository, commit, one 30–60 second video, and supporting links.

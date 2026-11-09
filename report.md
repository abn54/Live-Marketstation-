# IST 402 — Assignment 4, Part 4.1

**Market Data and the Dashboard**

**Student identifier:** abn54 · **Date:** November 9, 2026

- **Public repository:** [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-).
- **Implementation and evidence commit:** [`3b5bb029c2d0d2fa29ec1e711133e470882f088c`](https://github.com/abn54/Live-Marketstation-/commit/3b5bb029c2d0d2fa29ec1e711133e470882f088c). Supporting links are pinned to this version. The later report commit records that pin and the status of my recording.
- **Student-recorded video:** Recording/link pending. I will record and narrate one 30–60 second demonstration. [Word-for-word script and screen actions for recording](https://github.com/abn54/Live-Marketstation-/blob/6c30eb92c0d4a901350f93ed9c621932e7770341/docs/part-4-1-speaking-script.md). Replace this entry with the accessible video link before Canvas submission.
- **AI/tool disclosure:** [AI-USE.md](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/AI-USE.md) · **Curated process evidence:** [evidence log](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/docs/evidence-log.md).

## Completed

Marketstation uses the overview's required **Vue 3 frontend, Python FastAPI backend, and SQLite database on localhost**. TradingView Lightweight Charts renders updating one-minute candlesticks and corresponding volume. Yahoo Finance's actual pricing WebSocket supplies streaming quotes; its Chart endpoint supplies OHLCV every 15 seconds. FastAPI commits observations to SQLite before broadcasting them over its client WebSocket to Vue. BTC-USD, ETH-USD, SPY, and AAPL are selectable.

The dashboard displays provider, source times, quote/candle/receipt ages, separate feed states, forming/completed candles, and storage counters. Live status requires a genuine pricing message for the selected symbol in the current server session and fresh source timestamps; cached data or an open socket alone is insufficient. Closed equities remain stale while crypto can stream on weekends.

SQLite preserves logical identities, immutable revisions, every normalized receipt, accepted current heads, and feed transitions. The ledger exposes receipt and observation IDs, source and receipt times, revisions, disposition, and candle completeness. Read-only playback opens a recent receipt window with an as-of checkpoint and supports pause, restart, seeking, and speed. **RECORDED REPLAY** identifies playback while live collection continues in the background. The paginated API can retrieve the full history.

The opt-in outage control beside the chart stops Yahoo socket and HTTP collection. Both channels become unavailable, counts stop growing, source ages increase, and the chart retains committed data. After reconnect, the live badge requires a fresh pricing message for the selected symbol on the new Yahoo connection. Controls are disabled by default and restricted to the same origin.

## Design decisions

| Concern | Implemented rule |
| --- | --- |
| Identity and timing | Candle identity is source/kind/symbol/interval/UTC minute start. Preserve provider time separately from local receipt time and order chart snapshots by request start time, a local ordering token rather than a claimed provider revision timestamp. |
| Duplicate | Add a distinct receipt referencing existing content, without double volume or a false revision. A newer duplicate advances the ordering watermark. |
| Revised / out-of-order | Append changed content immutably. Apply newer/equal-order revisions; retain older differing responses as superseded without replacing the accepted head. A newer return to an old value is a legitimate revision. |
| Completeness | A fetched candle is complete if its minute ended by request start time. A closed market's final minute can complete without waiting for a new bar. An older partial cannot reopen a newer completed head. Completeness is persisted with the observation, not invented by a replay/UI timer. |
| Volume and replay | Use Yahoo's reported OHLCV and preserve null when volume is missing. The browser starts from a saved checkpoint, freezes a receipt watermark, and applies accepted records in original receipt order. Replay is read-only. |

The relevant generated code is [MarketStore._ingest_one](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/server/store.py): duplicate equality reuses the immutable observation but still upserts a newer `heads.ordering_time`. This prevents a slow differing response from an older request overwriting a newer unchanged fetch. [The store tests](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/tests/test_store.py) exercise that sequence, revisions/reversions, superseded arrivals, completion, persistence, and replay reconstruction.

## Revised approach and process evidence

The initial short Part 4.1 excerpt did not state a framework requirement, and the linked overview required university authentication. The first React/Express prototype therefore failed the explicit stack requirement supplied later in the pasted overview. It was replaced with Vue/FastAPI while retaining schema v1, original row IDs, immutable payloads, revisions, and receipts. [Preservation evidence](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/migration-preservation.json) compares all original columns of previously captured rows and confirms integrity. The Python store compares decoded payloads so numeric JSON formatting (`1` versus `1.0`) does not create false migration revisions.

An actual Python pricing-socket TLS failure reported a missing trusted issuer while chart HTTP requests succeeded. [The adapter](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/server/yahoo.py) now uses certifi's trusted CA roots with certificate and hostname verification still enabled. Regression tests check the SSL settings, and separate live evidence confirms Yahoo messages arrive. The initial Python test pass also exposed socket-shutdown cancellation and a retry-status timing assumption; lifecycle cleanup and event-based waiting corrected them. The final-candle rule was revised after the overview clarified interval-end semantics, with a regression test for an ended final bar. [The curated log](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/docs/evidence-log.md) connects instruction excerpts, failures, generated artifacts, checks, decisions, and uncertainty. Full chats, credentials, and private browser content are excluded.

[AI-USE.md](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/AI-USE.md) discloses Codex, the known model-family information and unavailable exact identifier, tools, revised framework choice, and the generated narration that was withdrawn at my request. The final recording will use my own voice. It does not claim the student independently authored or mastered every generated line. Part 4.1 calls no AI model/chat/vision/live-audio service and requires no model credentials.

## Verification

| Check | Observed result |
| --- | --- |
| Python/FastAPI tests | **30 passed, 0 failed.** Covers duplicates, revisions, out-of-order arrivals, the replay checkpoint, persistence across restarts, final-bar completion, protocol decoding, HTTP 429, in-flight outages, TLS, reconnect, validation, and commit-before-broadcast. [Actual output](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/test-results.txt) · [tests](https://github.com/abn54/Live-Marketstation-/tree/3b5bb029c2d0d2fa29ec1e711133e470882f088c/tests). |
| Vue build | Typechecking and production build passed. [Output](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/build-results.txt). |
| Genuine live path | **13 checks passed** on November 9. The independent client received a fresh Yahoo quote and an applied candle over FastAPI's WebSocket and matched them to SQLite records. It also checked real outage and recovery, replay, and database integrity. [Current live evidence](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/demo-live-verification.json). |
| Exact replay | **40,159 BTC receipts** through a frozen watermark reproduced all **360 displayed candles**, including IDs, closes, volume, and completeness. Replay made no observation writes. [Evidence](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/demo-live-verification.json). |
| Fresh checkout | **Passed** in 31.03 seconds at source commit `31c69e0`. A new clone completed locked installs, 30 tests, the Vue build, isolated recording import, and production HTTP and WebSocket checks. [Source commit](https://github.com/abn54/Live-Marketstation-/commit/31c69e001ee6f68f56526d458332f79ee80aa1d8) · [redacted results](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/clean-checkout.json). |
| GitHub checks | The workflow runs tests, the Vue build, and isolated recording import on pushes. [Workflow runs](https://github.com/abn54/Live-Marketstation-/actions) · [workflow](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/.github/workflows/checks.yml). |
| Browser | The updated production app showed live candles and volume, a readable ledger at 556 CSS pixels, and replay with restart, pause, and seeking. The intentional outage retained the chart and reconnect delivered a fresh quote. The earlier browser run also checked development proxying, symbol changes, and closed-equity freshness. [Recording rehearsal](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/demo-readiness.json) · [earlier browser QA](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/evidence/browser-qa.json). |

At the November 9 recovery checkpoint, the verification database held **56,193 observations, 14,002 revisions, 135,691 receipts, and 79,498 duplicate receipts**. Naturally out-of-order responses did not occur in this capture. Automated tests inject them to verify how the store responds.

The generated narrated demo has been withdrawn. I will record one 30–60 second combined demonstration/process video using my own voice, showing live chart/volume and feed health, receipt/revision history, SQLite/WebSocket delivery, replay, unavailable feed and recovery, and a design/verification decision. The speaking script is preparation, not a completed recording. **The actual accessible video link must be added before this report is submitted.** No separate process recording is required.

## Supporting documents and startup

[README](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/README.md) documents Python >=3.12 and Node >=24 setup: create `.venv`, install `requirements.txt`, run `npm ci`, `npm run db:init`, then `npm run dev` and open `http://127.0.0.1:3000`. Development proxies to FastAPI on 8000; `npm run build` and `npm start` serve the built Vue app directly from FastAPI. Initialization is idempotent and restart retains records. No credentials are required or exposed; runtime environment/database files are ignored.

[Agent instructions](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/AGENTS.md) · [Design/data flow/schema explanation](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/docs/design.md) · [Schema SQL](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/server/schema.sql) · [Overview-to-scope mapping](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/docs/assignment-scope.md) · [Detailed verification/limits](https://github.com/abn54/Live-Marketstation-/blob/3b5bb029c2d0d2fa29ec1e711133e470882f088c/docs/verification.md).

## Remaining limitations and submission

Yahoo can lag, stop, revise data, or rate limit access. Quotes stream upstream and the server polls candles every 15 seconds. Candle completion records that the interval had ended at fetch time. Three-minute overlap polling may miss older corrections until another backfill. SQLite retains the full log without automatic retention. The chart loads up to 360 bars, and the browser replays up to 800 recent receipts at receipts per second. Older receipts are available through the paginated API.

This is **Part 4.1 only**. Indicators, simulated trading/accounting, backtesting, AI decisions/chat/vision/live audio, and the presentation are later parts. Deployment and a mobile build are not required; the responsive check is only a browser layout check. The full pasted overview has now been applied. **Upload only this `report.md` to Canvas. Source and supporting evidence remain in the public repository. My recording link is still required before submission. Canvas upload has not been performed.**

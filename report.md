# IST 402 — Assignment 4, Part 4.1

**Market Data and the Dashboard**

**Student identifier:** abn54 · **Date:** November 7, 2026

- **Public repository:** [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-).
- **Submitted implementation and evidence:** [`3661d28d37434d82d2ecb4174c7b431ae7e6b550`](https://github.com/abn54/Live-Marketstation-/commit/3661d28d37434d82d2ecb4174c7b431ae7e6b550). Links below are pinned to this version; the report is added in a following documentation-only commit.
- **Student-recorded video:** Recording/link pending. I will record and narrate my own single 30–60 second demonstration. [Speaking script and screen actions](https://github.com/abn54/Live-Marketstation-/blob/main/docs/part-4-1-speaking-script.md). Add the actual accessible video link before Canvas submission.
- **AI/tool disclosure:** [AI-USE.md](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/AI-USE.md) · **Curated process evidence:** [evidence log](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/docs/evidence-log.md).

## Completed

Marketstation uses the overview's required **Vue 3 frontend, Python FastAPI backend, and SQLite database on localhost**. TradingView Lightweight Charts renders updating one-minute candlesticks and corresponding volume. Yahoo Finance's actual pricing WebSocket supplies streaming quotes; its Chart endpoint supplies OHLCV every 15 seconds. FastAPI commits observations to SQLite before broadcasting them over its client WebSocket to Vue. BTC-USD, ETH-USD, SPY, and AAPL are selectable.

The dashboard displays provider, source times, quote/candle/receipt ages, separate feed states, forming/completed candles, and storage counters. Live status requires a genuine pricing message for the selected symbol in the current server session and fresh source timestamps; cached data or an open socket alone is insufficient. Closed equities remain stale while crypto can stream on weekends.

SQLite preserves logical identities, immutable revisions, every normalized receipt, accepted current heads, and feed transitions. The ledger exposes identity, source/receipt times, revisions, and disposition. Read-only recorded playback supports pause/play, restart, seeking, and speed, remains labeled **RECORDED REPLAY**, and stays separate from background live collection. The genuine recording supports development without a live market; no generated prices or CSV practice substitute for live evidence.

The opt-in outage control stops real upstream socket/HTTP collection and polling. Both channels become unavailable, counts stop growing, source ages increase, and the chart retains committed data. Reconnection resumes genuine Yahoo collection. Controls are disabled by default and restricted to the same origin.

## Design decisions

| Concern | Implemented rule |
| --- | --- |
| Identity and timing | Candle identity is source/kind/symbol/interval/UTC minute start. Preserve provider time separately from local receipt time and order chart snapshots by request start time, a local ordering token rather than a claimed provider revision timestamp. |
| Duplicate | Add a distinct receipt referencing existing content, without double volume or a false revision. A newer duplicate advances the ordering watermark. |
| Revised / out-of-order | Append changed content immutably. Apply newer/equal-order revisions; retain older differing responses as superseded without replacing the accepted head. A newer return to an old value is a legitimate revision. |
| Completeness | A fetched candle is complete if its minute ended by request start time. A closed market's final minute can complete without waiting for a new bar. An older partial cannot reopen a newer completed head. Completeness is persisted with the observation, not invented by a replay/UI timer. |
| Volume and replay | Use Yahoo's reported OHLCV, not daily/rolling quote-volume differences. Missing volume remains null. Replay freezes a receipt watermark and applies accepted records in original receipt order without writing them back. |

The relevant generated code is [MarketStore._ingest_one](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/server/store.py): duplicate equality reuses the immutable observation but still upserts a newer `heads.ordering_time`. This prevents a slow differing response from an older request overwriting a newer unchanged fetch. [The store tests](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/tests/test_store.py) exercise that sequence, revisions/reversions, superseded arrivals, completion, persistence, and replay reconstruction.

## Revised approach and process evidence

The initial short Part 4.1 excerpt did not state a framework requirement, and the linked overview required university authentication. The first React/Express prototype therefore failed the explicit stack requirement supplied later in the pasted overview. It was replaced with Vue/FastAPI while retaining schema v1, original row IDs, immutable payloads, revisions, and receipts. [Preservation evidence](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/migration-preservation.json) compares all original columns of previously captured rows and confirms integrity. The Python store compares decoded payloads so numeric JSON formatting (`1` versus `1.0`) does not create false migration revisions.

An actual Python pricing-socket TLS failure reported a missing trusted issuer while chart HTTP requests succeeded. [The adapter](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/server/yahoo.py) now uses certifi's trusted CA roots with certificate and hostname verification still enabled. Regression tests check the SSL settings, and separate live evidence confirms Yahoo messages arrive. The initial Python test pass also exposed socket-shutdown cancellation and a retry-status timing assumption; lifecycle cleanup and event-based waiting corrected them. The final-candle rule was revised after the overview clarified interval-end semantics, with a regression test for an ended final bar. [The curated log](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/docs/evidence-log.md) connects instruction excerpts, failures, generated artifacts, checks, decisions, and uncertainty. Full chats, credentials, and private browser content are excluded.

[AI-USE.md](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/AI-USE.md) discloses Codex, the known model-family information and unavailable exact identifier, tools, revised framework choice, and the generated narration that was withdrawn at my request. The final recording will use my own voice. It does not claim the student independently authored or mastered every generated line. Part 4.1 calls no AI model/chat/vision/live-audio service and requires no model credentials.

## Verification

| Check | Observed result |
| --- | --- |
| Python/FastAPI tests | **29 passed, 0 failed.** [Actual output](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/test-results.txt) · [tests](https://github.com/abn54/Live-Marketstation-/tree/3661d28d37434d82d2ecb4174c7b431ae7e6b550/tests). Includes duplicates, revisions, out-of-order protection, replay, restart persistence, final-bar completion, protocol decoding, HTTP 429, in-flight outages, TLS settings, idempotent reconnect, validation, and commit-before-broadcast. |
| Vue build | Typechecking and production build passed. [Output](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/build-results.txt). |
| Genuine live path | **13 checks passed**: required running stack, fresh Yahoo quote and applied candle update over an actual client WebSocket, independent SQLite identity/time/value comparisons, real outage/recovery, replay, and integrity. [Structured evidence](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/live-verification.json). |
| Exact replay | **12,444 BTC receipts** through a frozen watermark reproduced all **360 displayed candles**, including IDs, closes, volume, and completeness; replay made no observation writes. [Evidence](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/live-verification.json). |
| Fresh checkout | **Passed** in 31.61 seconds at [candidate `5f0a4ba`](https://github.com/abn54/Live-Marketstation-/commit/5f0a4bae6aab21faae3ceb5acd8df3f5056017ef). A new clone had no `.venv`, node_modules, `.env`, dist, or database; locked installs, 29 tests, Vue build, isolated recording import, and actual production HTTP/WebSocket access succeeded. Application source is unchanged in the submitted evidence commit. [Redacted results](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/clean-checkout.json). |
| GitHub push checks | **Succeeded** for the submitted implementation commit. [Actual Actions run](https://github.com/abn54/Live-Marketstation-/actions/runs/42408386881) · [workflow](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/.github/workflows/checks.yml). |
| Browser | Development proxy and production rendering, chart/volume, symbols, outage/recovery, closed-equity stale/completed state, replay/seek/speed, and refresh passed. No production console errors were observed. [Browser QA](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/evidence/browser-qa.json). |

At the recorded live recovery checkpoint, SQLite held **4,259 observations, 318 revisions, 33,893 receipts, and 29,634 duplicate receipts**. These are captured live counts, not UI constants. Naturally out-of-order responses did not occur during that capture; deterministic injected tests establish that behavior separately from actual provider availability.

The generated narrated demo has been withdrawn. I will record one 30–60 second combined demonstration/process video using my own voice, showing live chart/volume and feed health, receipt/revision history, SQLite/WebSocket delivery, replay, unavailable feed and recovery, and a design/verification decision. The speaking script is preparation, not a completed recording. **The actual accessible video link must be added before this report is submitted.** No separate process recording is required.

## Supporting documents and startup

[README](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/README.md) documents Python >=3.12 and Node >=24 setup: create `.venv`, install `requirements.txt`, run `npm ci`, `npm run db:init`, then `npm run dev` and open `http://127.0.0.1:3000`. Development proxies to FastAPI on 8000; `npm run build` and `npm start` serve the built Vue app directly from FastAPI. Initialization is idempotent and restart retains records. No credentials are required or exposed; runtime environment/database files are ignored.

[Agent instructions](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/AGENTS.md) · [Design/data flow/schema explanation](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/docs/design.md) · [Schema SQL](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/server/schema.sql) · [Overview-to-scope mapping](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/docs/assignment-scope.md) · [Detailed verification/limits](https://github.com/abn54/Live-Marketstation-/blob/3661d28d37434d82d2ecb4174c7b431ae7e6b550/docs/verification.md).

## Remaining limitations and submission

Yahoo's unofficial public endpoints can lag, stop, revise data, or rate limit access. Quotes stream upstream; candles are HTTP-polled every 15 seconds and are not a complete trade tape. Completion means interval end at fetch time, not provider-certified finality. Three-minute overlap polling may miss older corrections until another full backfill. Gaps are not filled. SQLite has no automatic retention policy; the chart shows 360 bars, and browser replay is bounded to 200,000 receipts per symbol at receipts/second rather than original wall-clock cadence.

This is **Part 4.1 only**. Indicators, simulated trading/accounting, backtesting, AI decisions/chat/vision/live audio, and the presentation are later parts. Deployment and a mobile build are not required; the responsive check is only a browser layout check. The full pasted overview has now been applied. **Upload only this `report.md` to Canvas. Source and supporting evidence remain in the public repository. My recording link is still required before submission. Canvas upload has not been performed.**

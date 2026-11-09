# Verification and evidence — required Vue/FastAPI stack

Verified November 7, 2026 with Vue 3, Python 3.12, FastAPI, and disk-backed SQLite. Locked dependency versions are in `requirements.txt` and `package-lock.json`. Node >=24 is frontend/launcher tooling and an independent evidence client; it is not the application backend. The earlier React/Express prototype is a disclosed revised approach in Git history.

## Results

| Verification | Result | Evidence |
| --- | --- | --- |
| Python behavioral and FastAPI integration tests | **30 passed, 0 failed** | [Actual pytest output](../evidence/test-results.txt), [tests](../tests/) |
| Vue typecheck and production build | **Passed** | [Build output](../evidence/build-results.txt) |
| Actual Yahoo → FastAPI WS → independent client → SQLite | **13 checks passed** | [Structured live verification](../evidence/live-verification.json), [run output](../evidence/live-run-results.txt), [repeatable client](../scripts/capture-evidence.js) |
| Existing-record preservation across migration | **Original immutable samples unchanged; schema v1; integrity `ok`** | [Preservation comparisons](../evidence/migration-preservation.json) |
| Vue browser functionality and layout | **Passed** | [Browser QA](../evidence/browser-qa.json), [desktop](../evidence/live-dashboard.jpg), [responsive layout](../evidence/mobile-dashboard.jpg) |
| Real upstream outage/recovery | **Passed** | [Unavailable feed](../evidence/feed-unavailable.jpg), live verification |
| Closed-market freshness and final-bar completeness | **Passed** | [SPY stale but completed interval](../evidence/market-closed.jpg), ended-final-minute regression test |
| Recorded playback/seek | **Passed** | [Replay screenshot](../evidence/recorded-replay.jpg), browser QA, exact replay reconstruction in live verification |
| November 9 recording rehearsal | **Passed** on the updated production app | [Live chart, narrow ledger, replay, outage and recovery](../evidence/demo-readiness.json) |
| Genuine recording import to isolated disk database | **Passed; integrity `ok`** | [Import smoke output](../evidence/import-results.txt), [recording](../evidence/btc-recording.json) |
| Fresh-clone install/test/build/import and production HTTP/WS | **Passed** (29 tests; required stack; isolated database) | [Redacted clean-checkout results](../evidence/clean-checkout.json) |
| Student-recorded demonstration/process video | **Recording/link pending**; generated demo withdrawn at user request | [Speaking script and screen actions](part-4-1-speaking-script.md) |

## Live evidence boundaries

The final live verification began at **2026-11-07 19:48:18 UTC (2:48:18 PM Eastern)**. At its recovery checkpoint SQLite held **4,259 observations, 318 revisions, 33,893 receipts, 29,634 duplicate receipts, and 3,160 accepted candles**. These are actual captured counts, not hardcoded UI values. Captures from different times naturally have different counts/prices.

The independent client asserts the running **Vue 3 / FastAPI / SQLite** stack, receives a genuine fresh Yahoo quote and an **applied candle update** through a real network WebSocket, and checks the quote's source timestamp. It queries the same observation IDs through an independent read-only SQLite connection and compares provider identity/time and quote/candle values. This establishes persistence-before-broadcast without relying on a screenshot alone. Vue/TradingView rendering is separately established by actual browser captures.

During the deliberate real upstream pause, both channels became unavailable, the observation count stopped growing, and existing candles stayed queryable. Actual Yahoo collection resumed after reconnection. Replay folded **12,444 BTC receipts** through the frozen global receipt watermark **33,876**, reconstructing all **360 displayed candles** exactly (IDs, closes, volume, completeness) without writes. SQLite integrity was `ok`.

No naturally out-of-order response happened during this capture. Out-of-order arrivals, malformed messages, HTTP 429, and timing races are tested with explicitly injected inputs. Those checks establish deterministic application behavior, not external provider availability or complete exchange coverage.

## Test coverage and revised approaches

Tests use in-memory/temporary databases and local FastAPI WebSocket clients, not the user's database or external Yahoo endpoints. They verify:

- Duplicate identity versus receipt identity; property-order and cross-language numeric JSON equality; changed revisions; genuine newer reversions.
- Superseded older responses, newer-duplicate watermark protection, older-minute/source-time quote ordering, and exact receipt-order replay reconstruction.
- Atomic rejection, nullable volume, persisted completion revisions, late partial protection, disk close/reopen, frozen replay pagination, and read-only replay.
- Protobuf decoding, preservation of aligned OHLCV over appended last-price rows, current-minute incompleteness, and an ended final minute completing without a later bar.
- HTTP 429 retention/recovery; in-flight outage isolation; commit-before-callback; verified TLS/hostname settings; retry state; idempotent reconnect; both channels unavailable during pause.
- FastAPI parameter/body validation, disabled/same-origin fault controls, rejected cross-origin sockets, real ASGI snapshot/update delivery, REST/SQLite/replay agreement, and lifecycle cleanup.

The [curated log](evidence-log.md) connects instructions, generated code, observations, revisions, decisions, and uncertainty. It documents the framework mismatch, Python TLS certificate-store failure, first test failures (cancellation/retry timing), and the closed-final-bar completeness correction. [AI-USE.md](../AI-USE.md) discloses the coding agent, known/unknown model details, tooling and the withdrawn generated narration. [Selected first-run failures](../evidence/migration-first-run.txt) are retained separately from final passing results.

## Clean checkout and push checks

Run `.venv/bin/python -m scripts.verify_clean_checkout` after committing a candidate. It creates a **fresh Git clone with `--no-local`**, confirms ignored runtime files are absent, creates a new Python environment, installs locked dependencies, runs `npm ci`, tests and the Vue build, initializes/imports an isolated database, and starts a real production FastAPI server to check HTTP and WebSocket snapshot/replay access. It records the exact tested source commit and redacted command results in [clean-checkout.json](../evidence/clean-checkout.json). This check does not claim live Yahoo availability; live-provider evidence is separate above.

The clean checkout passed in **31.61 seconds** at source commit `5f0a4bae6aab21faae3ceb5acd8df3f5056017ef`: all five ignored runtime paths were absent, nine command stages succeeded, 29 tests and the Vue build passed, and a real production FastAPI HTTP/WebSocket smoke returned the required stack with 360 retrievable candles and recorded replay. The final implementation/evidence commit adds this result and documentation; application source remains unchanged from that tested candidate. [GitHub Actions](../.github/workflows/checks.yml) runs Python tests, Vue typechecking/build, and isolated recording import on every push/PR. Configured checks are not described as remotely passed unless an actual successful run is observed; the report distinguishes the observed remote status.

## Student-recorded video pending

The user will speak and record the demonstration themselves. The generated narrated MP4, transcript, media metadata, and assembly script have been removed from the current submission. Earlier generation/verification remains disclosed in AI-USE.md and Git history, but is not evidence of a completed student recording.

[The speaking script](part-4-1-speaking-script.md) provides approximately 120 written words and screen actions for a 50–60 second take: live data/volume/source ages; receipt/revision history; SQLite-before-WebSocket delivery; replay; actual outage/recovery; one failure/verification decision; and limitations. Record one video between 30 seconds and one minute. No separate full coding-session recording is required.

Add the student's actual accessible link to report.md before submitting. There is currently no replacement video link, so the video portion of submission packaging is incomplete. Other application/test/browser/clean-checkout evidence above remains valid.

## Browser and remaining limits

Both development proxying and the production Vue build served by FastAPI were exercised. Browser checks covered chart/volume, symbols, data path/ledger, actual outage/recovery, playback/pause/speed/seek, returning to live, refresh restoration, and stale equities with completed last intervals. Desktop was 1440×1080; the optional 390×844 responsive check had document width 390. No production console errors were observed after the recorded production reload. This is a browser layout check, not a mobile build.

Yahoo can be delayed, sparse, revised, unavailable, or rate limited. Candles are polled every 15 seconds. Completion records whether the interval had ended when the server fetched it. After the one-day bootstrap, three-minute overlap polling may miss older corrections until another full backfill. SQLite retains the receipt log without automatic retention. The chart loads up to 360 bars. Browser replay plays up to 800 recent receipts from a saved checkpoint at receipts per second. The full log is available through the paginated API.

This is Part 4.1 only: no indicators, trading, account results, model/chat/vision/live-audio integration, deployment, or mobile build is claimed. The full overview was supplied by the user, resolving the earlier authentication/readability gap. Canvas upload remains a student action; **only `report.md`** is uploaded, linking public source/commit, support documents, and the single combined video.

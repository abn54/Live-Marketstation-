# Verification and evidence — required Vue/FastAPI stack

Verified November 7, 2026 with Vue 3, Python 3.12, FastAPI, and disk-backed SQLite. Locked dependency versions are in `requirements.txt` and `package-lock.json`. Node >=24 is frontend/launcher tooling and an independent evidence client; it is not the application backend. The earlier React/Express prototype is a disclosed revised approach in Git history.

## Results

| Verification | Result | Evidence |
| --- | --- | --- |
| Python behavioral and FastAPI integration tests | **29 passed, 0 failed** | [Actual pytest output](../evidence/test-results.txt), [tests](../tests/) |
| Vue typecheck and production build | **Passed** | [Build output](../evidence/build-results.txt) |
| Actual Yahoo → FastAPI WS → independent client → SQLite | **13 checks passed** | [Structured live verification](../evidence/live-verification.json), [run output](../evidence/live-run-results.txt), [repeatable client](../scripts/capture-evidence.js) |
| Existing-record preservation across migration | **Original immutable samples unchanged; schema v1; integrity `ok`** | [Preservation comparisons](../evidence/migration-preservation.json) |
| Vue browser functionality and layout | **Passed** | [Browser QA](../evidence/browser-qa.json), [desktop](../evidence/live-dashboard.jpg), [responsive layout](../evidence/mobile-dashboard.jpg) |
| Real upstream outage/recovery | **Passed** | [Unavailable feed](../evidence/feed-unavailable.jpg), live verification, video |
| Closed-market freshness and final-bar completeness | **Passed** | [SPY stale but completed interval](../evidence/market-closed.jpg), ended-final-minute regression test |
| Recorded playback/seek | **Passed** | [Replay screenshot](../evidence/recorded-replay.jpg), browser QA, exact replay reconstruction in live verification |
| Genuine recording import to isolated disk database | **Passed; integrity `ok`** | [Import smoke output](../evidence/import-results.txt), [recording](../evidence/btc-recording.json) |
| Single combined demonstration/process video | **52.000 seconds; H.264 + AAC; complete decode passed** | [Video](../evidence/part-4-1-demo.mp4), [metadata](../evidence/video-metadata.json), [transcript](../evidence/demo-transcript.md) |

## Live evidence boundaries

The final live verification began at **2026-11-07 19:48:18 UTC (2:48:18 PM Eastern)**. At its recovery checkpoint SQLite held **4,259 observations, 318 revisions, 33,893 receipts, 29,634 duplicate receipts, and 3,160 accepted candles**. These are actual captured counts, not hardcoded UI values. Captures from different times naturally have different counts/prices.

The independent client asserts the running **Vue 3 / FastAPI / SQLite** stack, receives a genuine fresh Yahoo quote and an **applied candle update** through a real network WebSocket, and checks the quote's source timestamp. It queries the same observation IDs through an independent read-only SQLite connection and compares provider identity/time and quote/candle values. This establishes persistence-before-broadcast without relying on a screenshot alone. Vue/TradingView rendering is separately established by actual browser captures and the video.

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

The [curated log](evidence-log.md) connects instructions, generated code, observations, revisions, decisions, and uncertainty. It documents the framework mismatch, Python TLS certificate-store failure, first test failures (cancellation/retry timing), and the closed-final-bar completeness correction. [AI-USE.md](../AI-USE.md) discloses the coding agent, known/unknown model details, tooling, and synthesized narration. [Selected first-run failures](../evidence/migration-first-run.txt) are retained separately from final passing results.

## Clean checkout and push checks

Run `.venv/bin/python -m scripts.verify_clean_checkout` after committing a candidate. It creates a **fresh Git clone with `--no-local`**, confirms ignored runtime files are absent, creates a new Python environment, installs locked dependencies, runs `npm ci`, tests and the Vue build, initializes/imports an isolated database, and starts a real production FastAPI server to check HTTP and WebSocket snapshot/replay access. It records the exact tested source commit and redacted command results in [clean-checkout.json](../evidence/clean-checkout.json). This check does not claim live Yahoo availability; live-provider evidence is separate above.

The final report records the completed clean-checkout result and identifies its tested source commit. [GitHub Actions](../.github/workflows/checks.yml) runs Python tests, Vue typechecking/build, and isolated recording import on every push/PR. Configured checks are not described as remotely passed unless an actual successful run is observed; the report distinguishes the observed remote status.

## Combined 52-second video

| Time | Working application / process evidence |
| --- | --- |
| 00–10s | Actual Yahoo quotes, updating candles/volume, source ages/status, and Vue/FastAPI/SQLite label. |
| 10–16s | Receipt identity, times, revisions, duplicates, completeness. |
| 16–24s | Yahoo → SQLite → FastAPI WS → Vue chart, with narration identifying commit-before-broadcast and duplicate-watermark verification decisions. |
| 24–32s | Real upstream channels disconnected; both unavailable; stored chart retained. |
| 32–38s | Reconnection and waiting for genuine fresh pricing messages before live status. |
| 38–52s | Recorded playback, pause, seeking to the end, restart at a different speed. |

The footage is an edited capture of the actual required-stack app at two screenshots/second, encoded at 24 fps. Source values, chart content, counts, and feed states are genuine UI captures. Pauses between scenes are removed, so the UTC clock can jump. Narration is synthesized using macOS Samantha, not the student's voice. FFprobe confirms 52 seconds and H.264/AAC; a complete decode also succeeds. The video is **1,879,218 bytes**. No separate process recording is submitted.

## Browser and remaining limits

Both development proxying and the production Vue build served by FastAPI were exercised. Browser checks covered chart/volume, symbols, data path/ledger, actual outage/recovery, playback/pause/speed/seek, returning to live, refresh restoration, and stale equities with completed last intervals. Desktop was 1440×1080; the optional 390×844 responsive check had document width 390. No production console errors were observed after the recorded production reload. This is a browser layout check, not a mobile build.

Yahoo is unofficial and can be delayed, sparse, revised, unavailable, or rate limited. Candles are polled every 15 seconds; pricing messages are not a complete trade tape. Completion means the interval had ended at fetch time, not provider-certified finality. After the one-day bootstrap, three-minute overlap polling may miss older corrections until another full backfill. Gaps are not filled. SQLite has no automatic retention policy; the chart shows 360 bars and browser replay is bounded to 200,000 receipts per symbol. Playback speed is receipts/second rather than original wall-clock cadence.

This is Part 4.1 only: no indicators, trading, account results, model/chat/vision/live-audio integration, deployment, or mobile build is claimed. The full overview was supplied by the user, resolving the earlier authentication/readability gap. Canvas upload remains a student action; **only `report.md`** is uploaded, linking public source/commit, support documents, and the single combined video.

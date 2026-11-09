# Verification and evidence — required Vue/FastAPI stack

Verified November 7 and rechecked November 9, 2026 with Vue 3, Python 3.12, FastAPI, and disk-backed SQLite. Locked dependency versions are in `requirements.txt` and `package-lock.json`. Node >=24 runs frontend tooling, the launcher, and an independent evidence client. The earlier React/Express prototype is a disclosed revised approach in Git history.

## Results

| Verification | Result | Evidence |
| --- | --- | --- |
| Python behavioral and FastAPI integration tests | **30 passed, 0 failed** | [Actual pytest output](../evidence/test-results.txt), [tests](../tests/) |
| Vue typecheck and production build | **Passed** | [Build output](../evidence/build-results.txt) |
| Actual Yahoo → FastAPI WS → independent client → SQLite | **13 checks passed** on November 9 | [Current live check](../evidence/demo-live-verification.json), [November 7 check](../evidence/live-verification.json), [repeatable client](../scripts/capture-evidence.js) |
| Existing-record preservation across migration | **Original immutable samples unchanged; schema v1; integrity `ok`** | [Preservation comparisons](../evidence/migration-preservation.json) |
| Vue browser functionality and layout | **Passed** | [Browser QA](../evidence/browser-qa.json), [desktop](../evidence/live-dashboard.jpg), [responsive layout](../evidence/mobile-dashboard.jpg) |
| Real upstream outage/recovery | **Passed** | [Unavailable feed](../evidence/feed-unavailable.jpg), live verification |
| Closed-market freshness and final-bar completeness | **Passed** | [SPY stale but completed interval](../evidence/market-closed.jpg), ended-final-minute regression test |
| Recorded playback/seek | **Passed** | [Replay screenshot](../evidence/recorded-replay.jpg), browser QA, exact replay reconstruction in live verification |
| November 9 recording rehearsal | **Passed** on the updated production app | [Live chart, narrow ledger, replay, outage and recovery](../evidence/demo-readiness.json) |
| Genuine recording import to isolated disk database | **Passed; integrity `ok`** | [Import smoke output](../evidence/import-results.txt), [recording](../evidence/btc-recording.json) |
| Fresh-clone install/test/build/import and production HTTP/WS | **Passed**, including 30 tests and isolated SQLite | [Redacted clean-checkout results](../evidence/clean-checkout.json) |
| Student-recorded demonstration/process video | **58.92 seconds**, original student narration and screen recording | [Submission report](../report.md) |

## Live evidence boundaries

The November 9 live verification used the updated app on an isolated local server with a copy of the existing SQLite history. It collected genuine new Yahoo quotes and candles and passed all 13 checks. The independent client replayed **40,159 BTC receipts** and exactly reconstructed the **360 persisted chart candles** during the outage. The [November 7 run](../evidence/live-verification.json) provides earlier evidence and the basis for the bundled replay recording.

The independent client asserts the running **Vue 3 / FastAPI / SQLite** stack, receives a genuine fresh Yahoo quote and an **applied candle update** through a real network WebSocket, and checks the quote's source timestamp. It queries the same observation IDs through an independent read-only SQLite connection and compares provider identity/time and quote/candle values. This establishes persistence-before-broadcast without relying on a screenshot alone. Vue/TradingView rendering is separately established by actual browser captures.

During the deliberate upstream pause, both channels became unavailable, the observation count stopped growing, and existing candles stayed queryable. Yahoo collection resumed after reconnection. Replay reconstructed candle IDs, closes, volume, and completeness without writing records. SQLite integrity was `ok`.

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

The clean checkout passed in **31.03 seconds** at source commit `31c69e001ee6f68f56526d458332f79ee80aa1d8`. All five ignored runtime paths were absent, nine command stages succeeded, 30 tests and the Vue build passed, and the production HTTP/WebSocket smoke returned the required stack with 360 retrievable candles and recorded replay. The following commit captures these results. [GitHub Actions](../.github/workflows/checks.yml) runs Python tests, Vue typechecking and build, and isolated recording import on pushes and pull requests.

## Student-recorded video

The submitted clip was cut from the student's 3:14 Kaltura recording. The first section shows the live quote, candle chart, and feed health. The ledger and data pipeline follow around 0:17 and 0:24, including the student's explanation of committing updates before broadcast. Replay appears around 0:38. The deliberate outage and reconnection begin around 0:47.

FFprobe measured the exported file at **58.92 seconds**. The H.264 video and original AAC speech decoded successfully in FFmpeg. The [submission report](../report.md) links the clip.

## Browser and remaining limits

Both development proxying and the production Vue build served by FastAPI were exercised. Browser checks covered chart/volume, symbols, data path/ledger, actual outage/recovery, playback/pause/speed/seek, returning to live, refresh restoration, and stale equities with completed last intervals. Desktop was 1440×1080; the optional 390×844 responsive check had document width 390. No production console errors were observed after the recorded production reload. This is a browser layout check, not a mobile build.

Yahoo can be delayed, sparse, revised, unavailable, or rate limited. Candles are polled every 15 seconds. Completion records whether the interval had ended when the server fetched it. After the one-day bootstrap, three-minute overlap polling may miss older corrections until another full backfill. SQLite retains the receipt log without automatic retention. The chart loads up to 360 bars. Browser replay plays up to 800 recent receipts from a saved checkpoint at receipts per second. The full log is available through the paginated API.

This is Part 4.1 only: no indicators, trading, account results, model/chat/vision/live-audio integration, deployment, or mobile build is claimed. The full overview was supplied by the user, resolving the earlier authentication/readability gap. Canvas upload remains a student action; **only `report.md`** is uploaded, linking public source/commit, support documents, and the single combined video.

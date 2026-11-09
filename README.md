# Marketstation · Live Market Workstation

IST 402 — Assignment 4, Part 4.1. A **Vue 3 frontend, Python FastAPI backend, and SQLite database on localhost**, with genuine Yahoo streaming quotes, updating one-minute candlesticks and volume, browser WebSockets, and persistent replay.

[Submission report](report.md) · [Design/schema](docs/design.md) · [Verification](docs/verification.md) · [AI/tool disclosure](AI-USE.md) · [Curated process evidence](docs/evidence-log.md) · [Your speaking script](docs/part-4-1-speaking-script.md)

## Initialize and run

Requires **Python >=3.12**, **Node >=24**, npm, and outbound HTTPS/WSS to Yahoo. No API key, account login, database service, or global SQLite installation is required. Python's standard-library sqlite3 is the database driver; Python dependencies and frontend dependencies are separately locked.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run db:init
npm run dev
```

Open **http://127.0.0.1:3000**. Development starts Vue/Vite on 3000 and FastAPI on 8000. Vite proxies `/api` and `/ws`, keeping the browser on one origin. Node runs launchers and frontend tooling; the application backend is Python FastAPI.

On Windows, use `py -3.12 -m venv .venv` and `.venv\Scripts\python.exe -m pip install -r requirements.txt`. The npm launchers select the virtual environment's Python automatically. In PowerShell, set optional environment variables with `$env:NAME='value'`; the examples below use POSIX shell syntax.

For a production build served directly by FastAPI on port 3000:

```sh
npm run build
npm start
```

Stop with Ctrl+C. `npm run db:init` is idempotent, and startup also initializes a missing database. Normal restart/migration preserves `data/market.sqlite`, its observation IDs, revisions, and receipts. Never delete the database just to restart the app. SQLite uses WAL, foreign keys, atomic ingestion transactions, and FULL synchronization.

Optional configuration: copy `.env.example` to `.env` and restart. Defaults: `HOST=127.0.0.1`, `PORT=3000`, `API_PORT=8000` (development only), `DATABASE_PATH=./data/market.sqlite`, `POLL_INTERVAL_MS=15000`, `ENABLE_DEMO_CONTROLS=false`. Poll interval must be >=10000ms. Python and the development launcher load `.env`; no credentials are printed or committed. This is a trusted local workstation, not a multiuser public server.

## Live dashboard

- Select BTC-USD, ETH-USD, SPY, or AAPL. Crypto permits an actual weekend live demonstration while US equities are closed.
- The main quote price follows Yahoo's **pricing WebSocket**. One-minute candles and their volume follow Yahoo's **Chart HTTPS endpoint**, refreshed every 15 seconds and pushed to Vue over the **FastAPI WebSocket** after a SQLite commit. The live quote and last candle close can differ between chart refreshes; their times are separate.
- **Feed health** shows provider, quote age, candle age, receipt age, and separate channel states. Live status requires an actual pricing message for the selected symbol during the current server session, a streaming upstream channel, successful candle retrieval, fresh source timestamps, and a connected browser socket. A fresh-looking cached record or connected socket alone is insufficient. Closed/missing data stays `WAITING / STALE`; failed upstream collection stays `FEED UNAVAILABLE` with retained candles.
- **Observation ledger** shows receipt IDs, logical identity (hover the symbol), source/receipt timestamps (hover for full ISO dates), revisions, and duplicate/revised states. **Data pipeline** shows Yahoo → SQLite commit → FastAPI WebSocket → Vue chart.
- Candles/volume share a UTC axis. Use fit, zoom, and pan. Unknown volume is a gap; reported zero stays zero. TradingView Lightweight Charts renders both series.

## Persistence and recorded replay

`server/schema.sql` defines schema v1. `observations` holds immutable content/revisions, `receipts` every normalized arrival, `heads` accepted current content and ordering watermark, and `feed_events` source state transitions. Candle JSON includes OHLCV and `complete`; times are UTC epoch milliseconds. The full [schema and ordering rules](docs/design.md) explain local IDs, provider identity, source/receipt times, revisions, and completion.

A duplicate adds a receipt without a false revision; a newer duplicate advances the request watermark. A changed payload creates a revision. An older request response is retained but cannot replace a newer head. A newer return to an old value is a legitimate revision. All data is committed before broadcast. The migrated Python store opens existing schema-v1 records without rewriting them; decoded-payload equality avoids false revisions from `1` versus `1.0` JSON formatting.

Choose **Replay** for receipt-order playback, play/pause, restart, seeking, and speed. The browser loads up to 800 recent saved receipts and the saved chart state just before them. Playback starts near the end of that window. Restart returns to the beginning of the window. The full history remains available through `/api/replay` pagination. `RECORDED REPLAY` labels the display, and live collection continues in the background. Click **Live** to return to current collection. **View observation ledger** jumps to the saved receipt IDs, observation IDs, timestamps, revisions, and candle states.

For market-closed/offline development, import the [genuine captured BTC recording](evidence/btc-recording.json) to a separate database:

```sh
DATABASE_PATH=./data/replay.sqlite npm run recording:import
DATABASE_PATH=./data/replay.sqlite npm run dev
```

Then choose Replay. The import preserves logical provider identities and original source/receipt times; numeric row IDs are local to the destination database. The compact fixture omits redundant historical duplicate receipts. It remains historical data, not evidence that Yahoo is currently streaming. CSV loading is ungraded class practice and is outside this part.

## Demonstrate a real unavailable feed

```sh
ENABLE_DEMO_CONTROLS=true npm run dev
```

Click **Demonstrate feed outage** beside the chart. This stops upstream socket and HTTP collection. Both channels become unavailable, counts stop growing, source ages increase, and the chart retains committed candles. Click **Reconnect Yahoo feed** to resume collection. The selected symbol needs a Yahoo pricing message from the new connection before it shows as live. Controls are off by default and reject cross-origin requests.

HTTP failures including 429, malformed data, timeouts, and socket closure expose errors without generating substitute prices. Socket retries use exponential backoff up to 30 seconds; chart requests retry on the poll schedule. TLS is verified using trusted CA roots; certificate verification is never disabled.

## Verify and reproduce

```sh
npm test
npm run build
```

`npm test` runs pytest behavioral tests and FastAPI WebSocket integration tests without contacting Yahoo or the working database. [GitHub Actions](.github/workflows/checks.yml) runs those checks and the Vue build on pushes/PRs. [Clean-checkout evidence](evidence/clean-checkout.json) records dependency installation, tests/build, isolated import, and production server HTTP/WebSocket startup from a checkout without `.venv`, node_modules, `.env`, dist, or an existing database.

For a separate real network check, start the local app with demo controls enabled, then run:

```sh
npm run evidence
```

The independent client asserts the required stack, receives fresh Yahoo quotes and an applied candle update through FastAPI's socket, compares committed SQLite records, briefly disconnects/reconnects upstream feeds, and checks replay/integrity. It fails when live data cannot be obtained. It writes `evidence/live-verification.json`, the live run output when redirected, and a compact genuine recording. It deliberately interrupts the local demo feed, so do not run it during another recording.

## Scope, disclosure, and limitations

The full overview requires Vue/FastAPI/SQLite; the earlier React/Express prototype was migrated when that requirement was supplied. [AI-USE.md](AI-USE.md) discloses the coding agent, known model information, tools, the withdrawn generated demo, and revised approach. The [curated evidence log](docs/evidence-log.md) connects prompt excerpts, code, failures, tests, decisions, and uncertainty. It is not a full chat export. You will record the single 30–60 second combined video with your own voice using [the speaking script](docs/part-4-1-speaking-script.md). The generated demo and narration have been removed from the current submission. Add your actual video link to `report.md` before uploading only that report to Canvas.

Yahoo's public endpoints are unofficial and can change, delay data, or rate limit access. Quotes are not a complete trade tape. Candles use reported OHLCV instead of inferred minute volume from daily/rolling counters. Completeness means the minute had ended by the chart request start time; it is persisted with that fetched observation. A closed market's last bar can therefore complete without waiting for another bar. Outages do not invent finalizing snapshots, and later provider corrections remain possible. No exchange-session calendar is implemented.

Startup backfills one available day. Later polling overlaps the last three minutes, so older corrections require another full backfill. SQLite retains the full log without automatic retention. The chart holds up to 360 bars and opens zoomed to the recent bars. Use **Fit chart to data** to see the full chart range. The browser plays a recent receipt window, and the paginated API provides the full log.

## Primary references

[Vue](https://vuejs.org/guide/introduction.html) · [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) · [yfinance WebSocket](https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html) · [Yahoo pricing protocol](https://github.com/ranaroussi/yfinance/blob/main/yfinance/pricing.proto) · [Lightweight Charts](https://tradingview.github.io/lightweight-charts/docs)

Third-party attribution/licenses are in [NOTICE.md](NOTICE.md).

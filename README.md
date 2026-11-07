# Marketstation · Live Market Workstation

IST 402 — Assignment 4, Part 4.1. A working React + Node client/server dashboard with genuine Yahoo Finance streaming quotes, updating one-minute candlesticks and corresponding volume, WebSocket delivery, and persistent SQLite observations.

[Submission report](report.md) · [Design and schema](docs/design.md) · [Verification](docs/verification.md) · [Demo video](evidence/part-4-1-demo.mp4)

## Run

Requires **Node.js 24 or newer**, npm, and outbound HTTPS/WSS access to Yahoo Finance. No API keys, account credentials, Python packages, database service, or global SQLite installation are required.

```sh
npm ci
npm run db:init
npm run dev
```

Open **http://127.0.0.1:3000**. The development server serves both the React client and the API/WebSocket on one port. Database initialization is idempotent; startup also initializes a missing database automatically.

For a production build:

```sh
npm run build
npm start
```

Stop with Ctrl+C. Restarting keeps all committed records in `data/market.sqlite`. The database uses SQLite WAL, foreign keys, transactions, and FULL synchronization. Do not delete the database to restart the server.

Optional configuration: copy `.env.example` to `.env`, edit the non-secret settings, and restart. Node loads `.env` automatically. Defaults: `HOST=127.0.0.1`, `PORT=3000`, `DATABASE_PATH=./data/market.sqlite`, `POLL_INTERVAL_MS=15000`, `ENABLE_DEMO_CONTROLS=false`. The poll interval must be at least 10 seconds. The server is designed for a trusted local workstation; it does not include multiuser authentication or internet-facing deployment.

## Use the dashboard

- Select BTC-USD, ETH-USD, SPY, or AAPL. Bitcoin and Ethereum provide a live demonstration while US equity markets are closed.
- The main price follows Yahoo's **pricing WebSocket**. Candlesticks and their volume follow Yahoo's **Chart endpoint**, refreshed every 15 seconds and delivered to the browser over the server WebSocket. Price and candle close can differ between refreshes; their source times are visible.
- Read **Feed health** for quote age, candle age, receipt age, provider, and channel status. A connected socket alone never qualifies data as fresh. Old/missing data is labeled `WAITING / STALE`; upstream failure is labeled `FEED UNAVAILABLE` and retains the last committed candles.
- Inspect the **Observation ledger** for persisted receipt IDs, logical identity (hover the symbol), source/receipt timestamps, revisions, and duplicate/revised states. **Data pipeline** shows the source → database → WebSocket → chart path.
- Choose **Replay** to load persisted receipts. Play/pause, seek, restart, and choose a receipt-per-second speed. Playback begins near the end of a recording; restart to see the entire recording. `RECORDED REPLAY` stays explicit while background live collection continues. Click **Live** to return to current data.
- Use the chart's fit button after resizing, or zoom/pan directly. The price and volume series share the UTC time axis. Missing volume is a gap, not fabricated zero. Reported zero remains zero. Charts use TradingView Lightweight Charts.

## Demonstrate an unavailable feed

```sh
ENABLE_DEMO_CONTROLS=true npm run dev
```

Click **Demonstrate feed outage** at the bottom of the page. This terminates the real Yahoo socket, aborts in-flight HTTP requests, and suspends polling. Both channels become unavailable, observation counts stop growing, data ages increase, and the chart remains. Click **Reconnect Yahoo feed** to resume the real providers. Demo controls are disabled by default, same-origin only, and intended for loopback development.

A failed HTTP request (including 429), malformed quote, or disconnected socket also produces an explicit channel error. WebSocket reconnection uses exponential backoff up to 30 seconds. Chart fetching retries on the polling schedule. No prices are generated as a fallback.

## SQLite and replay

`server/schema.sql` is the schema source. `observations` stores immutable logical identities and revisions; `receipts` records every normalized arrival, including duplicates; `heads` selects the accepted current revision; `feed_events` records state transitions. Candle payloads include OHLCV and `complete` in validated JSON. Times are UTC epoch milliseconds. See [the full schema and ordering rules](docs/design.md).

A candle's logical identity is `(source, kind, symbol, interval, minute start)`. Its payload fingerprint excludes arrival time. An unchanged payload adds a receipt without a revision. A changed payload creates a revision. A response from an older request is retained but cannot replace a newer accepted snapshot. A newer return to an old value is a genuine revision. All writes complete before broadcast. Replay uses original receipt order and applies the same accepted updates; it never re-ingests records.

The included [BTC recording](evidence/btc-recording.json) was captured from the actual live source. To prepare a separate database for market-closed development:

```sh
DATABASE_PATH=./data/replay.sqlite node scripts/import-recording.js
DATABASE_PATH=./data/replay.sqlite npm run dev
```

Choose Replay. Importing does not relabel old data as live. Numeric row/receipt IDs belong to the destination database; logical provider identities and original source/receipt times survive import. The recording omits redundant historical duplicate receipts to stay compact. It is an optional development aid; the deliverable's live evidence uses actual network collection. CSV loading is outside this part.

## Verify

```sh
npm test
npm run build
```

Tests run without Yahoo, credentials, or access to the working database. To repeat the real source → backend → client WebSocket → SQLite checks, start the app with demo controls enabled and run:

```sh
npm run evidence
```

This performs a brief real upstream disconnection/recovery and writes `evidence/live-verification.json` and a genuine BTC recording. It fails if no live quote/candle arrives. See [verification and limits](docs/verification.md) for results, evidence links, and the 45-second demo.

## Data/provider limitations

Yahoo's public endpoints have no availability or delay guarantee and may change or rate-limit access. This educational workstation does not promise exchange-grade real time, complete tick coverage, or trading suitability. Chart data is polled, not tick-by-tick OHLCV. Quotes are not summed into candles because daily/rolling cumulative volume is not one-minute traded volume. Candle completion is conservative: a later minute must exist before a bar is finalized. Late provider corrections remain possible after completion.

Startup backfills the available one-day chart. Later polls overlap the last three minutes to capture recent revisions; corrections outside that window are discovered only by a subsequent full backfill. Gaps remain gaps. The chart displays the most recent 360 bars; SQLite retains the full observation log. There is no automatic retention/compaction policy, and browser replay is bounded to 200,000 receipts per symbol; the API supports paginated access beyond that. Data still grows over long sessions, so back up and manage the database deliberately.

## References

- [Yahoo WebSocket transport documented by yfinance](https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html)
- [yfinance reference implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/live.py) and [pricing protocol](https://github.com/ranaroussi/yfinance/blob/main/yfinance/pricing.proto)
- [TradingView Lightweight Charts documentation](https://tradingview.github.io/lightweight-charts/docs)
- [Node SQLite API](https://nodejs.org/api/sqlite.html)

The Yahoo wire protocol file is attributed to yfinance in `NOTICE.md`. Lightweight Charts attribution is displayed in the chart and footer. No credentials are stored or shown in this repository.

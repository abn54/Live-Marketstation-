# Marketstation · Live Market Workstation

IST 402 — Assignment 4 through Part 4.3. A **Vue 3 frontend, FastAPI backend, and SQLite database on localhost**, with live Yahoo data, candlesticks/volume, SMA crossovers, persistent simulated accounts, backtesting, and checked AI decisions, grounded chat, chart vision and live audio.

**Part 4.3 verification status:** Gemini free-tier structured decisions, an automatic simulated buy/fill on a later Yahoo quote, grounded chat, actual chart interpretation and two-way provider audio have been observed. Automated checks are separate from live observations. The student's 30–60-second combined demonstration/process recording is still pending; see [verification notes](docs/part-4-3-verification.md).

[Submission report](report.md) · [Design/schema](docs/design.md) · [Verification](docs/verification.md) · [AI/tool disclosure](AI-USE.md) · [Curated process evidence](docs/evidence-log.md)

## Initialize and run

Requires **Python >=3.12**, **Node >=24**, npm, and outbound HTTPS/WSS to Yahoo. Yahoo, SQLite, replay and the SMA simulations require no API key. AI features use a Google AI Studio Free tier project, with billing disabled, and a server-side Gemini key. Python's standard-library sqlite3 is the database driver; Python dependencies and frontend dependencies are separately locked.

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

## SMA strategy, simulated account, and backtesting

The chart overlays **SMA 9** in blue and **SMA 21** in amber, with arrows at their crossovers. Both averages use completed candle closes. The caption explicitly identifies the excluded forming candle. Lengths can be changed in **Strategy laboratory**, using the layers icon near the bottom of the left rail or by scrolling below the chart.

**Historical backtest → Run backtest** processes all saved receipts for the selected symbol through a frozen watermark. It shows account equity, cash, position quantity, cost basis, realized and unrealized P&L, fees, drawdown, an equity curve, and order/fill history with decision and execution receipt IDs. Saved runs stay fixed when new data arrives.

**Paper account → Start paper account** creates a persistent simulated account. Earlier candles warm up the averages, and future completed-bar crosses drive orders. One running account per symbol is allowed. Repeating Start with the same configuration returns the existing account. Pause it before changing its settings. Backend collection and accounting continue while the browser is closed, and restart catches up from the saved receipt cursor.

Defaults are a $10,000 balance, SMA 9/21, 10 basis points commission per side, and 5 basis points adverse slippage. An upward cross buys with 95% of cash; a downward cross sells the position. Fills use the next eligible observed quote after the decision. Read [the complete execution and accounting rules](docs/part-4-2-design.md) before interpreting a result.

To reproduce a backtest without a live market, import the genuine November 12 BTC recording into an isolated database and run the app against it:

```sh
DATABASE_PATH=./data/strategy-offline.sqlite npm run recording:import -- evidence/part-4-2-recording.json
DATABASE_PATH=./data/strategy-offline.sqlite npm start
```

The fixed sample yields five simulated fills and $9,909.38 ending equity under the defaults. It includes historical Yahoo prices and original source and receipt times. `npm run strategy:verify` reproduces those checks in a temporary database. Your main database contains a longer history and can yield different results.

## AI decisions, bot, chat, vision and voice

Create a private `.env.local` in the repository root using the blank names in `.env.example`. Set `GEMINI_API_KEY` there and `GEMINI_FREE_TIER_CONFIRMED=true` **only after confirming the project shows Free tier and billing is disabled**. Never use a `VITE_` key variable, paste secrets into chat, or commit this file. Settings are read on demand; process environment values take priority. The text/chat and live vision/voice defaults are `GEMINI_MODEL=gemini-3.5-flash-lite` and `GEMINI_LIVE_MODEL=gemini-3.8-live`; `gemini-3.1-flash-live-preview` is also allowed for speech. Other models are rejected before any provider request. A key and flag cannot independently prove cloud billing state: keep billing disabled in Google AI Studio. Free-tier quotas/account eligibility still apply. No paid fallback or billing-enablement code exists. The old OpenAI credential, if present locally, is unused.

Use the **robot icon → AI workstation** below the market chart. It has a separate $10,000 simulated account per symbol, preserving the Part 4.2 experiments.

- **Check decision** captures Yahoo bars/quote, completed-bar SMAs, the latest crossover, the SMA candidate, account, recent orders/fills and previous checked decision. The model returns strict JSON. The server checks identity, schema, confidence, freshness, controls, SMA agreement, pending orders and whether this candle already traded. A valid action queues an order for a subsequently received fresh quote; it does not fill at the price sent to the model. Inspect the exact context, response and checks in the decision card.
- **Start auto bot** performs the same checked path once per new completed minute, for at most 10 attempts or 10 minutes. The SMA regime permits buys only when fast > slow and flat, sells only when fast < slow and long. AI can approve that candidate or veto with hold. Crossovers explain the regime change; this AI strategy does not require the cross to occur on the current minute. Pause/cancel invalidates an in-flight response and cancels pending orders. Automation turns off on provider failure and restart. It can continue within its limit while the browser is closed.
- **Review only** asks the live model about saved data with execution disabled. It does not prove current market availability or cause an order. During recorded replay, live action controls are disabled; independent collection/previously enabled server automation continue until paused or their limit.
- **Chat** receives the server's market/indicator/account snapshot, previous checked decision and recent simulated activity, plus up to six recent conversation turns. It cannot place orders. Ask it to explain the current candidate or account.
- **Chart vision → Analyze visible chart** captures a PNG from the actual Lightweight Charts instance and sends it as image input in the same Gemini Live turn as its question, with numeric context. The UI displays the returned speech transcription as the interpretation. A preview shows the exact image. It is separate from a text-only chart description. SQLite stores the fingerprint/dimensions rather than image bytes. Image and numeric snapshot timing can differ; model visual estimates are not exact measurements or execution instructions.
- **Live voice → Start voice** requests microphone permission, samples through an AudioWorklet, and streams mono PCM16 at 16 kHz over the same-origin FastAPI WebSocket to Gemini Live. Returned PCM at 24 kHz plays through the visible audio control; input/output transcripts appear. The key is used only in the server's authenticated Google connection. This is live API speech. The session receives a frozen workstation snapshot and has no order tools. End, failure, tab/symbol change, page exit or the two-minute limit releases the microphone and playback resources. Reconnect captures fresh context. The demo-enabled **Inject audio failure** control explicitly labels an injected interruption. One voice session is allowed at a time.

Google free-tier quota, unsupported-model and eligibility errors appear as unavailable and cannot cause a trade. A transient HTTP 503 was also observed and later text requests succeeded. Wait for service/quota recovery; the app does not switch to paid models. [Official pricing](https://aistudio.google.com/docs/pricing) lists free-tier availability, limits and data-use terms. [Part 4.3 design](docs/part-4-3-design.md) explains the context and checks. The earlier OpenAI credit failure is retained as a revised approach in the process evidence.


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
npm run strategy:verify
npm run ai:verify
```

`npm test` runs pytest behavioral/FastAPI tests and Node browser-API doubles for the actual TypeScript voice controller, without contacting Yahoo/Gemini or the working database. `npm run ai:verify` demonstrates automatic checked buys/sells, accounting, holds, invalid replies and an outage using an explicitly mocked provider and synthetic prices in memory. [GitHub Actions](.github/workflows/checks.yml) runs these checks and the Vue build on pushes/PRs. [Part 4.3 verification](docs/part-4-3-verification.md) distinguishes clean-checkout, browser, mocked, historical and live-provider evidence.

For a separate real network check, start the local app with demo controls enabled, then run:

```sh
npm run evidence
```

The independent client asserts the required stack, receives fresh Yahoo quotes and an applied candle update through FastAPI's socket, compares committed SQLite records, briefly disconnects/reconnects upstream feeds, and checks replay/integrity. It fails when live data cannot be obtained. It writes `evidence/live-verification.json`, the live run output when redirected, and a compact genuine recording. It deliberately interrupts the local demo feed, so do not run it during another recording.

For opt-in **real AI provider** verification, `npm run ai:evidence` calls the local app using its confirmed free-tier configuration. Supply a fresh chart PNG with `--chart`; optional `--audio-input` accepts mono PCM16/16-kHz WAV and requires `--audio-description` explicitly identifying microphone, prerecorded or synthetic origin. It writes an ignored local JSON result and fails rather than replacing errors with mocks. Audio traverses the actual FastAPI/Gemini Live WebSocket bridge with real-time pacing and returned speech/transcripts. A prerecorded/synthetic probe does not prove browser microphone capture. Omitted image/audio checks remain incomplete. See `npm run ai:evidence -- --help`.


## Scope, disclosure, and limitations

The full overview requires Vue, FastAPI, and SQLite. The earlier React/Express prototype was migrated when that requirement was supplied. [AI-USE.md](AI-USE.md) discloses the coding agent, known model information, tools and revised approaches. The [evidence log](docs/evidence-log.md) connects instructions, code, failures, tests, decisions, and uncertainty. Archived [Part 4.1](docs/reports/part-4-1.md) and [Part 4.2](docs/reports/part-4-2.md) reports preserve those submissions and their videos. The current [Part 4.3 report](report.md) must remain marked pending until the remaining verification and the student's new 30–60-second combined demo/process video are available.

Yahoo's public endpoints are unofficial and can change, delay data, or rate limit access. Quotes are not a complete trade tape. Candles use reported OHLCV instead of inferred minute volume from daily/rolling counters. Completeness means the minute had ended by the chart request start time; it is persisted with that fetched observation. A closed market's last bar can therefore complete without waiting for another bar. Outages do not invent finalizing snapshots, and later provider corrections remain possible. No exchange-session calendar is implemented.

Startup backfills one available day. Later polling overlaps the last three minutes, so older corrections require another full backfill. SQLite retains the full log without automatic retention. Status totals rebuild once on open and then aggregate only appended IDs; receipt reads preserve cursor order without sorting the entire observation history. The chart holds up to 360 bars and opens zoomed to the recent bars. Use **Fit chart to data** to see the full chart range. The browser plays a recent receipt window, and the paginated API provides the full log.

## Primary references

[Vue](https://vuejs.org/guide/introduction.html) · [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) · [yfinance WebSocket](https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html) · [Yahoo pricing protocol](https://github.com/ranaroussi/yfinance/blob/main/yfinance/pricing.proto) · [Lightweight Charts](https://tradingview.github.io/lightweight-charts/docs)

[Gemini pricing/free tier](https://aistudio.google.com/docs/pricing) · [GenerateContent](https://ai.google.dev/api/generate-content) · [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) · [Image input](https://ai.google.dev/gemini-api/docs/image-understanding) · [Gemini Live](https://aistudio.google.com/docs/live-api) · [Live WebSocket protocol](https://aistudio.google.com/api-reference/live/bidi-generate-content)

Third-party attribution/licenses are in [NOTICE.md](NOTICE.md).

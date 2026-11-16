# Part 4.2 design and execution rules

The live data and immutable receipt schema from Part 4.1 feed both the chart and simulated accounts. Vue shows current accepted market snapshots. FastAPI processes account decisions in SQLite receipt order. A backtest freezes its final receipt watermark. A running paper account processes new receipts and checkpoints its state.

## Indicators and signals

`SMA(N) = sum(last N completed closing prices) / N`. Defaults are 9 and 21 observed one-minute bars, chosen as an understandable short/long comparison. Lengths must satisfy `2 ≤ fast < slow ≤ 200`. Each SMA is absent until it has a full window. Gaps stay gaps and windows count available bars. An overnight gap can therefore remain inside a window.

A buy crossover occurs when `previous fast − slow ≤ 0` and the current difference is positive. A sell crossover uses `previous difference ≥ 0` and a negative current difference. Exact equality produces no signal until an average leaves equality. A relative tolerance of `1e-12` treats negligible floating-point differences as equality.

`MovingAverages.update` keeps a deque of the latest slow-window closes. The Python batch adapter and Vue TypeScript function rebuild a snapshot from its completed candles. Tests compare both batch outputs and every incremental step to independent pandas `rolling(window, min_periods=window).mean()` calculations, including expected crossovers. The test inputs contain an extreme unfinished close, which must have no effect. [pandas rolling reference](https://pandas.pydata.org/docs/reference/api/pandas.Series.rolling.html) · [TradingView moving averages](https://www.tradingview.com/support/solutions/43000502589-moving-averages/)

The chart displays up to 360 current accepted bars. Historical corrections can change those snapshot overlays. A simulated account consumes the first accepted **completed** version of a new source minute once, in increasing source-time order. Later partials, duplicates, superseded arrivals, older backfills and completed corrections leave its past decisions intact. The market ledger retains them for inspection. Account receipt IDs identify the precise versions used. This distinction between a current snapshot and an original decision is intentional.

## Simulated order and fill timeline

1. Warm the averages from completed bars. Paper accounts warm up on all history available when they start. Backtests warm up sequentially from the beginning of the symbol's saved receipt log.
2. Only a completed crossover received no more than two minutes after its minute end can submit an order. Old bootstrap candles warm the averages and are excluded from stale trading instructions.
3. Upward crosses submit buys while flat. Downward crosses submit sells while long. Other crosses are logged as skipped. An opposing crossover cancels a still-pending order.
4. The next **applied** quote receipt after the decision can fill it if the quote source time is at or after the signal candle's end and the quote is no more than 60 seconds old at receipt. Same-source-time quote corrections follow receipt order. Older-source-time quotes cannot move the mark backward.
5. If a later quote arrives more than five minutes after the decision, the pending order expires. During an outage it waits. The next receipt resolves expiry.

Execution uses a later observed quote because Yahoo may deliver a completed candle after the following minute has already opened. Filling at that earlier open would assign a price that precedes the decision. Decision and fill receipt IDs are retained separately. Prefix-causality tests change later observations and confirm that earlier orders and fills remain unchanged. [TradingView strategy execution timing](https://www.tradingview.com/pine-script-docs/faq/strategies/)

## Account arithmetic

The account starts with USD cash, no position, and zero P&L. It is long-only and holds one selected symbol. A buy budgets 95% of cash, including commission. Fractional shares or coins use eight decimal places, rounded down. The model assumes one full fill per eligible order and unlimited liquidity at the observed quote plus adverse slippage. Order books, partial fills, margin, short selling, interest, dividends, corporate actions and taxes are outside this model.

- Buy execution price is `quote × (1 + slippageBps / 10000)`. Sell price is `quote × (1 − slippageBps / 10000)`.
- Commission is `rounded notional × feeBps / 10000`, rounded to cents. The default fee is 10 bps (0.10%) per side and default slippage is 5 bps (0.05%). These are modeling choices.
- Notional and fees round half up to cents. Decimal arithmetic keeps internal account values as decimal strings.
- Entry cost basis equals buy notional plus entry fee. Selling the position realizes net proceeds minus that basis. The exit fee is subtracted from proceeds.
- Market value equals quantity times the last observed quote, rounded to cents. Unrealized P&L equals market value minus entry basis. Equity equals cash plus market value and also starting cash plus realized plus unrealized P&L.
- Open positions remain marked at the last observed quote at the end of a test. Final liquidation and exit costs are excluded from that mark.
- Maximum drawdown is the largest percentage fall from an earlier equity peak, evaluated on every quote. The plotted curve retains the last mark per observed minute. It can smooth an intraminute trough while the drawdown metric still includes it.

Known examples verify a $1,000 account buying 9.5 units at $100 and selling at $110, ending with $1,095 cash and $95 realized profit. A separate 1% fee example ends at $1,074.30 after $19.76 in total fees. Tests check adverse slippage, drawdown, and equity reconciliation.

## Durable experiments and schema

Initialization adds `simulation_runs` and `heads_observation` while preserving market rows and IDs. Market schema compatibility stays at user_version 1. The run table has `id`, `mode`, `status`, `symbol`, `created_at`, `until_receipt`, `config_json` and `state_json`. A partial unique index permits one running paper account per symbol. The existing `heads` join gains an observation-ID index for larger databases.

Run state holds cash, position, cost basis, realized P&L, fees, indicators, orders, fills, equity points, and the last processed receipt. Under the store lock, a transaction commits the entire updated state with its receipt watermark. After a stop between ingestion and account processing, startup catches up from that watermark. Repeated callbacks and startup retries cannot duplicate trades. A paused account remains saved. Start creates a new account after the previous one is paused.

The UI displays the latest 20 saved runs per symbol and 30 trade rows per view. The full run is available from `GET /api/simulations/{id}`. Backtest creation is capped at 500,000 receipts per symbol. This local workstation uses one backend worker and same-origin guards for state-changing requests.

## Reproduction and interpretation

`npm run strategy:verify` imports `evidence/part-4-2-recording.json` into temporary SQLite and runs the defaults. The sample has 2,917 genuine Yahoo receipts from November 12, 2026. It produces 108 completed bars, five crosses and five fills. Ending equity is $9,909.38, with −$73.31 realized and −$17.31 unrealized P&L. Its prices are historical, and execution is simulated.

This measures a single selected instrument over one saved receipt window under explicit costs and timing. The symbol was selected from available instruments and introduces selection/survivorship concerns. Changing windows after seeing results risks overfitting. Quote latency, missing data, gaps, source revisions and the execution model can change results. Future-performance claims would require broader out-of-sample and multi-instrument evaluation.

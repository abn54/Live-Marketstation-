# IST 402 — Assignment 4, Part 4.2

**Indicators, Simulated Trading, and Backtesting**

Student identifier **abn54** · November 15, 2026

- **Repository** — [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-).
- **Version** — Implementation commit will be pinned after final verification.
- **Part 4.2 video** — Student-recorded 30–60 second demonstration link pending. The new recording must show the SMA overlays and crossover, simulated account and trade history, historical backtest result, and one design or verification decision.

## Completed

The existing Vue 3, FastAPI, SQLite and Yahoo WebSocket workstation now displays configurable SMA 9 and SMA 21 lines with upward and downward crossover markers on its candlestick chart. The indicator caption gives both current values, the latest crossover, and the completed-candle policy. Warm-up windows have no SMA value until enough closes exist. Forming candles are excluded.

The Strategy laboratory has a historical backtest and a paper account. Both use the same crossover and accounting engine. It tracks orders, fills, cash, fractional position quantity, cost basis, realized and unrealized profit or loss, commissions, equity and maximum drawdown. Orders link decision receipts to later quote receipts used for fills. Saved results, configuration and paper-account receipt checkpoints survive restart in SQLite. Paper accounts warm up from existing observations and trade only on future eligible signals. A backtest evaluates the historical decisions sequentially through a frozen receipt watermark.

Part 4.1's live chart, volume, feed health, observation ledger, read-only replay and outage controls continue to work. The previous submission is preserved in [its archived report](docs/reports/part-4-1.md).

## Design and execution decisions

The defaults are 9/21 completed one-minute bars, $10,000 starting cash, 10 basis points commission per side and 5 basis points adverse slippage. These are editable modeling assumptions. They were chosen before inspecting the strategy result. A short SMA crossing upward submits a buy with 95% of cash while flat. A downward cross sells the held position. Equality alone does not create a signal.

Each decision uses only data already received. The server fills an order on the next eligible quote receipt after its signal, at the quote price adjusted for slippage. A completed candle can arrive after the following minute has opened, so using that earlier open would assign a fill before the decision. A signal must arrive within two minutes of the candle end, and a fill quote must be within 60 seconds of its source time. An order with no eligible quote within five minutes expires when a subsequent quote is processed.

The account consumes the first accepted completed observation of each increasing source minute once. Later corrections stay inspectable in the market ledger and do not rewrite past account decisions. Current chart overlays use accepted snapshot heads, so corrections can change their historical appearance. The recorded decision and fill IDs support tracing the difference.

Decimal arithmetic rounds cash, notional and commissions to cents, and quantities down to eight decimals. Entry cost includes the buy fee. Realized P&L is net sell proceeds minus entry cost. Unrealized P&L is the last observed quote value minus entry cost. The invariant is `equity = starting cash + realized P&L + unrealized P&L`. Open positions remain marked at test end. [Full execution and schema notes](docs/part-4-2-design.md) · [core implementation](server/strategy.py)

## Verification and results

| Check | Result |
| --- | --- |
| Automated behavioral and integration tests | 44 tests cover the existing market contract, pandas reference comparisons, batch/incremental/Vue equivalence, crossovers and equality, unfinished candles, late revisions, duplicate retries, cost arithmetic, drawdown, prefix causality, account persistence, and FastAPI validation. [Test output](evidence/part-4-2-tests.txt) · [strategy tests](tests/test_strategy.py) |
| Vue typecheck and production build | Passed. [Build output](evidence/part-4-2-build.txt) |
| Genuine recorded data and accounting | The isolated sample has 2,917 historical Yahoo receipts, 108 completed candles, five crossovers and five simulated fills. Every fill follows its signal receipt. Equity reconciles, market rows are preserved, and the saved result survives reopening SQLite. [Results with orders and fills](evidence/part-4-2-verification.json) · [repeatable verification](scripts/verify_strategy.py) |
| Browser | Verified chart SMA values and markers, parameter validation, backtest controls, account metrics and equity curve, order/fill tables, saved results, paper-account start, and connection recovery after the query-index correction. [Detailed verification](docs/part-4-2-verification.md) |
| Fresh checkout | A new clone at source commit `6c131ec` completed locked installs, 44 tests, Vue build, isolated recording import and production HTTP/WebSocket checks in **30.91 seconds**. Its backtest reproduced five fills and $9,909.38 equity. [Clean-checkout result](evidence/part-4-2-clean-checkout.json) |
| GitHub checks | **Succeeded** for source commit `6c131ec`. Python tests, Vue typecheck/build, isolated recording import and recorded-strategy verification all passed. [Actual Actions run](https://github.com/abn54/Live-Marketstation-/actions/runs/43801567690) · [workflow](.github/workflows/checks.yml) |

The fixed historical sample finishes with **$9,909.38 equity**, **$496.34 cash**, **0.13095891 BTC**, **−$73.31 realized P&L**, **−$17.31 unrealized P&L**, and **$47.28 in fees**. Return is **−0.9062%** and maximum drawdown is **0.9112%**. The open position remains marked to the last quote. The longer local database produces a different result because it covers additional observations. Profitability was not used as a completion criterion.

The calculation reference is pandas `rolling(...).mean()`, using a full window and independent crossover comparisons. Tests invoke the actual Vue TypeScript calculator through Node and compare it and the Python batch/incremental outputs to that reference. [pandas rolling documentation](https://pandas.pydata.org/docs/reference/api/pandas.Series.rolling.html)

## Revised approach and disclosure

During browser verification, the growing market history caused four-second candle queries for each symbol. The initial four-symbol WebSocket snapshot exceeded the browser's connection deadline. Adding an index on `heads(observation_id)` reduced the same local queries to approximately 2–3 milliseconds per symbol, and the browser displayed the live chart and SMAs. The first Vue typecheck also caught a marker generic mismatch, corrected using the chart library's `Time` type. [Curated evidence log](docs/evidence-log.md)

Codex generated and revised the source, tests, controls, docs, and report, and ran the recorded verification. Its disclosed environment identifies the GPT-6 model family. Exact deployed model metadata was unavailable. The student supplies the demonstration recording and should be able to explain the implementation. [Tool and model disclosure](AI-USE.md)

## Startup, reproduction and limits

The README documents Python >=3.12 and Node >=24, creating `.venv`, installing locked requirements, `npm ci`, `npm run db:init`, and `npm run dev`. `npm run build` and `npm start` serve the production app on localhost. Schema initialization adds the run table and join index while preserving market records. Yahoo requires no credentials. [README](README.md) · [agent instructions](AGENTS.md) · [schema](server/schema.sql)

`npm run strategy:verify` imports the committed genuine recording into temporary SQLite and reproduces the stated result. Synthetic test examples are explicitly labeled. Browser replay and backtests retain their historical labels when live data is stale or unavailable. [Recorded sample](evidence/part-4-2-recording.json)

This is a long-only simulation with one chosen symbol, fractional units, full fills and modeled costs. It omits spread/depth, partial fills, market impact, taxes and corporate actions. Gaps remain in the data. Marked open P&L excludes a hypothetical final exit fee. Missing or delayed quotes reduce fills. The sample's instrument selection introduces selection/survivorship concerns, and tuning on it risks overfitting. A historical result cannot establish future performance. The UI displays the latest 20 saved runs and 30 trade rows per table. Full saved results remain available through the API, and each creation is bounded to 500,000 symbol receipts.

Upload **only this `report.md`** to Canvas after adding the accessible Part 4.2 video link. The source and supporting evidence remain in the public repository.

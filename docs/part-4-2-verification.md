# Part 4.2 verification

Verification is performed on the Vue/FastAPI/SQLite workstation. Tests use injected values or isolated temporary databases. The committed receipt window contains genuine recorded Yahoo observations. Browser checks use the actual local production application and the existing market log.

## Repeated checks

Run `npm test`, `npm run build`, and `npm run strategy:verify`. The independent reference is pandas rolling arithmetic with full windows. Tests run the actual frontend calculator through Node, then compare every output and crossover to pandas and the incremental Python state. Known account examples check 95% sizing, fractional quantities, fees, adverse slippage, realized and unrealized P&L, equity reconciliation and drawdown.

The 2,917-receipt historical sample is reproducible with SMA 9/21 and the defaults. It produces five fills and $9,909.38 ending equity. Its full orders and fills are in [the recorded verification](../evidence/part-4-2-verification.json). The verification checks receipt ordering, signal-candle end, unchanged market rows, and reopening the saved account. A paper-account test warms indicators, adds a new crossover and quote, and reopens SQLite to prove that the fill is retained exactly once.

The no-look-ahead test fixes the prefix that creates and fills an order, adds later prices, and checks that the original decision and execution remain unchanged. Tests keep forming closes out of signals, prevent completed corrections and duplicate callbacks from trading twice, exclude late bootstrap instructions, preserve frozen backtests, and validate same-origin routes and invalid settings.

## Browser recipe

1. Open BTC-USD and confirm both chart lines, SMA values, crossover arrows and the forming-candle exclusion caption.
2. Open Strategy laboratory. Run a historical backtest and inspect cash, equity, position, P&L, costs, drawdown, the equity curve, and orders/fills with their source receipt IDs.
3. Enter a fast length greater than the slow length. Verify the run action is disabled with a readable validation message. Restore 9/21.
4. Start a paper account, confirm its simulated label and initial cash balance, and verify that the existing history warms the averages without generating retrospective orders.
5. Refresh and reload saved experiments. Inspect Orders & decisions, switch symbols and modes, pause the account, and confirm saved results persist.
6. Exercise a narrow layout and check that each new panel and its inputs remain usable.

The historical backtest on the larger local database yielded 201 fills, including buys and sells. The fixed sample is used for stable assertions because the live database grows over time. Run parameters, receipt watermark and period are displayed with each result.

The saved paper account recovered after backend restart and page reload. Later genuine receipts had produced nine crosses and seven simulated fills. Pausing retained those results. BTC/ETH navigation restored the appropriate symbol state. Both 556px and 1440px layouts were checked, and no browser console errors were observed. [Browser observations](../evidence/part-4-2-browser.json) · [SMA chart](../evidence/part-4-2-indicators.jpg) · [Account and backtest](../evidence/part-4-2-dashboard.jpg)

## Failed/revised observations

Before the new join index, BTC/ETH/SPY candle queries on the larger history took about four seconds each. After `heads_observation`, the same queries took about 2–3 ms, and a browser reload restored live chart data and indicator values. The query timing is an observed local measurement. The marker plugin's initial generic type mismatch was caught by vue-tsc and corrected before browser verification.

## Submission status

A fresh `git clone --no-local` at source commit `6c131ec33604be858a77bfb6e8a0a048375b6d85` passed in **30.91 seconds**. It began without a virtual environment, Node modules, .env, build output or database. Locked installs, 44 tests, Vue build, isolated genuine recording import, production HTTP/WebSocket startup and a backtest with five fills succeeded. Its equity was $9,909.38. [Clean-checkout evidence](../evidence/part-4-2-clean-checkout.json)

The GitHub Actions run for that source commit completed successfully. Tests, the Vue build, isolated import and recorded-strategy verification all passed. [Observed run](https://github.com/abn54/Live-Marketstation-/actions/runs/43801567690) · [captured status](../evidence/part-4-2-ci.json)

The submitted Part 4.2 clip lasts **59.12 seconds**, within the required 30–60 seconds. It was cut from the student's 167.424-second Kaltura recording. Its opening shows SMA 9/21 and the completed-candle explanation. Backtest settings and account metrics follow around 0:19, followed by the equity curve, fills, reference verification, and decision/execution timing. The final table shows orders and their outcomes.

FFprobe checked the duration and H.264/AAC streams. FFmpeg decoded the full export without errors. The clip keeps the student's original narration at its original speed. The main database shown in the recording is longer than the fixed offline sample, and the student changes the cash setting while recording. [Video verification and source scene ranges](../evidence/part-4-2-video-verification.json)

The report pins the application, evidence and video commit. Part 4.1's submitted report remains archived separately.

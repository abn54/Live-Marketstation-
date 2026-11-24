# IST 402 — Assignment 4, Part 4.3

**AI-Assisted Automated Trading and Interaction** · abn54 · November 24, 2026

**Recording pending — do not submit yet.** The implementation and live Gemini provider checks are available. The student's own microphone demonstration and accessible **30–60-second combined demonstration/process video** still need to be recorded and linked here.

- **Repository:** [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-).
- **Implementation commit:** pending final Gemini source/evidence snapshot. Historical OpenAI source `3315741` is superseded; its checks are not represented as checks of this revision.
- **Single Part 4.3 video:** **pending student's recording/link**. Earlier parts' videos do not demonstrate this part.

## Completed work and design

The Vue 3/FastAPI/SQLite workstation preserves genuine Yahoo streaming observations, candlesticks/volume, completed-bar SMA 9/21, persistence/replay and Part 4.2 accounting/backtests. Part 4.3 adds a decision API, separate durable simulated AI accounts, opt-in automation, grounded chat, real chart-image interpretation and Gemini Live two-way speech. All trading stays simulated.

`POST /api/ai/decision` sends a bounded snapshot of accepted Yahoo observations, source/receipt times and ages, completed indicators/crossover, SMA candidate, simulated account, recent orders/fills and previous checked decision. The model returns strict buy/sell/hold JSON with symbol, snapshot ID, confidence and explanation. The UI and SQLite audit expose the exact context, response and checks.

The SMA regime determines the permitted side: fast > slow while flat permits buy; fast < slow while long permits sell; otherwise hold. AI can confirm that candidate or veto with hold. The crossover explains the regime; unlike Part 4.2's event strategy, this bot can enter an existing regime. Schema, finite confidence, identity, SMA agreement, fresh current-session source data, unchanged controls/completed candle and account eligibility are rechecked after the provider responds. Actions need confidence >=0.60; it is a self-report, not a calibrated probability. Stale, invalid, unavailable and held results cannot alter holdings.

An eligible action commits the audit and pending order atomically. It fills only from a later applied, fresh Yahoo quote received after the checked response/final receipt watermark. Existing Decimal rules use 95% cash, eight-decimal quantity, 10 bps fee and 5 bps adverse slippage. Cash, position, equity, realized/unrealized P&L, fees, orders and fills remain inspectable. Automation is off initially/after restart, limited to one attempt per completed minute and 10 attempts/10 minutes. Pause cancels pending orders and invalidates late replies; a provider outage disarms it. Review-only requests cannot trade.

## Required AI interaction

**Chat** receives the server's market/indicator/account snapshot and bounded conversation history. It explains current activity without order tools. **Vision** sends the actual chart PNG and question together to Gemini Live, alongside numeric context. Its output transcription appears with the preview and stored image fingerprint/dimensions. It cannot execute a trade, and visual estimates may differ from newer exact values. **Voice** streams browser microphone PCM16 at 16 kHz through FastAPI to Gemini Live and returns 24-kHz spoken audio plus input/output transcripts. It receives a frozen snapshot and no order tools. End, failure, tab/symbol changes and the two-minute limit release resources; reconnect captures fresh context.

Text/decision uses `gemini-3.5-flash-lite`; vision/speech uses `gemini-3.8-live`. The user confirmed a Free tier Google project with billing disabled. Server-only credentials, model allowlists and an explicit confirmation guard implement the no-payment preference. No paid fallback/billing changes exist. The app cannot independently inspect billing state; free-tier eligibility and quotas still apply. Requested aliases are distinguished from actual returned model/version IDs.

## Verification and evidence

| Check | Result and boundary |
| --- | --- |
| Automated checks | **83 Python + 9 voice-controller/DSP tests passed**, Vue build/typecheck and both strategy/AI verifiers passed. [Tests](evidence/part-4-3-tests.txt) · [Build](evidence/part-4-3-build.txt) |
| Live decision and chat | Real structured hold passed server checks and preserved the $10,000 flat account. A real chat reply explained the account. Holds and failures are not presented as buy/sell fills. [Provider evidence](evidence/part-4-3-gemini-live.json) |
| Automated simulated buys/sells | A clearly mocked provider/synthetic market drove automatic checked buys/sells and later-quote fills: $8,017.10 final flat equity, −$1,982.90 realized P&L, $17.01 fees. [Mocked verifier](evidence/part-4-3-mocked-verification.json) |
| Actual chart vision | The real model interpreted the submitted candlestick/SMA PNG and stated future-price uncertainty. [Image](evidence/part-4-3-gemini-chart.png) · [Vue response](evidence/part-4-3-gemini-vision.jpg) |
| Live API audio | A labeled synthetic test question traversed the actual FastAPI/Gemini bridge; Gemini transcribed the input and returned 10.84 seconds of account-grounded speech. Backend byte/turn counters independently confirmed transport. This is separate from the pending student microphone/video demonstration. |
| Invalid/unavailable/audio failure | Injected checks cover malformed decisions, wrong identity/confidence, stale/revised/paused context, unavailable service, audio frames/permissions/transport failure, cleanup/reconnect and single-session limits. Actual Gemini 503s were visibly unavailable and disarmed automation. No fallback trade occurred. |
| Clean checkout / CI | Final Gemini source checks pending publication; historical OpenAI checks apply only to their recorded commit. [Clean-checkout record](evidence/part-4-3-clean-checkout.json) · [CI record](evidence/part-4-3-ci.json) |
| Student combined video | **Pending** 30–60-second accessible Part 4.3 recording. |

## Process account and revised approaches

The student supplied the requirements and asked Codex to implement/verify the necessary work. Codex generated/revised code, tests, UI, documents and report; consulted official provider references; exercised the actual browser; and preserved earlier experiments. Treating AI as checked SMA confirmation/veto keeps sizing/accounting deterministic. The final receipt watermark prevents execution at a price already visible before the checked decision.

The initial OpenAI route received a real exhausted-credit error. The student declined payment and approved Gemini Free tier; no billing was enabled. Temporary GenerateContent image 503s then motivated explicit Gemini Live vision. A separate asynchronous image frame failed to establish image availability; putting the image and question in one turn produced actual interpretation. A large-history startup delay was traced to complete-log counts on every quote; append-only counters/receipt-first joins fixed it without deleting records. Earlier browser lifecycle failures led to generation guards and cleanup tests. These failed/revised approaches and evidentiary boundaries are retained in the [curated process log](docs/evidence-log.md) and [AI/tool disclosure](AI-USE.md). The student records and narrates the combined video themselves; there is no public speaking script.

## Limitations and supporting documents

Free-tier quotas, service capacity, browser permissions and autoplay can interrupt a demonstration. Model explanations may be wrong, snapshots are bounded/frozen, and simulation does not model depth, partial fills, impact or taxes. Successful checks establish behavior under observed/tested inputs, not profitability or universally reliable availability. Browser microphone speech remains to be demonstrated by the student. This is a local workstation without multiuser authentication.

[Startup/initialization](README.md) · [Agent instructions](AGENTS.md) · [AI context, checks, audio and SQLite schema](docs/part-4-3-design.md) · [Market persistence/replay design](docs/design.md) · [Accounting rules](docs/part-4-2-design.md) · [Detailed verification/boundaries](docs/part-4-3-verification.md)

Submit **only this `report.md`** to Canvas after adding the final commit and actual accessible video link. Source/evidence remain in the linked repository.

# Curated, redacted process evidence — Parts 4.1–4.3

These are selected decision records, not a complete chat export. Prompt excerpts are from the assignment text/user instructions. Source observations, injected tests, and UI captures have different evidentiary roles. The final report pins all current links to the submitted implementation/evidence commit. The previous framework implementation is retained only in history.

## Part 4.3 · From model output to a checked simulated outcome

- **Intent/prompt.** “Supply relevant market observations, indicators, and simulated-account context” and show checks “before the response can cause a simulated action.”
- **Artifacts/decision.** [AI service](../server/ai.py), [provider client](../server/ai_provider.py), [panel](../client/AIPanel.vue), and additive schema. SMA regime permits one side; AI may confirm or hold. The server checks schema/identity/confidence/freshness/control generation/current candle/account eligibility, then commits audit and pending order together. Fills wait for a fresh quote after the checked decision watermark. A separate AI account preserves the earlier experiments.
- **Verification.** [Injected tests](../tests/test_ai.py) and [explicitly mocked end-to-end result](../evidence/part-4-3-mocked-verification.json) exercise automatic buy/sell, accounting, veto/hold, invalid response, outdated context and unavailable provider. The fixtures use memory/temporary SQLite. The actual browser/source path showed fresh Yahoo quotes, an unavailable model call leaving $10,000 unchanged, and a feed outage causing a pre-model skip followed by recovery.
- **Uncertainty.** Mock passes establish behavior under controlled inputs, not live model quality. Live successful decisions remain unverified while credits are exhausted. The regime filter differs from Part 4.2's crossover-event strategy and is disclosed explicitly.

## Part 4.3 · Text, actual image input, and live-audio lifecycle

- **Intent/prompt.** “Include a chatbot grounded in the workstation's data,” a vision model receiving chart imagery, and “two-way real-time speech through a live API.”
- **Artifacts/decision.** The server builds fresh bounded context for chat/vision and a frozen context for voice. `MarketChart.captureImage` captures the real chart canvas as PNG, rather than asking a text-only model to imagine the chart. [Captured input](../evidence/part-4-3-chart-input.png) · [voice controller](../client/voice.ts). FastAPI authenticates Realtime SDP negotiation while microphone/remote audio uses real WebRTC. None of these explanation paths has trading tools.
- **Verification.** Browser observations confirmed capture/preview, quota errors in chat/vision, and rendered audio controls. [Voice-controller tests](../scripts/test-voice.mjs) use browser API doubles to check actual controller cleanup, permission denial, timeout, provider failure/reconnect, transport loss and late permission after cancellation. A UI check exposed a misleading initial voice status after switching other tabs; the watcher now ends sessions only when leaving the voice tab.
- **Failed checks/revision.** Two additional voice regression tests initially failed: a late autoplay rejection revived an ended UI state, and a provider `response.done` failure left it labeled live. The controller now guards the playback callback's generation and treats failed responses/closed event channels as terminal failures that release the microphone. Both regression tests then passed with the rest of the controller suite.
- **Uncertainty.** A rendered control, mock session or negotiated SDP is insufficient evidence of a live spoken exchange. Successful image interpretation and microphone/remote-audio conversation remain required; the report must retain those pending states.

## Part 4.3 · Failed secure setup and actual exhausted-credit response

- **Intent.** Enable and demonstrate genuine provider calls without exposing credentials.
- **Failed approach.** The secure local key-save confirmation repeatedly returned not approved. No key was created or written through that flow. The student then used an ignored local file; the agent only created a blank field and checked presence without printing its value.
- **Actual service observation/revision.** Real Responses requests reached OpenAI but returned HTTP 429, type `insufficient_quota`, code `credit_balance_exhausted`. The initial generic 429 message did not distinguish this from a rate limit. The provider client now explicitly classifies exhausted credit and has a regression test; no fake successful decision replaces the provider failure.
- **Verification/decision.** [Live failure and browser evidence](../evidence/part-4-3-live-provider.json) are separate from mocked successes. Automation disarms on a provider outage, and the visible account remained unchanged. The student was asked to fund the API project or use a funded key locally; no purchase or account link was made.
- **Remaining uncertainty.** Adding funds is an external account action and was not claimed complete. Model access and successful multimodal behavior still need real observations after that change. The final 30–60-second student video is pending.

## Part 4.2 · Indicators, execution and accounting

- **Intent and instruction.** “Display two simple moving averages of different lengths and their crossover” and “using only information available at each decision time.”
- **Artifacts and decision.** `client/indicators.ts` and `server/strategy.py` compute completed-bar averages. `server/simulation.py` consumes saved receipts and commits account state with a receipt checkpoint. An order fills at a subsequently observed quote, because a completed candle may arrive after the following minute has opened.
- **Verification.** Independent pandas rolling means check Python batch, incremental, and Vue values and crossovers. Known cash/P&L examples, unfinished bars, late corrections, duplicate receipt retries, prefix causality, fees, slippage and persistence have focused tests. The genuine recorded sample yields five simulated fills. [Recorded result](../evidence/part-4-2-verification.json) · [tests](../tests/test_strategy.py)
- **Uncertainty.** The fixed receipt sample measures one chosen strategy on one instrument with modeled liquidity and costs. It cannot establish expected future returns. Later corrections can change a current chart overlay while account decisions retain their original observation versions.

## Part 4.2 · Browser failure and revised query

- **Question.** Why did the browser initially show an empty chart while the server was receiving Yahoo quotes?
- **Observed failure.** The larger SQLite history made `MarketStore.candles` take roughly four seconds per symbol. The four-symbol snapshot exceeded the browser's ten-second connection deadline. Browser inspection showed reconnecting status alongside working HTTP results.
- **Decision and artifact.** Add `heads_observation` in `server/schema.sql`. Its join index gives SQLite an indexed lookup from an observation to its accepted head. Existing records and IDs are preserved.
- **Verification.** The same local candle queries dropped to approximately 2–3 milliseconds per symbol. The browser then showed live quotes, both SMA values and the saved backtest. The first TypeScript build also caught an incompatible marker generic; the corrected explicit `ISeriesMarkersPluginApi<Time>` passed the Vue build.
- **Remaining uncertainty.** Query timings are local observations. Growth, hardware and network latency can change them. Future large-volume retention remains a separate concern.

## Part 4.2 · Student-recorded submission video

- **Instruction.** The student supplied a Kaltura recording and requested, “take parts of this to create the video ... the length needed.”
- **Artifact and decision.** The 167.424-second source was cut to 59.12 seconds using five chronological excerpts. Original narration covers SMA lengths, completed candles, pandas/accounting verification and subsequent-quote execution. The footage shows the chart, account metrics, equity curve, fills and decision table. [Media](../evidence/part-4-2-student-demo.mp4)
- **Verification.** FFprobe confirmed the duration and streams. FFmpeg decoded all audio and video without errors. Source scene ranges and the exported hash are recorded in [video verification](../evidence/part-4-2-video-verification.json).
- **Boundary.** The recorded backtests use the growing local market log and include cash-setting changes. Their results differ from the fixed historical sample used for stable numerical verification.

## 1. Required behavior and genuine live provenance

- **Intended change / instruction:** “The Part 4.1 deliverable must demonstrate live streaming.” “Make the data source, age, and feed status visible.”
- **Generated artifacts:** [Yahoo adapter](../server/yahoo.py), [FastAPI transport](../server/main.py), [Vue dashboard](../client/App.vue), [chart](../client/MarketChart.vue).
- **Observation / verification:** [Actual live verification](../evidence/live-verification.json) receives a new Yahoo quote and an applied candle revision over a real client WebSocket, then compares their IDs, provider timestamps, and values to SQLite through an independent connection. It also asserts the running Vue/FastAPI/SQLite stack and source quote freshness. [Browser evidence](../evidence/browser-qa.json) show the actual chart and volume.
- **Decision / relevant code:** Keep upstream pricing WebSocket and Chart OHLCV as separate channels. `YahooFeed.fetch_symbol` commits a normalized batch before `on_data`; FastAPI's callback publishes those committed results. Vue applies only accepted records to chart state.
- **Uncertainty:** Public Yahoo data can lag, stop, or be revised. A connected socket or refreshing display alone does not establish freshness; the UI checks source timestamps.

## 2. Framework mismatch — revised implementation approach

- **New instruction excerpt:** “Use the familiar Vue frontend, FastAPI backend, and SQLite database on localhost.”
- **Earlier result / failure:** The initial short Part 4.1 excerpt omitted the stack requirement. The first implementation used React/Express. The complete overview could not then be read through university authentication. That version met functional checks but failed the later-supplied stack requirement. [Historical implementation 0209507](https://github.com/abn54/Live-Marketstation-/commit/020950785a75f4e8d092203108a375f9387d667f) identifies the revised approach honestly.
- **Resulting artifacts:** `client/App.vue`, `client/MarketChart.vue`, `server/main.py`, `server/store.py`, `server/yahoo.py`, Python tests, and updated startup/docs. React/Express runtime files and dependencies were removed.
- **Verification:** [Migration preservation evidence](../evidence/migration-preservation.json) compares all columns of previously captured immutable rows with the existing database and checks schema version/integrity. [Python tests](../tests/) preserve the earlier behavioral contract, including numeric JSON compatibility. [Clean-checkout evidence](../evidence/clean-checkout.json) verifies the required stack without existing runtime files.
- **Decision / relevant generated code:** Preserve schema v1 and row IDs rather than resetting the database. `MarketStore._ingest_one` compares decoded market payloads so JavaScript `1` and Python `1.0` do not create false migration revisions. The submitted report points to the migrated version, not 0209507.
- **Uncertainty / ownership:** Passing agent-run checks does not replace the student's responsibility to review/explain the code. No claim is made that the initial framework choice was compliant.

## 3. TLS failure — diagnosis from actual channel evidence

- **Question:** Why did chart HTTP requests succeed while the Python pricing feed remained unavailable?
- **Observed failure:** `SSLCertVerificationError: unable to get local issuer certificate` was recorded in the stream's feed events. [Selected first-run observations](../evidence/migration-first-run.txt) retain a redacted excerpt, separate from the final passing output.
- **Changed artifact / relevant code:** `YahooFeed.stream_loop` supplies `ssl.create_default_context(cafile=certifi.where())` to the upstream connection. This uses trusted certificate roots and keeps hostname checking and `CERT_REQUIRED` enabled.
- **Verification:** The socket-path regression test asserts the SSL context's verification settings; [live evidence](../evidence/live-verification.json) separately establishes Yahoo pricing messages arrived after the revision.
- **Decision:** Use a known CA bundle rather than weakening TLS or relabeling cached quotes as live.
- **Remaining uncertainty:** Yahoo's service and the network can still fail. The UI exposes failure and retries; the certificate fix is not an availability guarantee.

## 4. Duplicate watermark and out-of-order observations

- **Instruction excerpt:** “Explain and test how duplicate, revised, and out-of-order observations are handled.”
- **Generated artifacts:** `MarketStore._ingest_one`, [schema](../server/schema.sql), [store tests](../tests/test_store.py).
- **Relevant code:** A duplicate adds a receipt referencing immutable content. Its newer `orderingTime` still advances `heads.ordering_time`. Otherwise, a slow differing response from an older request could incorrectly replace the newest unchanged fetch. Changed older payloads are retained as `superseded` with `applied=false`.
- **Verification:** Tests cover a newer duplicate followed by a slow older differing response, a legitimate newer return to an old value, completion followed by a late partial, source-time ordering of old quotes/minutes, and full replay reconstruction. These are deterministic injected cases, not claims that the captured Yahoo session naturally produced all those conditions.
- **Decision:** Preserve immutable arrival/revision history and accepted heads separately; use request start time as a local version-order token because Yahoo Chart supplies no reliable revision timestamp.
- **Uncertainty:** Equal-order quote corrections are arrival ordered, not exchange-sequenced. Completeness records whether the interval had ended at fetch time; later provider corrections remain possible.

## 5. First Python test failures and asynchronous cleanup

- **Intent:** Preserve the client/socket/storage contract during migration and test shutdown/retry behavior.
- **First observation:** The initial run had **2 failed, 26 passed**: WebSocket test context shutdown propagated cancellation, and one test read retry status before async subscription cleanup completed. [Redacted failure summary](../evidence/migration-first-run.txt).
- **Changed artifacts:** FastAPI endpoint cancellation/finally cleanup in `server/main.py`; the socket test in `tests/test_yahoo.py` waits for a retry-status event rather than relying on one event-loop tick.
- **Verification:** [Final test output](../evidence/test-results.txt) and clean-checkout results. The provider callback test checks that a row is already queryable when publish is invoked. FastAPI TestClient exercises a real ASGI WebSocket path, while live evidence uses a network socket to the running server.
- **Decision:** Make asynchronous lifecycle boundaries explicit. Do not weaken state assertions merely to make a timing-sensitive test pass.
- **Uncertainty:** Unit/integration tests inject provider messages; they do not establish external Yahoo availability. The separate live capture addresses that boundary.

## 6. Outage, replay, and final packaging

- **Instruction excerpts:** “including an unavailable-feed condition”; “upload only report.md”. The overview also requires tool/model disclosure and one combined 30–60 second demonstration/process video.
- **Artifacts:** Upstream pause and resume in `YahooFeed`, read-only `/api/replay`, Vue replay controls, [AI-USE.md](../AI-USE.md), this curated log, and the report.
- **Verification:** Live checks confirm both upstream channels become unavailable, no market records are generated during the pause, existing candles remain queryable, actual collection recovers, and receipt-order replay exactly reconstructs persisted candles without writes. Browser checks exercise playback, seeking, and returning to live.
- **Decision:** Show retained data with explicit outage/replay labels; submit one Markdown report linking public repository/commit, supporting evidence, and a single combined demo/process video. The student will include a design/verification decision in their own narration. No source files/ZIPs go to Canvas.
- **Remaining uncertainty:** The instructor's access to a future university submission is not established by public GitHub checks. Canvas upload remains a student action. No later assignment capabilities or student comprehension are claimed complete by this Part 4.1 implementation.

## 7. Closed-market final candle completeness

- **Instruction excerpt:** “A candle for the current interval is incomplete until that interval ends.”
- **Revised approach:** Earlier code waited for a later bar to appear before marking the final bar complete. That left a closed market's final bar marked forming even long after its minute ended. The historical SPY screenshot in the earlier commit exposed that limitation; the pasted overview clarified the intended interval semantics.
- **Changed code / verification:** `normalize_chart` now records `complete = source_time + 60000 <= request_started_at`. A regression test checks an ended final minute with no later bar; a current-minute test keeps its candle incomplete. The final closed-market screenshot shows the corrected state. Existing observations remain immutable; a later actual fetch creates the completeness revision.
- **Decision / uncertainty:** Completeness denotes interval end as observed at fetch time, not exchange-certified finality. Do not mutate a retained/replayed snapshot merely because the UI clock advances; source outages and later provider corrections remain visible.

## 8. Student recording replaces generated media

- **Intent:** The student chose to present and narrate the demonstration in their own voice.
- **Decision and artifacts:** Withdraw the generated MP4, transcript, media metadata, and assembler. Keep genuine market recordings, screenshots, tests, and the tool disclosure as evidence.
- **Verification:** The student's Kaltura recording was 3:14. The exported 58.92-second clip preserves the live chart, ledger, replay, outage and recovery, and the student's explanation of SQLite before WebSocket delivery. FFmpeg decoded both streams successfully. The [report](../report.md) links the clip.

## 9. Recording rehearsal and replay responsiveness

- **Instruction excerpt:** “make sure everyhting taht i eed to show works well”.
- **Observation:** At 556 CSS pixels, the ledger hid its revision and state columns offscreen. The browser loaded about 40,000 BTC receipts and took about 2.5 seconds to enter replay in one local run. The outage control was in the footer, away from the chart.
- **Decision and code:** `MarketStore.recent_replay` builds the chart checkpoint from accepted receipts before an 800-receipt window. The browser replays that window and the full log stays available through the existing API. Vue shows the revision and state in narrow ledger rows and places the outage action beside the chart. Reconnect waits for a receipt on the new Yahoo socket for the selected symbol.
- **Verification:** The [browser rehearsal](../evidence/demo-readiness.json) observed revised and duplicate candle rows at the original narrow width. Replay opened in about 1.1 seconds in the updated local run and kept the chart visible at restart. The intentional outage retained the chart. After reconnect, the live badge returned with a new source timestamp. The API regression test checks the checkpoint and window against persisted heads, including superseded and duplicate receipts.
- **Uncertainty:** The timings are local observations. Yahoo's next pricing message and candle update can take longer during another recording.

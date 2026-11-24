# Part 4.3 verification and outstanding evidence

Status on November 24, 2026: implementation, **76 Python tests, 8 voice-controller tests, Vue build, recorded-strategy verification, mocked AI verification, clean-checkout startup and observed GitHub Actions** passed. Successful live model/vision/audio evidence and the student's combined 30–60-second recording remain pending. Do not submit this work as complete yet.

## Repeatable local checks

Run `npm test`, `npm run build`, `npm run strategy:verify`, and `npm run ai:verify` from the repository root after the README's locked installs. Tests use memory/temporary SQLite; they do not contact Yahoo/OpenAI or modify the working database. [Test output](../evidence/part-4-3-tests.txt) · [Build output](../evidence/part-4-3-build.txt)

A fresh clone at source commit `331574169cc9565e3d5e814f5c4b77714a8c37e3`, without private env files, node_modules, a virtual environment, build output or the working database, completed locked installs and all checks. A separate production process served the built Vue client, exposed the expected HTTP/AI routes and a real FastAPI WebSocket snapshot, and correctly returned unavailable for an AI review without credentials instead of substituting a mock. The initial startup harness expected `#app`; it was corrected to the application's actual `#root` mount and startup was rerun. [Clean-checkout result](../evidence/part-4-3-clean-checkout.json) · [Selected clean-checkout output](../evidence/part-4-3-clean-checkout.txt)

[GitHub Actions succeeded for the same source](https://github.com/abn54/Live-Marketstation-/actions/runs/45297522907). The actual run is recorded in [CI evidence](../evidence/part-4-3-ci.json). Subsequent documentation/evidence/report changes are distinguished from that tested source.

`tests/test_ai.py` verifies strict schema/identity, finite confidence, SMA and confidence vetoes, hold, review-only behavior, idempotency, subsequent-quote fills and cash reconciliation, stale feed preflight, unavailable provider, changed controls/candle/outage during a request, late historical quotes, once-per-candle automation, restart persistence/disarming, chat/vision grounding and read-only behavior, origin/input validation, audio-session failure, redacted provider errors, strict outgoing schemas/image input, exhausted-credit classification and additive schema preservation.

`scripts/test-voice.mjs` runs the actual `client/voice.ts` controller with browser API doubles: connected session/transcripts/End cleanup, microphone denial, provider failure/reconnect, lost connection versus injected failure, late microphone permission after cancellation, session timeout, late autoplay rejection after End, and a provider `response.done` failure. Two added regression cases initially failed: the late autoplay callback changed an ended session to live, and a failed response left the UI live. Generation checking and explicit failed-response handling fixed both; the suite then passed. These are deterministic mocked browser-API checks, not a real microphone or live audio-provider observation.

[Mocked AI end-to-end evidence](../evidence/part-4-3-mocked-verification.json) uses a mock model, synthetic rising/falling prices, a fixed clock and in-memory SQLite. The automatic path queues/fills a buy and later sell; the final flat account has $8,017.10 cash/equity, −$1,982.90 realized P&L and $17.01 fees. Hold, invalid model response and provider outage leave the account unchanged. This establishes accounting/check behavior for known inputs, not live trading performance. It is not passed off as a Yahoo session.

## Actual browser observations

The actual Vue app displayed fresh Yahoo quotes, candlesticks/volume and completed-bar SMAs. The AI panel displayed the current candidate and a separate $10,000 account. Clicking Check decision reached the real provider, recorded its HTTP 429 rejection and left holdings/orders unchanged. Chat and actual chart-PNG submission likewise displayed provider unavailability rather than invented replies. [Chart input](../evidence/part-4-3-chart-input.png) is the real canvas image sent in the vision request, not proof that a model interpreted it.

The opt-in Yahoo outage control stopped real collection. An executable AI request was skipped before calling the model because the feed check failed. Reconnect restored the main live feed. The voice tab rendered its model/context description, microphone controls, remote audio player and explicit injected-failure control. Successful microphone/WebRTC conversation was not claimed while the API credit blocker remained. [Dashboard capture](../evidence/part-4-3-dashboard.jpg) · [Feed check](../evidence/part-4-3-feed-check.jpg)

The running working database passed `PRAGMA quick_check` and retained its existing market records and saved simulation runs. The additive migration regression compares the complete immutable market/current-head and saved-run rows before/after initialization of the new tables in a temporary database.

## Actual live-provider failure

A real HTTPS Responses call reached OpenAI and returned HTTP **429**, error type **`insufficient_quota`**, code **`credit_balance_exhausted`**, with a message that no credits remain. This is exhausted API credit, not a successful model response or a transient request-rate observation. The provider error classifier was revised to identify this code while keeping credentials/raw provider bodies out of public error responses. No further repeated live probes are needed until the balance/key changes.

The secure key-save widget had earlier returned not approved. No key was created through that flow. The student subsequently saved their own key in ignored `.env.local`; verification detected its presence without printing it. The file is not part of Git, frontend assets, screenshots or the report. Credentials/private account identifiers are excluded from curated evidence.

On November 24, checks initially skipped while the source was stale after the workstation resumed. Once current selected-symbol Yahoo messages and candles were available, the real decision endpoint was retried and still returned exhausted-credit unavailability. No model decision or simulated order was fabricated. That recheck is included in the live-provider artifact.

## Required remaining checks

1. Use a funded provider project. Capture successful structured decision and grounded chat replies with actual returned model/reply IDs, context and check results. Demonstrate an eligible simulated outcome (including a legitimate hold if conditions call for it); retain mocked buy/sell tests separately.
2. Submit the actual visible chart image and capture the live vision model's interpretation. Confirm that image identity and context are traceable.
3. Perform a real two-way spoken exchange through Start voice. Show microphone input, remote audio output/transcripts, End cleanup, injected session failure and reconnection. Mark any prerecorded/synthetic audio used for automated provider tests separately from live microphone observations.
4. Repeat the clean checkout/CI checks if implementation changes; current source `3315741` has already passed them. Update the final report with successful live evidence when it exists.
5. The student records one accessible **30–60-second** combined demonstration/process screencast showing the required AI modalities, checked simulated action/state and one design/verification decision. Detailed process belongs in the report/evidence log. No previous part's video is a substitute.

## Limits

Mocked passes cannot prove provider/model availability, voice quality, image understanding or resistance to every prompt injection. The context is bounded and frozen; voices must reconnect for newer data. Model confidence is not calibrated. The bot's regime-filtered long-only simulation omits market depth, partial fills, impact/taxes and guarantees of future performance. API quota, microphone permissions, browser autoplay/WebRTC and provider changes remain external dependencies. The local app has no multiuser authentication and is intended for loopback.

# Part 4.3 — AI data flow and execution design

This extension preserves the Vue 3/FastAPI/SQLite workstation and gives it a separate simulated AI account per symbol. Source observations remain genuine Yahoo data. AI cannot create market observations or send real brokerage orders. Part 4.2's crossover-only accounts/backtests remain separate.

## Market → context → checked decision → account

Yahoo pricing/Chart → atomic market observation/head/receipt commit → market WebSocket and chart. The AI service takes a bounded snapshot from those accepted database heads. A decision response is checked before an AI audit row and pending simulated order are committed together. Later applied, fresh Yahoo quote receipts drive the existing Decimal accounting engine. The browser reads account and audit results through the AI API.

`server/ai_provider.py` owns server-only authenticated HTTPS requests. `server/ai.py` owns snapshots, decisions, eligibility, automation and audit. `server/main.py` exposes the routes. `client/AIPanel.vue` renders controls/results; `client/MarketChart.vue` captures the real chart canvas. `server/voice.py` bridges live PCM, and `client/voice.ts` plus `client/audio-worklet.js` manage actual microphone resampling and remote playback. No mock provider is installed as a production fallback.

## Information sent to the model

Each context has a random `snapshotId`, capture time, symbol and receipt watermark. It includes the latest Yahoo quote and source/receipt timestamps, quote age, age since the latest completed candle ended, source/feed classification, up to 32 completed OHLCV candles, computed fast/slow SMA values, latest crossover, SMA candidate, simulated account, last six orders/fills, previous checked decision and execution assumptions. Indicator computation can use up to `max(80, slow+4)` fetched bars; the model receives the last 32 raw completed bars and the computed values. Forming candles are excluded from indicators and action eligibility.

The model does not receive the API key, environment files, local paths, microphone recordings from unrelated sessions, full SQLite history, browser cookies, or brokerage credentials. Provider instructions treat questions, chart text and prior explanations as data rather than authority to change execution rules. Gemini free-tier data-use terms apply to the bounded snapshot, questions, chart and transient speech; consult the official pricing/terms. SQLite keeps its own audit independently.

The default text/image model is `gemini-3.5-flash-lite`; the native live vision/speech model is `gemini-3.8-live`. The supported alternative speech model is `gemini-3.1-flash-live-preview`. Server-side `GEMINI_MODEL` / `GEMINI_LIVE_MODEL` settings are checked against explicit free-tier model allowlists. Requests require a private `GEMINI_API_KEY` and `GEMINI_FREE_TIER_CONFIRMED=true`, reflecting the user's confirmation of Free tier with billing disabled. No paid fallback or billing changes exist. The application cannot independently inspect cloud billing state. Eligibility and quotas can make the service unavailable even with a valid key. Requested model names and actual returned `modelVersion`/reply IDs are distinguished in evidence. Text/decision uses the supported GenerateContent REST API with `responseJsonSchema` for decisions. Vision uses Live `clientContent.parts.inlineData` with the question and actual PNG in one turn; its spoken response is transcribed into the displayed interpretation. Authentication is a header on a fixed Google host; the key is never embedded in URLs.

## SMA and AI relationship

For a flat account, fast SMA > slow SMA permits a **buy** candidate. For a long account, fast SMA < slow SMA permits a **sell** candidate. Otherwise the candidate is **hold**. Scale-aware equality counts as hold. The latest completed-bar crossover is included to explain when the regime changed. The bot can enter an existing regime; it does not require a crossover on the current minute. This is a disclosed change from Part 4.2's crossover-event-only strategy.

AI can confirm the candidate or veto with hold. It cannot choose the opposite side, resize the order, short an asset, change fees, or bypass account eligibility. Its explanation and confidence are model outputs, not validated financial truth or calibrated probabilities.

## Response contract and application checks

The strict JSON schema contains exactly `action` (buy/sell/hold), `symbol`, `snapshotId`, finite `confidence` in [0,1], and an 8–1200-character `reason`. Extra fields are forbidden. Pydantic validates the response again even though the provider was asked for structured output. Refusal, incomplete output and malformed envelopes are rejected.

For executable requests, preflight requires sufficient completed SMAs, an active streaming feed with available symbol candles and a matching selected-symbol quote seen in this server session, quote source age 0–60 seconds, completed-candle end age 0–180 seconds and no pending order. A fresh cached quote plus another symbol's connected socket is insufficient. Failed preflight is audited without calling the model.

After the network response, the server rechecks freshness/account eligibility and validates:

- Exact response symbol and snapshot identity.
- AI action is the SMA candidate or hold; non-hold confidence is at least 0.60.
- The account control generation is unchanged. Pause/start/restart invalidates in-flight replies.
- The latest completed observation ID and SMA candidate are unchanged, and the response is no more than 45 seconds old.
- There is no pending order, and this source candle has not already produced an AI order, including later revisions.

The request key makes a completed retry return its existing audit row instead of calling the provider or creating another order. Concurrent decision calls are rejected as busy. Read-only review still validates schema/identity/control context but never creates an order, even on stale saved data.

## Simulated execution and persistence

An accepted action records the input snapshot, returned model/reply ID, explanation, checks and final receipt watermark. The pending order's `decisionTime` is the checked response time, not the earlier input snapshot or candle close. Its cursor starts at the final watermark, so an earlier quote cannot fill it.

`PaperAccount.quote/fill` applies the Part 4.2 execution rules: use a later applied fresh quote, 95% cash buys, entire-position sells, adverse slippage 5 bps, commission 10 bps, eight-decimal quantities and cent-rounded cash/fees. A quote must be fresh relative to wall time and not locally received before the checked decision. Five-minute expiry uses the existing quote-processing rule. Holds and rejected/unavailable decisions do not alter holdings. The AI account is marked from quote receipts and does not run the SMA account's automatic crossover-order method.

Automation is off by default. Activation allows at most one attempt per new completed source minute and stops after 10 attempts or 10 minutes. A provider outage disarms it. Pause cancels pending orders and invalidates late model replies. Restart preserves the account/audit while disarming automation and canceling pending orders. Quotes can continue marking the saved account. Existing historical orders, market receipts and Part 4.2 runs are preserved.

## SQLite additions

Initialization extends existing schema v1 additively with `CREATE TABLE IF NOT EXISTS`; it does not rewrite existing market rows or reset their identities.

| Table         | Fields and role                                                                                                                                                                                     |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai_bots`     | `id`, unique `symbol`, `created_at`, `running`, `generation`, `config_json`, `state_json`. State holds the existing accounting engine's account/orders/fills, receipt cursor and automation limits. |
| `ai_activity` | Monotonic `id`, unique nullable `request_key`, nullable `bot_id` FK, `symbol`, `kind`, `created_at`, `status`, `context_json`, `response_json`. Immutable decision/chat/vision/audio events.        |

`ai_activity_symbol(symbol,id DESC)` supports recent activity. Decisions commit their audit entry and updated account/pending order in one SQLite transaction under the same store lock used by ingestion. Subsequent accounting saves its receipt cursor and account state together. Chat/vision/audio do not mutate the account. Full chart-image bytes, raw microphone audio, transport connection details and credentials are not stored in the audit. PNG dimensions/size/SHA-256 identify a submitted image. Audio stores session negotiation/status metadata and labels browser-reported events separately from direct provider observations.

## Grounded interaction

**Chat:** receives the server context and up to six previous conversation messages from the UI (API allows at most eight). The model explains the current account/decision, gaps and uncertainty. Conversation history is untrusted and supplies no execution capability.

**Vision:** the browser obtains a PNG from the actual chart instance, including rendered candlesticks/SMAs/markers. The server checks data-URL type, byte limit, PNG header and bounded dimensions, then sends real image input and numeric context. Vision explicitly uses Gemini Live and displays output transcription; it does not retry failed GenerateContent vision calls silently or claim generated audio proves microphone capture. It stores a fingerprint rather than image data. The image is a frozen visual observation and can differ slightly from the newer server context. Visual estimates cannot establish exact execution prices or prove strategy quality.

**Live voice:** microphone → AudioWorklet → 16-kHz mono PCM16 → same-origin `/ws/ai/voice?symbol=...` → authenticated Gemini Live WebSocket → 24-kHz returned PCM → scheduled browser playback/visible audio control. The server waits for `setupComplete`, records setup separately from speech, and forwards binary audio and transcript/turn/interruption controls. The private key is a server-only authentication header. The provider receives a frozen bounded context, brief English-response instructions and no tools. Reconnect captures fresh context.

Browser resampling handles 44.1/48-kHz devices, clipping and exact 100-ms blocks. Playback queues are bounded; interruptions clear queued speech. The server permits one session at a time, caps frames and session duration (two minutes), and records byte/turn counts and whether transcripts were observed. Raw audio and transcript text are not stored in SQLite. End, failure, tab/symbol change or page exit releases microphone, worklet, sockets, playback and AudioContext; generation guards also release late permission grants. A setup ACK alone is not proof of two-way speech. The opt-in evidence client streams a clearly labeled test WAV through this same bridge and requires both spoken-input transcription and returned audio/transcript.

## Failure and verification boundaries

Provider transport errors/timeouts, HTTP errors, empty/refused/incomplete replies, invalid decisions and changed context are visibly unavailable/rejected, with no fallback model/prices. Public errors omit credentials and upstream bodies. Gemini free-tier quota is distinguished from other service errors; no error enables paid fallback. Same-origin checks cover state-changing routes, inputs and uploads are bounded, and TLS verification remains enabled. This is a trusted localhost tool, not an authenticated multiuser service.

The production path never inserts a mock decision to make a demonstration appear to work. Unit/API/voice-controller tests and `ai:verify` explicitly inject providers, prices and browser APIs. They establish implementation behavior under those inputs, not live model quality or real microphone audio. Live-service observations and their current limits are in [verification](part-4-3-verification.md).

## Large-history responsiveness

The append-only observation/receipt logs permit exact incremental status totals. `MarketStore.stats` rebuilds once after opening and thereafter aggregates rows above saved IDs, retaining revisions/duplicates/superseded counts. An initial version rescanned the growing log for every pricing message and starved the event loop; the revised path preserves all records and reduces repeated status work. Receipt-first `CROSS JOIN` queries retain chronological cursor order without a full symbol-history sort. Regression tests compare totals through duplicates/revisions/out-of-order receipts and reopen. No record reset or retention policy was introduced.

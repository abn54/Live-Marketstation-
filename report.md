# IST 402 — Assignment 4, Part 4.3

**AI-Assisted Automated Trading and Interaction**

Student identifier **abn54** · November 23, 2026

**WORK IN PROGRESS — NOT READY TO SUBMIT.** The application and local checks are implemented, but the configured OpenAI API project returned `credit_balance_exhausted`. Successful live model/vision/audio evidence and the student's new 30–60-second combined demonstration/process video are pending. Mocked passes are not presented as live integration evidence.

- **Repository:** [abn54/Live-Marketstation-](https://github.com/abn54/Live-Marketstation-).
- **Implementation/evidence commit:** to be pinned after the final source and clean-checkout checks.
- **Part 4.3 video:** **pending**. The Part 4.2 video does not demonstrate this part.

## Completed implementation

The Vue 3/FastAPI/SQLite workstation retains genuine Yahoo streaming quotes, candlesticks/volume, completed-bar SMA 9/21 overlays, durable observations/replay, and the separate Part 4.2 simulations/backtests. Part 4.3 adds a server-only decision API, a persistent opt-in AI simulated account, grounded chat, actual chart-image input to a vision-language model, and a two-way Realtime WebRTC audio client.

`POST /api/ai/decision` snapshots recent accepted market observations, source/receipt ages, completed indicators/latest crossover, SMA candidate, simulated account, recent orders/fills and previous checked decision. OpenAI is asked for strict buy/sell/hold JSON with symbol/snapshot ID, bounded confidence and reason. The exact context, response, explanation and application checks are inspectable in the UI and audited in SQLite.

The SMA regime limits which action is possible: fast > slow while flat permits buy; fast < slow while long permits sell; otherwise hold. AI can approve the permitted candidate or hold. The latest crossover explains the current regime. Unlike Part 4.2, this bot can enter an already-established regime rather than requiring a crossover on the current minute.

The server revalidates the schema, symbol/snapshot identity, finite confidence, SMA agreement, fresh source data, unchanged controls/completed candle and account eligibility. Actions need confidence >=0.60 and can occur at most once per completed source candle. Confidence is a model self-report, not a calibrated financial probability. Invalid, stale, unavailable and held outcomes leave positions unchanged.

Valid actions queue a simulated order after the checked response, committing audit and pending account state atomically. A later fresh applied Yahoo quote fills it using the existing Decimal accounting engine, 95% cash allocation, 10 bps commission and 5 bps slippage. The account tracks cash, position, equity, realized/unrealized P&L, fees and order/fill outcomes. Automation is off by default, one attempt per completed minute, capped at 10 attempts/10 minutes. Pause/restart invalidates late replies and cancels pending orders; provider failure disarms the bot. Review-only calls cannot trade.

## AI-assisted interaction and context

**Chat** receives the server market/indicator/account snapshot, previous checked decision, recent simulated orders/fills and bounded conversation history. It explains the workstation without order tools.

**Chart vision** sends a PNG captured from the actual visible Lightweight Charts instance, with numeric context, to the image-capable model. The UI previews the exact image. SQLite records its hash/dimensions rather than raw bytes. Visual estimates and the later numeric snapshot can differ in time and cannot directly execute a trade.

**Live voice** sends microphone audio and receives remote audio through OpenAI Realtime WebRTC. FastAPI authenticates SDP negotiation server-side without exposing the API key. The session receives a frozen workstation snapshot; transcript events display speech. It has no trading tools. End, failure, tab/symbol change, page exit or the two-minute limit releases microphone/transport resources. Reconnect refreshes context. This implementation uses live API speech, not browser text-to-speech; successful actual two-way exchange remains unverified while credits are exhausted.

The configured text/image model is `gpt-5.4-mini`; the configured speech model is `gpt-realtime-2.1`. These are requested models, not claims of successfully observed responses. The key stays in ignored server-side configuration. Yahoo itself needs no credentials.

## Verification results and evidence boundaries

| Evidence                          | Result and meaning                                                                                                                                                                                                                                                                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local automated checks            | Python behavioral/API tests, the actual voice controller with browser API doubles, Vue typecheck/build, existing recorded-strategy verification and mocked AI end-to-end checks passed in the development checkout. Final exact output and clean-checkout result will be pinned before submission.                                                   |
| Mocked complete bot path          | Synthetic rising/falling prices and a mock provider produced automatic checked buy/sell orders and subsequent-quote fills in memory. Final flat cash/equity is $8,017.10, realized P&L −$1,982.90, fees $17.01. Holds, invalid replies and an injected unavailable provider do not create further orders. This is not live market/model performance. |
| Genuine Yahoo/browser path        | The Vue browser showed fresh Yahoo quote/candle data and SMA values. The real provider's rejection left the $10,000 AI account unchanged. An intentional feed outage caused a failed feed check and skipped the request before model invocation; reconnect restored live source status.                                                              |
| Actual chart input                | The browser captured and submitted the actual chart PNG. The live provider returned quota failure; successful interpretation is pending.                                                                                                                                                                                                             |
| Invalid/unavailable/audio failure | Injected tests verify invalid schema/identity/confidence, stale context, pause/revision/outage during a call, API errors, microphone denial, disconnected transport, timeout, cleanup and reconnect. These are marked mocked checks, not live audio observations.                                                                                    |
| Real OpenAI request               | HTTP 429, type `insufficient_quota`, code `credit_balance_exhausted`. This establishes an actual unavailable-provider condition and does not establish successful AI decision/chat/vision/audio integration.                                                                                                                                         |
| Clean checkout / CI               | Pending final snapshot verification and observed Actions run.                                                                                                                                                                                                                                                                                        |
| Combined demo/process recording   | Pending student's accessible 30–60-second Part 4.3 recording.                                                                                                                                                                                                                                                                                        |

## Process and design decisions

The student supplied the assignment and asked Codex to perform the implementation. Codex generated/revised the source, tests, UI, docs and report, inspected official provider documentation and exercised the real browser. The important design choice was to treat AI as a checked veto/confirmation of an SMA candidate, with deterministic sizing/accounting and no direct trading tools for conversations. The checked response time and final receipt watermark prevent retroactive execution at a quote already visible to the model.

A secure key-save confirmation repeatedly returned not approved. No key was created through that flow. The student subsequently saved their own key privately, and presence was checked without printing it. Real provider probes then exposed exhausted credit. The initial generic HTTP-429 handling was revised to distinguish `credit_balance_exhausted` from a transient rate limit; a regression test covers that distinction. The report remains explicitly pending instead of replacing live evidence with synthetic successes.

Browser verification also exposed an initial voice-status message claiming a session had stopped when the user merely switched between non-voice tabs. The watcher was narrowed to leaving the actual voice tab. Voice lifecycle tests check that late microphone permission cannot revive an ended session. Full prompts/chats, credentials and private account/browser details are excluded from Git.

The coding agent is disclosed as Codex; its known environment identifies the GPT-6 family, without an asserted exact deployed build. No subagents were used. The product's model settings are separate from the coding-agent identity. The student must review and be able to explain the generated application.

## Startup, persistence and limitations

The README documents Python >=3.12, Node >=24, `.venv`, locked dependency installation, `npm ci`, `npm run db:init`, and `npm run dev`; production uses `npm run build` and `npm start`. Initialization additively creates `ai_bots` and `ai_activity` without resetting existing market records or simulation runs. The audit and pending order commit together, and account state includes a receipt cursor. Credentials, SQLite/WAL files, private recording notes and build outputs are excluded from Git.

Model output can be wrong; prompt instructions and schema checks do not prove financial correctness or prevent every misleading explanation. Snapshots are bounded/frozen, images may lag numeric values, and voice must reconnect for updated context. The account is a long-only full-fill simulation and omits depth, partial fills, taxes and impact. Live calls depend on funded provider access, microphone permission, browser WebRTC/autoplay and external services. Mocked checks cannot establish live model quality, vision understanding or audio usability. This trusted localhost application has no public multiuser authentication or real broker integration.

Supporting documents: README; agent instructions; Part 4.3 design/context/schema; verification notes; AI/tool disclosure; curated evidence log; automated tests; mocked verification JSON; actual provider/browser evidence. Links will be pinned to the implementation/evidence snapshot before submission.

When complete, upload **only `report.md`** to Canvas. Keep source/evidence/video in the linked repository. **Do not submit this pending draft yet.**

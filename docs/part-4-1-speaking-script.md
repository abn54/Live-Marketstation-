# Part 4.1 — your spoken demonstration

Aim for **50–60 seconds**, with your own voice and the working app on screen. This is one combined demonstration/process video. The directions below are not spoken lines.

## What to say

> This is my Part 4.1 market workstation, using Vue, FastAPI, and SQLite.
>
> Yahoo Finance streams live quotes. One-minute candles and volume refresh every fifteen seconds. The source, age, and feed status are visible.
>
> The ledger preserves observation IDs, source and receipt times, revisions, and candle completeness. Duplicates get separate receipts; older responses cannot overwrite newer data.
>
> Updates commit to SQLite before broadcasting over WebSockets.
>
> Replay reads stored observations without changing the database.
>
> Disconnecting Yahoo marks the feed unavailable while keeping the chart. Reconnecting restores live collection.
>
> A TLS failure was fixed using trusted certificates. Twenty-nine tests, thirteen live checks, and clean-checkout verification passed.
>
> Yahoo can be delayed or rate limited. My report links the repository, commit, disclosure, and evidence.

## What to show while speaking

| Approximate time | On-screen action |
| --- | --- |
| 0–12s | Start with **BTC-USD** and **Live** selected. Show the moving quote, candlesticks/volume, and **Feed health** source/age/status. |
| 12–27s | Scroll to **Observation ledger**. Point to receipt identity, source/receipt times, revision, and duplicate/revised state. Open **Data pipeline** while explaining SQLite-before-WebSocket delivery. |
| 27–35s | Click **Replay** and let playback advance briefly so **RECORDED REPLAY** and its controls are visible. |
| 35–47s | Click **Live**, then **Demonstrate feed outage**. Show the unavailable channels and retained chart. Click **Reconnect Yahoo feed**. |
| 47–60s | While genuine quotes resume, say the failure, verification, and limitation lines. End with the dashboard or report/evidence links. |

Rehearse once and keep the final recording between **30 seconds and 1 minute**. The script is approximately 120 written words, depending on how numbers/acronyms are spoken. Use a natural pace and do not spend extra seconds reading the interface labels aloud.

## Prepare the app

Choose BTC-USD and wait for a genuine **LIVE FEED** before recording. The footer's outage buttons require demo controls. For a future restart, stop the existing server first, then run:

```sh
ENABLE_DEMO_CONTROLS=true npm start
```

Use `npm run dev` instead of `npm start` if you are developing. The production build and dependencies are already prepared in this workspace. If the server has just reconnected, allow the next actual pricing message to arrive; a waiting status during reconnection is expected.

## Rubric coverage

- **Functionality/integration:** live Yahoo → FastAPI → SQLite → WebSocket → Vue chart, plus replay and outage/recovery.
- **Comprehension/correctness:** source versus receipt time, revisions/completeness, duplicate and out-of-order rules, and commit before broadcast.
- **Process/verification:** one actual revised approach (TLS trusted-root fix), recorded tests/live checks, and supporting evidence/disclosure.
- **Testability/limits/UX:** clean-checkout verification, visible age/failure states, and Yahoo delay/rate-limit limitations.

The script does not claim indicators, trading, backtesting, chatbot, vision, or live-audio AI; these are later assignment parts. It does not claim that you personally ran the agent's checks or independently authored every generated line. Read the linked design and evidence notes so you can explain these statements in your own words.

## After you record

Upload your video somewhere the instructor can access, add its actual link to `report.md`, and check that it plays without requiring access the instructor does not have. **Only `report.md` goes to Canvas.** The generated narrated demo was withdrawn at your request; there is no replacement video link yet.

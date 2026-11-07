# Combined Part 4.1 demonstration/process video

52-second narrated edited capture of the actual **Vue 3 + FastAPI + SQLite** application. Browser captures are sampled at two per second and encoded at 24 fps. No source values, chart content, counters, or statuses are fabricated. Pauses between scenes are removed, so UTC time may jump. Narration is synthesized using macOS Samantha, not the student's voice. The 16–24 second scene identifies a verification/design decision; the report and curated log explain the revised approach and relevant generated code.

**00–10s.** Vue and FastAPI power this dashboard. Actual Yahoo quotes and candlesticks update with volume, source times, data ages, and feed status.

**10–16s.** The ledger preserves identities, source and receipt times, revisions, duplicate arrivals, and candle completeness.

**16–24s.** Verification checks commit before broadcast. Newer duplicates advance the watermark, preventing older responses from overwriting current candles.

**24–32s.** Disconnecting the real upstream feed marks both channels unavailable. Collection stops, observation age increases, and stored candles remain available.

**32–38s.** Reconnecting resumes Yahoo collection. The dashboard waits for fresh messages; the database remains intact.

**38–52s.** Recorded replay reads SQLite receipts in their original order. Here are playback, pause, seeking to the end, and restarting at a different speed. The recording is labeled, while live collection continues independently.

# Part 4.1 demo transcript

45-second narrated, edited capture of the real running application. Browser screenshots were captured at two per second and encoded at 24 fps. No prices, charts, counters, or statuses were generated or replaced. Pauses between scenes were removed; the on-screen UTC clock therefore jumps between scenes. Narration uses the macOS Samantha voice.

**00–12s.** This is Marketstation with actual Yahoo Finance data. Quotes stream through the backend WebSocket. One minute candlesticks and their reported volume refresh separately. Source, age, and feed health stay visible.

**12–17s.** The ledger shows persisted receipt identities, source and receipt times, and revisions.

**17–22s.** Each observation commits to SQLite before the backend broadcasts it to the chart.

**22–30s.** Disconnecting the real upstream feed marks both channels unavailable. Collection stops, observation age increases, and stored candles remain available.

**30–35s.** Reconnecting restores actual Yahoo data without discarding any of the persistent records.

**35–45s.** Recorded replay reads the SQLite receipt log. Playback and seeking preserve observation order and revisions. The recording is clearly labeled, and live collection continues independently.

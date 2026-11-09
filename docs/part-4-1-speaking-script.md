# Part 4.1 recording script

Read the quoted lines **word for word**. Follow the click cues silently while you speak. Start on **BTC-USD → Live** with **Yahoo source live** visible. Aim for **50–58 seconds** in one recording.

### 0–12 seconds · Live chart

Point to the candles, the volume bars at the bottom of the chart, and **Feed health** on the right.

> Yahoo Finance streams live Bitcoin quotes. TradingView shows one-minute candles and volume, refreshed every fifteen seconds. Feed health shows the source, data age, and status.

### 12–25 seconds · SQLite and the data path

Click **View observation ledger**. Point at a candle row marked **forming** or **complete**, with a revision such as **v2**. Click **Data pipeline** beside the ledger as you say the second sentence.

> The ledger shows observation IDs, source and receipt times, revisions, and candle completion. FastAPI saves updates in SQLite before sending them to Vue over WebSockets, so chart updates are traceable.

### 25–40 seconds · Duplicates, revisions, and replay

Click the clock icon in the left sidebar, labeled **Recorded replay**. Point to the **RECORDED** label and the counter advancing below the chart.

> Duplicates get separate receipts. Changed values create revisions. Older responses arriving late cannot overwrite newer data. Tests cover all three. Replay reads saved records in receipt order.

### 40–58 seconds · Outage and recovery

Click **Live**, then **Demonstrate feed outage** beside the chart. Point to **Yahoo unavailable · saved chart** and the candles still on screen.

> I’m disconnecting Yahoo to demonstrate an outage. The feed shows unavailable, and the saved candles stay visible. I’ll reconnect now.

Click **Reconnect Yahoo feed**. When **Yahoo source live** returns, say:

> A fresh quote confirms recovery.

## What the report covers

The spoken SQLite sentence explains the design decision required by Section 6. The report and its linked evidence cover the detailed test results, setup and schema, the TLS failure and fix, the public GitHub commit, AI disclosure, the evidence log, and limitations. Once you have your 30–60 second recording, send the accessible video link for the report.

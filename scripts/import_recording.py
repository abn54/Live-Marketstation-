"""Import genuine normalized receipts without relabeling them as live."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from server.store import MarketStore

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
recording = json.loads(
    Path(
        sys.argv[1] if len(sys.argv) > 1 else "evidence/btc-recording.json"
    ).read_text()
)
if recording.get("formatVersion") != 1 or not isinstance(
    recording.get("records"), list
):
    raise ValueError("Unsupported recording")
store = MarketStore(os.getenv("DATABASE_PATH", "./data/market.sqlite"))
try:
    for r in recording["records"]:
        o = r["observation"]
        keys = (
            ("open", "high", "low", "close", "volume", "complete")
            if o["kind"] == "candle"
            else (
                "price",
                "currency",
                "dayVolume",
                "changePercent",
                "exchange",
                "marketHours",
            )
        )
        store.ingest_batch(
            [
                dict(
                    source=o["source"],
                    kind=o["kind"],
                    symbol=o["symbol"],
                    interval=o["interval"],
                    sourceTime=o["sourceTime"],
                    receivedAt=r["receivedAt"],
                    orderingTime=r.get("orderingTime", o["orderingTime"]),
                    payload={k: o.get(k) for k in keys},
                )
            ]
        )
    print(
        f"Imported {len(recording['records'])} recorded receipts from {recording['source']}; historical data is never relabeled live."
    )
    print(store.stats())
    print({"integrity": store.db.execute("PRAGMA integrity_check").fetchone()[0]})
finally:
    store.close()

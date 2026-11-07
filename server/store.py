"""SQLite audit log and accepted-current projection; compatible with schema v1."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from pathlib import Path

MAX_SAFE_INTEGER = 2**53 - 1


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_observation(o):
    if o.get("kind") not in ("candle", "quote") or not re.fullmatch(
        r"[A-Z0-9^=.\-]{1,24}", o.get("symbol", "")
    ):
        raise ValueError("Invalid observation identity")
    if o.get("source") not in ("yahoo-chart", "yahoo-stream"):
        raise ValueError("Invalid observation source")
    for key in ("sourceTime", "receivedAt", "orderingTime"):
        value = o.get(key)
        if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
            raise ValueError(f"Invalid {key}")
    if o["sourceTime"] > o["receivedAt"] + 300_000:
        raise ValueError("Source timestamp is too far in the future")
    p = o["payload"]
    if o["kind"] == "candle":
        if o["interval"] != "1m" or o["sourceTime"] % 60_000:
            raise ValueError("Candle must be aligned to one minute")
        values = [p.get(k) for k in ("open", "high", "low", "close")]
        if not all(finite(v) and v > 0 for v in values):
            raise ValueError("Invalid OHLC")
        if p["high"] < max(values) or p["low"] > min(values):
            raise ValueError("Invalid OHLC bounds")
        if p.get("volume") is not None and (not finite(p["volume"]) or p["volume"] < 0):
            raise ValueError("Invalid volume")
        if type(p.get("complete")) is not bool:
            raise ValueError("Missing candle completeness")
    elif o.get("interval") != "tick" or not finite(p.get("price")) or p["price"] <= 0:
        raise ValueError("Invalid quote")


def hydrate(row):
    if row is None:
        return None
    return dict(
        id=row["id"],
        logicalId=row["logical_id"],
        revision=row["revision"],
        source=row["source"],
        kind=row["kind"],
        symbol=row["symbol"],
        interval=row["interval"],
        sourceTime=row["source_time"],
        receivedAt=row["received_at"],
        orderingTime=row["ordering_time"],
        **json.loads(row["payload_json"]),
    )


class MarketStore:
    def __init__(self, path="./data/market.sqlite"):
        if str(path) != ":memory:":
            Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(
            str(path), isolation_level=None, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 1:
            self.db.close()
            raise ValueError(
                "Database is newer than supported schema v1; explicit migration required"
            )
        self.db.executescript(
            "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL;"
        )
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())

    def ingest_batch(self, observations):
        for o in observations:
            validate_observation(o)
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                result = [self._ingest_one(o) for o in observations]
                self.db.execute("COMMIT")
                return result
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _ingest_one(self, o):
        logical_id = ":".join(
            str(o[k]) for k in ("source", "kind", "symbol", "interval", "sourceTime")
        )
        payload_json = json.dumps(
            o["payload"], sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        fingerprint = hashlib.sha256(payload_json.encode()).hexdigest()
        head = self.db.execute(
            "SELECT o.*,h.ordering_time AS head_order FROM heads h JOIN observations o ON o.id=h.observation_id WHERE h.logical_id=?",
            (logical_id,),
        ).fetchone()
        # Semantic equality also accepts existing JS-written numeric JSON (1 vs
        # 1.0), preserving old row IDs without rewriting immutable observations.
        existing = (
            head if head and json.loads(head["payload_json"]) == o["payload"] else None
        )
        if existing is None and head and o["orderingTime"] < head["head_order"]:
            for row in self.db.execute(
                "SELECT * FROM observations WHERE logical_id=? ORDER BY id DESC",
                (logical_id,),
            ):
                if json.loads(row["payload_json"]) == o["payload"]:
                    existing = row
                    break
        applied = False
        if existing:
            observation_id, disposition = existing["id"], "duplicate"
        else:
            revision = self.db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM observations WHERE logical_id=?",
                (logical_id,),
            ).fetchone()[0]
            observation_id = self.db.execute(
                "INSERT INTO observations(logical_id,revision,source,kind,symbol,interval,source_time,received_at,ordering_time,payload_hash,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    logical_id,
                    revision,
                    o["source"],
                    o["kind"],
                    o["symbol"],
                    o["interval"],
                    o["sourceTime"],
                    o["receivedAt"],
                    o["orderingTime"],
                    fingerprint,
                    payload_json,
                ),
            ).lastrowid
            applied = head is None or o["orderingTime"] >= head["head_order"]
            disposition = (
                "superseded" if not applied else "revised" if head else "inserted"
            )
        # Even a duplicate from a newer request advances the ordering watermark.
        if applied or (existing and o["orderingTime"] >= head["head_order"]):
            self.db.execute(
                "INSERT INTO heads VALUES (?,?,?) ON CONFLICT(logical_id) DO UPDATE SET observation_id=excluded.observation_id,ordering_time=excluded.ordering_time",
                (logical_id, observation_id, o["orderingTime"]),
            )
        receipt_id = self.db.execute(
            "INSERT INTO receipts(observation_id,received_at,ordering_time,disposition,applied) VALUES (?,?,?,?,?)",
            (
                observation_id,
                o["receivedAt"],
                o["orderingTime"],
                disposition,
                int(applied),
            ),
        ).lastrowid
        return dict(
            receiptId=receipt_id,
            receivedAt=o["receivedAt"],
            disposition=disposition,
            applied=applied,
            observation=hydrate(
                self.db.execute(
                    "SELECT * FROM observations WHERE id=?", (observation_id,)
                ).fetchone()
            ),
        )

    def candles(self, symbol, limit=360):
        with self.lock:
            rows = self.db.execute(
                "SELECT o.* FROM heads h JOIN observations o ON o.id=h.observation_id WHERE o.kind='candle' AND o.symbol=? ORDER BY o.source_time DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
            return [hydrate(r) for r in reversed(rows)]

    def quote(self, symbol):
        with self.lock:
            return hydrate(
                self.db.execute(
                    "SELECT o.* FROM heads h JOIN observations o ON o.id=h.observation_id WHERE o.kind='quote' AND o.symbol=? ORDER BY o.source_time DESC,o.id DESC LIMIT 1",
                    (symbol,),
                ).fetchone()
            )

    def recent(self, symbol, limit=12):
        with self.lock:
            rows = self.db.execute(
                "SELECT r.id AS receipt_id,r.disposition,r.received_at AS receipt_time,o.* FROM receipts r JOIN observations o ON o.id=r.observation_id WHERE o.symbol=? ORDER BY r.id DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
            return [
                dict(
                    **hydrate(r),
                    receiptId=r["receipt_id"],
                    disposition=r["disposition"],
                    receiptTime=r["receipt_time"],
                )
                for r in rows
            ]

    def replay(self, symbol, *, after=0, until=MAX_SAFE_INTEGER, limit=500):
        with self.lock:
            rows = self.db.execute(
                "SELECT r.id AS receipt_id,r.received_at AS receipt_time,r.disposition,r.applied,r.ordering_time AS receipt_ordering_time,o.* FROM receipts r JOIN observations o ON o.id=r.observation_id WHERE o.symbol=? AND r.id>? AND r.id<=? ORDER BY r.id LIMIT ?",
                (symbol, after, until, limit),
            ).fetchall()
            return [
                dict(
                    receiptId=r["receipt_id"],
                    receivedAt=r["receipt_time"],
                    orderingTime=r["receipt_ordering_time"],
                    disposition=r["disposition"],
                    applied=bool(r["applied"]),
                    observation=hydrate(r),
                )
                for r in rows
            ]

    def stats(self):
        with self.lock:
            observations = self.db.execute(
                "SELECT COUNT(*) AS observations,COALESCE(SUM(revision>1),0) AS revisions FROM observations"
            ).fetchone()
            receipts = self.db.execute(
                "SELECT COUNT(*) AS receipts,COALESCE(SUM(disposition='duplicate'),0) AS duplicates,COALESCE(SUM(disposition='superseded'),0) AS superseded,COALESCE(MAX(id),0) AS lastReceiptId FROM receipts"
            ).fetchone()
            candles = self.db.execute(
                "SELECT COUNT(*) FROM heads h JOIN observations o ON o.id=h.observation_id WHERE kind='candle'"
            ).fetchone()[0]
            return dict(
                **dict(observations),
                **dict(receipts),
                candles=candles,
                journalMode=self.db.execute("PRAGMA journal_mode").fetchone()[0],
            )

    def event(self, channel, state, detail, now):
        with self.lock:
            self.db.execute(
                "INSERT INTO feed_events(received_at,channel,state,detail) VALUES (?,?,?,?)",
                (now, channel, state, detail),
            )

    def events(self, limit=10):
        with self.lock:
            return [
                dict(r)
                for r in self.db.execute(
                    "SELECT * FROM feed_events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            ]

    def close(self):
        with self.lock:
            self.db.close()

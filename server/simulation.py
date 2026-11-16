"""Durable paper sessions and frozen receipt-order historical experiments."""

import json
import time
import uuid

from .strategy import PaperAccount

MAX_RECEIPTS = 500_000


class Simulations:
    def __init__(self, store):
        self.store = store

    def _consume(self, account, until, warmup=False):
        count = 0
        while account.state["lastReceiptId"] < until:
            page = self.store.replay(
                account.config["symbol"],
                after=account.state["lastReceiptId"],
                until=until,
                limit=2000,
            )
            if not page:
                break
            for receipt in page:
                account.process(receipt, warmup=warmup)
            count += len(page)
            if count > MAX_RECEIPTS:
                raise ValueError("This experiment exceeds 500,000 symbol receipts")
        account.state["lastReceiptId"] = until

    def create(self, config):
        # The same lock protects ingestion and run checkpoints. Commit account
        # state, orders, fills and last receipt together in one JSON snapshot.
        with self.store.lock:
            if config["mode"] == "paper":
                running = self.store.db.execute(
                    "SELECT id,config_json FROM simulation_runs WHERE symbol=? AND status='running'",
                    (config["symbol"],),
                ).fetchone()
                if running:
                    if json.loads(running["config_json"]) == config:
                        return self.get(running["id"])
                    raise ValueError(
                        "Pause the existing paper account before changing its settings"
                    )
            until = self.store.stats()["lastReceiptId"]
            account = PaperAccount(config)
            self._consume(account, until, warmup=config["mode"] == "paper")
            if account.state["completedBars"] < config["slow"] + 1:
                raise ValueError(
                    "Not enough completed candles. Import the genuine recording or collect more data."
                )
            if config["mode"] == "paper":
                account.state["equity"] = []
            run_id = uuid.uuid4().hex
            self.store.db.execute(
                "INSERT INTO simulation_runs VALUES (?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    config["mode"],
                    "running" if config["mode"] == "paper" else "finished",
                    config["symbol"],
                    int(time.time() * 1000),
                    until,
                    json.dumps(config),
                    json.dumps(account.state, allow_nan=False),
                ),
            )
            return self.get(run_id)

    def _sync(self, row, until):
        account = PaperAccount(
            json.loads(row["config_json"]), json.loads(row["state_json"])
        )
        if row["status"] == "running":
            self._consume(account, until)
            self.store.db.execute(
                "UPDATE simulation_runs SET state_json=?, until_receipt=? WHERE id=?",
                (json.dumps(account.state, allow_nan=False), until, row["id"]),
            )

    def sync(self):
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT * FROM simulation_runs WHERE status='running'"
            ).fetchall()
            if not rows:
                return
            until = self.store.stats()["lastReceiptId"]
            self.store.db.execute("BEGIN IMMEDIATE")
            try:
                for row in rows:
                    self._sync(row, until)
                self.store.db.execute("COMMIT")
            except BaseException:
                self.store.db.execute("ROLLBACK")
                raise

    def get(self, run_id):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM simulation_runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            config, state = json.loads(row["config_json"]), json.loads(
                row["state_json"]
            )
            account = PaperAccount(config, state)
            return dict(
                id=row["id"],
                mode=row["mode"],
                status=row["status"],
                symbol=row["symbol"],
                createdAt=row["created_at"],
                untilReceipt=row["until_receipt"],
                config=config,
                summary=account.summary(),
                orders=state["orders"],
                fills=state["fills"],
                signals=state["signals"],
                equity=state["equity"],
                firstReceiptTime=state["firstReceiptTime"],
                lastReceiptTime=state["lastReceiptTime"],
                lastCandleTime=state["lastCandleTime"],
                processedReceipts=state["processedReceipts"],
            )

    def list(self, symbol):
        with self.store.lock:
            return [
                dict(row)
                for row in self.store.db.execute(
                    "SELECT id,mode,status,symbol,created_at AS createdAt FROM simulation_runs WHERE symbol=? ORDER BY created_at DESC,id DESC LIMIT 20",
                    (symbol,),
                )
            ]

    def pause(self, run_id):
        with self.store.lock:
            row = self.get(run_id)
            if row["mode"] != "paper":
                raise ValueError("Only a running paper account can be paused")
            self.sync()
            self.store.db.execute(
                "UPDATE simulation_runs SET status='paused' WHERE id=?", (run_id,)
            )
            return self.get(run_id)

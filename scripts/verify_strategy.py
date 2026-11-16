"""Reproduce Part 4.2 on genuine recorded receipts in an isolated database."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from server.simulation import Simulations
from server.store import MarketStore


def verify():
    with tempfile.TemporaryDirectory(prefix="marketstation-strategy-") as folder:
        path = str(Path(folder) / "market.sqlite")
        command = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.import_recording",
                "evidence/part-4-2-recording.json",
            ],
            env={**os.environ, "DATABASE_PATH": path},
            capture_output=True,
            text=True,
        )
        if command.returncode:
            raise RuntimeError("Genuine recording import failed")
        store = MarketStore(path)
        counts = store.stats()
        result = Simulations(store).create(
            dict(
                symbol="BTC-USD",
                mode="backtest",
                fast=9,
                slow=21,
                initialCash=10000,
                feeBps=10,
                slippageBps=5,
            )
        )
        assert result["summary"]["fills"] >= 2
        assert {fill["side"] for fill in result["fills"]} == {"buy", "sell"}
        orders = {order["id"]: order for order in result["orders"]}
        for fill in result["fills"]:
            order = orders[fill["orderId"]]
            assert fill["receiptId"] > order["signalReceiptId"]
            assert fill["receivedAt"] >= order["decisionTime"]
            assert fill["sourceTime"] >= order["signalTime"] + 60000
        summary = result["summary"]
        assert (
            abs(
                summary["equity"]
                - (10000 + summary["realizedPnl"] + summary["unrealizedPnl"])
            )
            < 0.001
        )
        assert store.stats() == counts
        store.close()
        reopened = MarketStore(path)
        persisted = Simulations(reopened).get(result["id"])
        assert persisted == result
        reopened.close()
        return dict(
            origin="Genuine Yahoo observations recorded November 12, 2026; simulated execution",
            dataset="evidence/part-4-2-recording.json",
            config=result["config"],
            checks=dict(
                fillsAfterDecision=True,
                quoteSourceAfterCandleEnd=True,
                equityReconciles=True,
                marketRecordsUnchanged=True,
                restartPersists=True,
            ),
            processedReceipts=result["processedReceipts"],
            summary=summary,
            orders=result["orders"],
            fills=result["fills"],
        )


if __name__ == "__main__":
    result = verify()
    Path("evidence/part-4-2-verification.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))

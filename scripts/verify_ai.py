"""Reproducible, explicitly MOCKED decisions on synthetic prices in memory.

No live provider, working database, or credentials are used by this verifier.
"""

import argparse
import asyncio
import json
from pathlib import Path

from server.ai import AIAssistant
from server.store import MarketStore
from tests.test_ai import MockProvider, quote, seed
from tests.test_store import T, candle


async def verify():
    store = MarketStore(":memory:")
    seed(store)
    clock = [T + 25 * 60_000 + 10_000]
    feed = dict(
        paused=False,
        stream=dict(state="streaming"),
        symbols={"BTC-USD": dict(chartState="available")},
    )

    def live_quote(at, price=125):
        feed["symbols"]["BTC-USD"].update(
            lastQuoteSourceTime=at, lastQuoteReceivedAt=at
        )
        return quote(store, at, price=price)

    live_quote(clock[0] - 1000)
    provider = MockProvider()
    ai = AIAssistant(store, provider, lambda: feed, lambda: clock[0])
    bot = ai.ensure_bot("BTC-USD")
    ai.set_running(bot["id"], True)
    await ai.tick()
    buy = ai.activities("BTC-USD")[0]
    assert buy["status"] == "queued"
    assert not ai.get_bot(bot["id"])["fills"]
    clock[0] += 1000
    live_quote(clock[0], price=126)
    ai.sync()
    after_buy = ai.get_bot(bot["id"])
    assert after_buy["orders"][-1]["status"] == "filled"
    ai.set_running(bot["id"], False)

    # Synthetic subsequent declining candles switch the completed-bar regime.
    for index in range(25, 50):
        at, price = T + index * 60_000, 150 - index
        store.ingest_batch(
            [
                candle(
                    sourceTime=at,
                    receivedAt=at + 61_000,
                    orderingTime=at + 60_000,
                    payload=dict(
                        open=price,
                        high=price + 1,
                        low=price - 1,
                        close=price,
                        volume=10,
                        complete=True,
                    ),
                )
            ]
        )
    clock[0] = T + 50 * 60_000 + 10_000
    live_quote(clock[0] - 1000, price=101)
    ai.sync()
    provider.action = "sell"
    ai.set_running(bot["id"], True)
    await ai.tick()
    sell = ai.activities("BTC-USD")[0]
    assert sell["status"] == "queued"
    clock[0] += 1000
    live_quote(clock[0], price=100)
    ai.sync()
    ai.set_running(bot["id"], False)
    final = ai.get_bot(bot["id"])
    assert final["orders"][-1]["status"] == "filled"
    assert final["account"]["quantity"] == "0"
    assert (
        abs(final["account"]["cash"] - 10000 - final["account"]["realizedPnl"]) < 0.001
    )
    provider.action = "hold"
    hold = await ai.decide(bot["id"], "mock-verification-hold")
    provider.bad = '{"action":"unrestricted-order"}'
    invalid = await ai.decide(bot["id"], "mock-verification-invalid")
    provider.bad = None
    provider.failure = True
    outage = await ai.decide(bot["id"], "mock-verification-outage")
    result = dict(
        evidence="MOCKED AI + SYNTHETIC prices + fixed historical clock; NOT live-provider evidence",
        isolation="In-memory SQLite; no writes to the working database",
        checks=dict(
            automaticBuyThenSell=True,
            fillsFollowDecision=True,
            cashReconciles=True,
            holdLeavesAccountUnchanged=hold["status"] == "hold",
            invalidModelRejected=invalid["status"] == "rejected",
            providerOutageStopsAction=outage["status"] == "unavailable",
        ),
        buyDecision=buy,
        accountAfterBuy=after_buy,
        sellDecision=sell,
        finalAccount=final,
        holdStatus=hold["status"],
        invalidStatus=invalid["status"],
        unavailableStatus=outage["status"],
    )
    assert all(result["checks"].values())
    store.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(verify())
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                evidence=result["evidence"],
                checks=result["checks"],
                finalAccount=result["finalAccount"]["account"],
            ),
            indent=2,
        )
    )

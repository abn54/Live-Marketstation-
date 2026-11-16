"""Reference calculations and explicit, synthetic accounting examples."""

import copy
from decimal import Decimal
import json
import random
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from server.simulation import Simulations
from server.store import MarketStore
from server.strategy import MovingAverages, PaperAccount, crossover, indicators
from tests.test_app import FakeFeed
from server.main import create_app
from tests.test_store import T

CONFIG = dict(
    symbol="BTC-USD",
    mode="backtest",
    fast=2,
    slow=3,
    initialCash=1000,
    feeBps=0,
    slippageBps=0,
)


def bars(values, complete=True):
    return [
        dict(id=i + 1, sourceTime=T + i * 60_000, close=value, complete=complete)
        for i, value in enumerate(values)
    ]


def receipt(i, value, kind="candle", complete=True):
    source = T + i * 60_000
    return dict(
        receiptId=i + 1,
        receivedAt=source + 61_000,
        applied=True,
        observation=dict(
            id=i + 1,
            sourceTime=source,
            kind=kind,
            complete=complete,
            close=value,
            price=value,
        ),
    )


def market_event(i, value, kind="candle"):
    source = T + i * 60_000
    return dict(
        source="yahoo-chart" if kind == "candle" else "yahoo-stream",
        kind=kind,
        symbol="BTC-USD",
        interval="1m" if kind == "candle" else "tick",
        sourceTime=source,
        receivedAt=source + 61_000,
        orderingTime=source + 60_000,
        payload=(
            dict(
                open=value, high=value, low=value, close=value, volume=10, complete=True
            )
            if kind == "candle"
            else dict(price=value)
        ),
    )


@pytest.mark.parametrize("fast,slow", [(2, 3), (9, 21), (20, 100)])
def test_python_batch_incremental_and_vue_match_independent_pandas_reference(
    fast, slow
):
    rng = random.Random(402)
    values = [100 + rng.uniform(-10, 10) for _ in range(250)]
    candles = bars(values)
    # The unfinished close is intentionally extreme. It must affect neither SMA.
    candles[-1].update(complete=False, close=1_000_000)
    expected = pd.Series(values[:-1])
    short = expected.rolling(fast, min_periods=fast).mean()
    long = expected.rolling(slow, min_periods=slow).mean()
    differences = short - long
    signals = []
    for i, difference in enumerate(differences):
        signals.append(
            "buy"
            if i and differences.iloc[i - 1] <= 0 < difference
            else "sell" if i and differences.iloc[i - 1] >= 0 > difference else None
        )
    calc = MovingAverages(fast, slow)
    incremental = [calc.update(value) for value in values[:-1]]
    batch = indicators(candles, fast, slow)
    raw = subprocess.check_output(
        [
            "node",
            "--input-type=module",
            "-e",
            "import {calculateIndicators} from './client/indicators.ts';"
            "let t='';for await(const c of process.stdin)t+=c;"
            "let d=JSON.parse(t);console.log(JSON.stringify(calculateIndicators(d.c,d.f,d.s)));",
        ],
        input=json.dumps(dict(c=candles, f=fast, s=slow)).encode(),
        cwd=Path(__file__).resolve().parent.parent,
    )
    vue = json.loads(raw)
    for rows in (incremental, batch, vue):
        assert len(rows) == len(expected)
        for i, point in enumerate(rows):
            for name, reference in [("fast", short), ("slow", long)]:
                if pd.isna(reference.iloc[i]):
                    assert point[name] is None
                else:
                    assert point[name] == pytest.approx(reference.iloc[i], abs=1e-10)
            assert point["signal"] == signals[i]


def test_equality_plateau_crosses_only_when_leaving_equality():
    assert crossover(None, 1) is None
    assert crossover(-1, 0) is None
    assert crossover(0, 1) == "buy"
    assert crossover(1, 0) is None
    assert crossover(0, -1) == "sell"
    assert all(p["signal"] is None for p in indicators(bars([2] * 30), 2, 3))


def test_known_round_trip_reconciles_cash_cost_realized_and_unrealized():
    account = PaperAccount(CONFIG)
    buy = dict(id=1, side="buy")
    account.fill(buy, receipt(1, 100, "quote"), Decimal(100))
    account.state["lastMark"] = "110"
    summary = account.summary()
    assert summary["cash"] == 50 and summary["quantity"] == "9.50000000"
    assert summary["costBasis"] == 950 and summary["unrealizedPnl"] == 95
    assert summary["equity"] == 1095 and summary["realizedPnl"] == summary["fees"] == 0
    account.fill(dict(id=2, side="sell"), receipt(2, 110, "quote"), Decimal(110))
    result = account.summary()
    assert result["cash"] == result["equity"] == 1095
    assert result["realizedPnl"] == 95 and result["unrealizedPnl"] == 0
    assert result["quantity"] == "0" and result["costBasis"] == 0


def test_known_fees_and_adverse_slippage():
    account = PaperAccount({**CONFIG, "feeBps": 100})
    account.fill(dict(id=1, side="buy"), receipt(1, 100, "quote"), Decimal(100))
    assert account.state["cash"] == "50.00" and account.state["costBasis"] == "950.00"
    account.fill(dict(id=2, side="sell"), receipt(2, 110, "quote"), Decimal(110))
    assert account.summary()["cash"] == 1074.30
    assert account.summary()["realizedPnl"] == 74.30
    assert account.summary()["fees"] == 19.76
    slipped = PaperAccount({**CONFIG, "slippageBps": 100})
    slipped.fill(dict(id=1, side="buy"), receipt(1, 100, "quote"), Decimal(100))
    slipped.fill(dict(id=2, side="sell"), receipt(2, 100, "quote"), Decimal(100))
    assert [f["price"] for f in slipped.state["fills"]] == [101, 99]
    assert slipped.summary()["realizedPnl"] < 0


def test_completed_crossover_then_later_quote_and_prefix_causality():
    account = PaperAccount(CONFIG)
    for i, value in enumerate([3, 2, 1, 2, 4]):
        account.process(receipt(i, value))
    assert account.state["orders"][0]["status"] == "pending next quote"
    assert not account.state["fills"]
    prefix = copy.deepcopy(account.state)
    q = receipt(5, 10, "quote")
    q["receivedAt"] = T + 5 * 60_000 + 1000
    account.process(q)
    assert (
        account.state["fills"][0]["receiptId"] > prefix["orders"][0]["signalReceiptId"]
    )
    assert account.state["fills"][0]["price"] == 10
    assert (
        account.state["orders"][0]["decisionTime"]
        == prefix["orders"][0]["decisionTime"]
    )
    restarted = PaperAccount(CONFIG, prefix)
    restarted.process(q)
    assert restarted.state == account.state
    restarted.process(q)
    assert restarted.state == account.state


def test_partial_duplicate_superseded_and_late_corrections_cannot_trade_twice():
    account = PaperAccount(CONFIG)
    for i, value in enumerate([3, 2, 1, 2]):
        account.process(receipt(i, value))
    partial = receipt(4, 100, complete=False)
    account.process(partial)
    assert not account.state["orders"]
    completed = receipt(4, 4)
    completed["receiptId"] = 6
    account.process(completed)
    assert len(account.state["orders"]) == 1
    corrected = copy.deepcopy(completed)
    corrected["receiptId"] = 7
    corrected["observation"]["close"] = 1
    account.process(corrected)
    corrected.update(receiptId=8, applied=False)
    account.process(corrected)
    assert len(account.state["orders"]) == 1
    assert account.state["completedBars"] == 5


def test_late_bootstrap_does_not_create_orders_and_stale_quotes_do_not_fill():
    late = PaperAccount(CONFIG)
    for i, value in enumerate([3, 2, 1, 2, 4]):
        item = receipt(i, value)
        item["receivedAt"] += 600_000
        late.process(item)
    assert not late.state["orders"]
    account = PaperAccount(CONFIG)
    for i, value in enumerate([3, 2, 1, 2, 4]):
        account.process(receipt(i, value))
    stale = receipt(5, 100, "quote")
    account.process(stale)  # Its quote source is 61 seconds old.
    assert not account.state["fills"]
    expired = receipt(10, 100, "quote")
    account.process(expired)
    assert account.state["orders"][0]["status"].startswith("expired")


def test_future_prices_cannot_change_a_previous_decision_or_fill_and_drawdown_is_known():
    prefix = []
    for i, value in enumerate([3, 2, 1, 2, 4]):
        prefix.append(receipt(i, value))
    quote = receipt(5, 100, "quote")
    quote["receivedAt"] = quote["observation"]["sourceTime"] + 1000
    prefix.append(quote)
    account = PaperAccount(CONFIG)
    for item in prefix:
        account.process(item)
    original_orders = copy.deepcopy(account.state["orders"])
    original_fills = copy.deepcopy(account.state["fills"])
    for i, value in [(6, 120), (7, 90)]:
        q = receipt(i, value, "quote")
        q["receivedAt"] = q["observation"]["sourceTime"] + 1000
        account.process(q)
    assert account.state["orders"] == original_orders
    assert account.state["fills"] == original_fills
    assert account.summary()["equity"] == 905
    assert account.summary()["unrealizedPnl"] == -95
    assert account.summary()["maxDrawdownPercent"] == pytest.approx(
        (1190 - 905) / 1190 * 100
    )


def test_equity_always_reconciles_and_a_cross_buys_then_sells():
    account = PaperAccount(CONFIG)
    for i, value in enumerate([3, 2, 1, 2, 4, 5, 2, 1]):
        c = receipt(i, value)
        c["receiptId"] = i * 2 + 1
        account.process(c)
        q = receipt(i + 1, 100 + i, "quote")
        q["receiptId"] = i * 2 + 2
        q["receivedAt"] = q["observation"]["sourceTime"] + 2000
        account.process(q)
        s = account.summary()
        assert s["equity"] == pytest.approx(
            1000 + s["realizedPnl"] + s["unrealizedPnl"], abs=0.001
        )
    assert [f["side"] for f in account.state["fills"]] == ["buy", "sell"]
    assert account.summary()["quantity"] == "0"


def test_simulations_persist_freeze_history_and_recover_running_session(tmp_path):
    path = tmp_path / "market.sqlite"
    store = MarketStore(path)
    for i, value in enumerate([3, 2, 1, 2, 4]):
        store.ingest_batch([market_event(i, value)])
    service = Simulations(store)
    backtest = service.create(CONFIG)
    paper = service.create({**CONFIG, "mode": "paper"})
    assert paper["summary"]["fills"] == paper["summary"]["signals"] == 0
    assert service.create({**CONFIG, "mode": "paper"})["id"] == paper["id"]
    with pytest.raises(ValueError, match="Pause"):
        service.create({**CONFIG, "mode": "paper", "fast": 3, "slow": 4})
    quote = market_event(5, 10, "quote")
    quote["receivedAt"] = quote["sourceTime"] + 1000
    store.ingest_batch([quote])
    service.sync()
    assert service.get(backtest["id"]) == backtest
    assert service.get(paper["id"])["untilReceipt"] > paper["untilReceipt"]
    store.close()
    reopened = MarketStore(path)
    service = Simulations(reopened)
    service.sync()
    before = service.get(paper["id"])
    service.sync()
    assert service.get(paper["id"]) == before
    paused = service.pause(paper["id"])
    reopened.ingest_batch([market_event(6, 100)])
    service.sync()
    assert service.get(paper["id"]) == paused
    reopened.close()


def test_strategy_routes_validation_same_origin_and_saved_results():
    store = MarketStore(":memory:")
    for i, value in enumerate([3, 2, 1, 2, 4]):
        store.ingest_batch([market_event(i, value)])
    app = create_app(store=store, feed_factory=FakeFeed, serve_client=False)
    with TestClient(app) as client:
        for update in [
            dict(fast=4),
            dict(feeBps=-1),
            dict(initialCash=0),
            dict(slow=201),
        ]:
            assert (
                client.post("/api/simulations", json={**CONFIG, **update}).status_code
                == 422
            )
        assert (
            client.post(
                "/api/simulations",
                json=CONFIG,
                headers={"Origin": "https://elsewhere.example"},
            ).status_code
            == 403
        )
        assert client.get("/api/simulations/missing").status_code == 404
        result = client.post("/api/simulations", json=CONFIG)
        assert result.status_code == 200
        saved = result.json()
        assert client.get(f"/api/simulations/{saved['id']}").json() == saved
        assert (
            client.get("/api/simulations?symbol=BTC-USD").json()["runs"][0]["id"]
            == saved["id"]
        )
    store.close()


def test_running_paper_account_executes_new_crossovers_and_restart_cannot_repeat_fill(
    tmp_path,
):
    path = tmp_path / "paper.sqlite"
    store = MarketStore(path)
    for i, value in enumerate([3, 2, 1, 2]):
        store.ingest_batch([market_event(i, value)])
    service = Simulations(store)
    paper = service.create({**CONFIG, "mode": "paper"})
    store.ingest_batch([market_event(4, 4)])
    service.sync()
    pending = service.get(paper["id"])
    assert pending["orders"][0]["status"] == "pending next quote"
    assert pending["summary"]["fills"] == 0
    quote = market_event(5, 100, "quote")
    quote["receivedAt"] = quote["sourceTime"] + 1000
    store.ingest_batch([quote])
    service.sync()
    assert service.get(paper["id"])["summary"]["fills"] == 1
    store.close()
    store = MarketStore(path)
    service = Simulations(store)
    service.sync()
    assert service.get(paper["id"])["summary"]["fills"] == 1
    assert service.get(paper["id"])["summary"]["quantity"] == "9.50000000"
    store.close()

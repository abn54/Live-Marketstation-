import hashlib

import pytest

from server.store import MarketStore

T = 1794009600000


def candle(**changes):
    observation = dict(
        source="yahoo-chart",
        kind="candle",
        symbol="BTC-USD",
        interval="1m",
        sourceTime=T,
        receivedAt=T + 30000,
        orderingTime=T + 25000,
        payload=dict(open=100, high=103, low=99, close=102, volume=10, complete=False),
    )
    observation.update(changes)
    return observation


@pytest.fixture
def store():
    s = MarketStore(":memory:")
    yield s
    s.close()


def test_duplicate_preserves_identity_and_distinct_receipts(store):
    a = store.ingest_batch([candle()])[0]
    b = store.ingest_batch([candle(receivedAt=T + 35000, orderingTime=T + 34000)])[0]
    assert b["disposition"] == "duplicate"
    assert a["observation"]["id"] == b["observation"]["id"]
    assert a["receiptId"] != b["receiptId"]
    assert store.stats()["observations"] == 1
    assert store.stats()["receipts"] == 2
    assert store.replay("BTC-USD")[1]["orderingTime"] == T + 34000
    assert store.replay("BTC-USD")[1]["receivedAt"] == T + 35000


def test_property_order_and_js_numeric_format_do_not_create_false_revision(store):
    o = candle()
    store.ingest_batch([o])
    # Simulate an immutable row from the prior JavaScript implementation.
    legacy = '{"close":102,"complete":false,"high":103,"low":99,"open":100,"volume":10}'
    store.db.execute(
        "UPDATE observations SET payload_json=?,payload_hash=?",
        (legacy, hashlib.sha256(legacy.encode()).hexdigest()),
    )
    o["payload"] = dict(reversed(list(o["payload"].items())))
    o["payload"]["open"] = 100.0
    assert store.ingest_batch([o])[0]["disposition"] == "duplicate"
    assert (
        store.db.execute("SELECT payload_json FROM observations").fetchone()[0]
        == legacy
    )


def test_revision_is_immutable_and_promoted(store):
    first = store.ingest_batch([candle()])[0]
    o = candle(receivedAt=T + 40000, orderingTime=T + 39000)
    o["payload"].update(high=105, close=104, volume=15)
    second = store.ingest_batch([o])[0]
    assert second["disposition"] == "revised"
    assert second["observation"]["revision"] == 2
    assert store.candles("BTC-USD")[0]["close"] == 104
    assert (
        store.replay("BTC-USD")[0]["observation"]["close"]
        == first["observation"]["close"]
    )


def test_out_of_order_response_retained_not_applied(store):
    store.ingest_batch([candle(orderingTime=T + 29000)])
    o = candle(orderingTime=T + 20000, receivedAt=T + 40000)
    o["payload"]["close"] = 101
    result = store.ingest_batch([o])[0]
    assert result["disposition"] == "superseded"
    assert not result["applied"]
    assert store.candles("BTC-USD")[0]["close"] == 102
    assert store.stats()["superseded"] == 1


def test_new_duplicate_watermark_blocks_slow_old_response(store):
    store.ingest_batch([candle()])
    store.ingest_batch([candle(orderingTime=T + 40000, receivedAt=T + 41000)])
    old = candle(orderingTime=T + 35000, receivedAt=T + 42000)
    old["payload"]["close"] = 101
    assert store.ingest_batch([old])[0]["disposition"] == "superseded"
    assert store.candles("BTC-USD")[0]["close"] == 102


def test_newer_return_to_prior_value_is_real_revision(store):
    store.ingest_batch([candle()])
    changed = candle(orderingTime=T + 35000, receivedAt=T + 36000)
    changed["payload"]["close"] = 101
    store.ingest_batch([changed])
    result = store.ingest_batch([candle(orderingTime=T + 40000, receivedAt=T + 41000)])[
        0
    ]
    assert result["disposition"] == "revised"
    assert result["observation"]["revision"] == 3
    assert store.candles("BTC-USD")[0]["close"] == 102


def test_completion_revision_cannot_be_reopened_by_old_partial(store):
    store.ingest_batch([candle()])
    done = candle(orderingTime=T + 70000, receivedAt=T + 71000)
    done["payload"]["complete"] = True
    store.ingest_batch([done])
    late = candle(orderingTime=T + 50000, receivedAt=T + 72000)
    late["payload"]["close"] = 101
    assert store.ingest_batch([late])[0]["disposition"] == "superseded"
    assert store.candles("BTC-USD")[0]["complete"] is True


def test_older_minute_is_sorted_without_changing_newer_minute(store):
    store.ingest_batch(
        [candle(sourceTime=T + 60000, orderingTime=T + 80000, receivedAt=T + 81000)]
    )
    store.ingest_batch([candle(orderingTime=T + 82000, receivedAt=T + 83000)])
    assert [o["sourceTime"] for o in store.candles("BTC-USD")] == [T, T + 60000]


def test_replay_frozen_watermark_and_readonly(store):
    store.ingest_batch([candle()])
    store.ingest_batch([candle(receivedAt=T + 40000)])
    high = store.stats()["lastReceiptId"]
    late = candle(orderingTime=T + 20000, receivedAt=T + 45000)
    late["payload"]["close"] = 101
    store.ingest_batch([late])
    before = store.stats()
    first = store.replay("BTC-USD", until=high, limit=1)
    second = store.replay("BTC-USD", after=first[0]["receiptId"], until=high)
    assert len(second) == 1 and second[0]["disposition"] == "duplicate"
    assert second[0]["receivedAt"] == T + 40000
    assert not store.replay("BTC-USD")[2]["applied"]
    assert store.stats() == before


def test_invalid_batch_is_atomic_and_unknown_volume_is_null(store):
    invalid = candle()
    invalid["payload"]["high"] = 1
    with pytest.raises(ValueError, match="bounds"):
        store.ingest_batch([candle(), invalid])
    assert store.stats()["observations"] == 0
    unknown = candle()
    unknown["payload"]["volume"] = None
    store.ingest_batch([unknown])
    assert store.candles("BTC-USD")[0]["volume"] is None


def test_latest_quote_follows_source_time_not_arrival(store):
    def quote(source_time, price, received):
        return dict(
            source="yahoo-stream",
            kind="quote",
            symbol="BTC-USD",
            interval="tick",
            sourceTime=source_time,
            receivedAt=received,
            orderingTime=received,
            payload=dict(price=price),
        )

    store.ingest_batch([quote(T + 2000, 103, T + 3000), quote(T + 1000, 101, T + 4000)])
    assert store.quote("BTC-USD")["price"] == 103


def test_disk_reopen_preserves_records_and_integrity(tmp_path):
    path = tmp_path / "market.sqlite"
    s = MarketStore(path)
    s.ingest_batch([candle()])
    s.close()
    s = MarketStore(path)
    try:
        assert s.candles("BTC-USD")[0]["close"] == 102
        assert s.stats()["receipts"] == 1
        assert s.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        s.close()


def test_full_replay_reconstructs_projection_with_revisions_and_superseded(store):
    store.ingest_batch([candle()])
    changed = candle(orderingTime=T + 40000, receivedAt=T + 41000)
    changed["payload"].update(high=105, close=104)
    store.ingest_batch([changed])
    late = candle(orderingTime=T + 30000, receivedAt=T + 45000)
    late["payload"]["close"] = 100
    store.ingest_batch([late])
    heads = {}
    for r in store.replay("BTC-USD"):
        if r["applied"]:
            heads[r["observation"]["logicalId"]] = r["observation"]
    assert list(heads.values()) == store.candles("BTC-USD")

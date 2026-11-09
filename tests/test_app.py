import asyncio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import create_app
from server.store import MarketStore
from tests.test_store import T, candle


class FakeFeed:
    def __init__(self, **options):
        self.options = options
        self.paused = False

    def status(self):
        return dict(
            stream=dict(state="unavailable", detail="test unavailable"),
            chart=dict(state="unavailable", detail="test unavailable"),
            symbols={},
            paused=self.paused,
            pollMs=15000,
        )

    async def start(self):
        pass

    async def stop(self):
        pass

    async def pause(self):
        self.paused = True

    async def resume(self):
        self.paused = False


@pytest.fixture
def runtime():
    store = MarketStore(":memory:")

    def create(demo=False):
        return create_app(
            store=store, demo_controls=demo, feed_factory=FakeFeed, serve_client=False
        )

    yield store, create
    store.close()


def test_health_exposes_unavailable_upstream_and_required_stack(runtime):
    store, create = runtime
    with TestClient(create()) as client:
        h = client.get("/api/health").json()
        assert h["ok"] and h["feed"]["stream"]["state"] == "unavailable"
        assert h["stats"]["observations"] == 0
        assert h["stack"] == dict(
            frontend="Vue 3", backend="FastAPI", database="SQLite"
        )


def test_symbol_and_pagination_are_validated(runtime):
    _, create = runtime
    with TestClient(create()) as client:
        assert client.get("/api/candles?symbol=INVALID").status_code == 400
        for query in ["after=-1", "limit=100000", "limit=0", "limit=NaN"]:
            assert client.get("/api/replay?symbol=BTC-USD&" + query).status_code == 422
        assert client.get("/api/missing").status_code == 404


def test_fault_controls_disabled_by_default(runtime):
    _, create = runtime
    with TestClient(create()) as client:
        assert (
            client.post("/api/demo/feed", json={"action": "disconnect"}).status_code
            == 403
        )


def test_cross_origin_fault_action_and_websocket_are_rejected(runtime):
    _, create = runtime
    with TestClient(create(True)) as client:
        assert (
            client.post(
                "/api/demo/feed",
                json={"action": "disconnect"},
                headers={"Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws", headers={"Origin": "https://untrusted.example"}
            ):
                pass


def test_demo_disconnect_and_reconnect(runtime):
    _, create = runtime
    with TestClient(create(True)) as client:
        for action in ("disconnect", "reconnect"):
            r = client.post("/api/demo/feed", json={"action": action})
            assert r.status_code == 200
            assert r.json()["feed"]["paused"] == (action == "disconnect")
        assert (
            client.post("/api/demo/feed", json={"action": "invalid"}).status_code == 422
        )


def test_real_fastapi_socket_rest_and_sqlite_agree(runtime):
    store, create = runtime
    app = create()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot" and len(snapshot["symbols"]) == 4
            results = store.ingest_batch([candle()])
            # Execute the exact provider callback on FastAPI's running event loop.
            client.portal.call(app.state.feed.options["on_data"], results)
            event = ws.receive_json()
            assert event["type"] == "observations"
            assert (
                event["results"][0]["observation"]["id"]
                == results[0]["observation"]["id"]
            )
            d = client.get("/api/candles?symbol=BTC-USD").json()
            assert d["candles"][0]["id"] == event["results"][0]["observation"]["id"]
            assert d["candles"][0]["volume"] == 10
            replay = client.get("/api/replay?symbol=BTC-USD").json()
            assert (
                replay["mode"] == "recorded"
                and replay["records"][0]["receiptId"]
                == event["results"][0]["receiptId"]
            )


def test_replay_pagination_keeps_frozen_watermark(runtime):
    store, create = runtime
    store.ingest_batch([candle(), candle(receivedAt=1794009640000)])
    with TestClient(create()) as client:
        first = client.get("/api/replay?symbol=BTC-USD&limit=1").json()
        store.ingest_batch([candle(receivedAt=1794009650000)])
        second = client.get(
            f"/api/replay?symbol=BTC-USD&after={first['nextAfter']}&until={first['until']}"
        ).json()
        assert (
            len(second["records"]) == 1
            and second["records"][0]["disposition"] == "duplicate"
        )
        assert second["until"] == first["until"]


def test_recent_replay_checkpoint_and_window_reconstruct_persisted_heads(runtime):
    store, create = runtime
    quote = {
        **candle(),
        "kind": "quote",
        "source": "yahoo-stream",
        "interval": "tick",
        "sourceTime": T + 1000,
        "payload": {"price": 102},
    }
    revised = candle(receivedAt=T + 40_000, orderingTime=T + 35_000)
    revised["payload"].update(close=103)
    superseded = candle(receivedAt=T + 41_000, orderingTime=T + 20_000)
    superseded["payload"].update(close=101)
    initial, saved_quote, correction, *_ = store.ingest_batch([
        candle(), quote, revised, superseded, candle(symbol="ETH-USD"),
    ])
    next_candle = candle(sourceTime=T + 60_000, receivedAt=T + 80_000, orderingTime=T + 75_000)
    store.ingest_batch([revised, candle(symbol="ETH-USD"), next_candle])
    with TestClient(create()) as client:
        before = store.stats()
        replay = client.get("/api/replay/recent?symbol=BTC-USD&limit=3").json()
        assert replay["mode"] == "recorded" and replay["until"] == before["lastReceiptId"]
        assert [r["disposition"] for r in replay["records"]] == ["superseded", "duplicate", "inserted"]
        checkpoint = replay["checkpoint"]
        assert checkpoint["candles"] == [correction["observation"]]
        assert checkpoint["candles"][0]["id"] != initial["observation"]["id"]
        assert checkpoint["quote"] == saved_quote["observation"]
        heads = {o["logicalId"]: o for o in checkpoint["candles"]}
        for r in replay["records"]:
            if r["applied"]:
                heads[r["observation"]["logicalId"]] = r["observation"]
        assert list(heads.values()) == store.candles("BTC-USD")
        assert store.stats() == before
        assert client.get("/api/replay/recent?symbol=SPY").json()["records"] == []

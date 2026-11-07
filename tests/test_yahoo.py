import asyncio
import base64
import json
import ssl

import httpx
import pytest
from yfinance.pricing_pb2 import PricingData

from server.store import MarketStore
from server.yahoo import YahooFeed, decode_quote, normalize_chart
from tests.test_store import T


def chart_data():
    return {
        "chart": {
            "result": [
                {
                    "meta": {"shortName": "Bitcoin USD", "currency": "USD"},
                    "timestamp": [T // 1000, T // 1000 + 60, T // 1000 + 75],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100, 102, 103],
                                "high": [104, 105, 103],
                                "low": [99, 101, 103],
                                "close": [102, 104, 103],
                                "volume": [50, 70, 0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def message():
    p = PricingData(id="BTC-USD", price=100.5, time=T, currency="USD", day_volume=1000)
    return json.dumps(
        {"type": "pricing", "message": base64.b64encode(p.SerializeToString()).decode()}
    )


def test_protobuf_retains_original_milliseconds_and_provenance():
    q = decode_quote(message(), T + 1000)
    assert q["sourceTime"] == T and q["payload"]["price"] == 100.5
    assert q["receivedAt"] == T + 1000 and q["payload"]["dayVolume"] == 1000
    assert q["source"] == "yahoo-stream"


def test_normalizer_prefers_ohlcv_over_appended_price_row():
    obs = normalize_chart(chart_data(), "BTC-USD", T + 90000, T + 91000)["observations"]
    assert len(obs) == 2 and obs[0]["payload"]["complete"]
    assert not obs[1]["payload"]["complete"]
    assert obs[1]["payload"]["volume"] == 70 and obs[1]["payload"]["close"] == 104
    assert obs[1]["orderingTime"] == T + 90000


def test_null_ohlc_skipped_and_missing_volume_is_not_zero():
    data = chart_data()
    q = data["chart"]["result"][0]["indicators"]["quote"][0]
    q["volume"][0] = None
    q["open"][1] = q["open"][2] = None
    obs = normalize_chart(data, "BTC-USD", T + 90000, T + 91000)["observations"]
    assert len(obs) == 1 and obs[0]["payload"]["volume"] is None


def test_provider_error_and_malformed_protocol_fail_explicitly():
    with pytest.raises(ValueError, match="Rate limited"):
        normalize_chart(
            {"chart": {"error": {"description": "Rate limited"}}}, "BTC-USD", T, T
        )
    with pytest.raises(ValueError):
        decode_quote("{broken")


async def test_http_429_retains_history_and_recovers():
    s = MarketStore(":memory:")
    fail = True

    async def respond(request):
        return httpx.Response(429) if fail else httpx.Response(200, json=chart_data())

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        f = YahooFeed(s, client=client, clock=lambda: T + 90000)
        f.stopped = False
        try:
            await f.fetch_symbol("BTC-USD")
            assert f.symbols["BTC-USD"]["chartState"] == "unavailable"
            assert "429" in f.symbols["BTC-USD"]["chartError"]
            assert s.stats()["observations"] == 0
            fail = False
            await f.fetch_symbol("BTC-USD")
            assert s.stats()["observations"] == 2
            fail = True
            await f.fetch_symbol("BTC-USD")
            assert len(s.candles("BTC-USD")) == 2
        finally:
            await f.stop()
            s.close()


async def test_inflight_outage_cannot_leak_rows_or_healthy_status():
    s = MarketStore(":memory:")
    entered = asyncio.Event()
    release = asyncio.Event()

    async def respond(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json=chart_data())

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        f = YahooFeed(s, client=client, clock=lambda: T + 90000)
        f.stopped = False
        task = asyncio.create_task(f.fetch_symbol("BTC-USD"))
        await entered.wait()
        await f.pause()
        release.set()
        await task
        try:
            assert s.stats()["observations"] == 0
            assert (
                f.status()["chart"]["state"] == "unavailable" and f.status()["paused"]
            )
        finally:
            await f.stop()
            s.close()


async def test_real_async_socket_path_commits_before_publish_and_reports_disconnect():
    s = MarketStore(":memory:")
    committed = asyncio.Event()
    left = asyncio.Event()
    retry = asyncio.Event()

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, raw):
            assert "BTC-USD" in raw

        def __aiter__(self):
            return self

        async def __anext__(self):
            if committed.is_set():
                left.set()
                raise ConnectionError("test disconnect")
            return message()

    def on_data(results):
        assert s.stats()["observations"] == 1
        assert results[0]["observation"]["id"] == s.quote("BTC-USD")["id"]
        committed.set()

    def on_status(status):
        if "retry" in status["stream"]["detail"]:
            retry.set()

    def connector(*args, **kwargs):
        assert kwargs["ssl"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["ssl"].check_hostname
        return Socket()

    f = YahooFeed(
        s,
        clock=lambda: T + 1000,
        connector=connector,
        on_data=on_data,
        on_status=on_status,
    )
    f.stopped = False
    task = asyncio.create_task(f.stream_loop())
    try:
        await asyncio.wait_for(retry.wait(), 2)
        assert committed.is_set() and f.status()["stream"]["state"] == "unavailable"
        assert "retry" in f.status()["stream"]["detail"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await f.stop()
        s.close()


async def test_reconnect_is_idempotent_and_pause_marks_every_symbol_unavailable():
    s = MarketStore(":memory:")
    f = YahooFeed(s)
    f.stopped = False
    f.paused = True
    launches = []
    f._launch = lambda: launches.append(1)
    try:
        await f.resume()
        await f.resume()
        assert launches == [1]
        await f.pause()
        assert all(m["chartState"] == "unavailable" for m in f.symbols.values())
    finally:
        await f.stop()
        s.close()


def test_ended_final_minute_is_complete_without_waiting_for_another_bar():
    observed = normalize_chart(chart_data(), "BTC-USD", T + 180000, T + 181000)[
        "observations"
    ]
    assert observed[-1]["sourceTime"] == T + 60000
    assert observed[-1]["payload"]["complete"] is True

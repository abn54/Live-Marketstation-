"""Yahoo pricing WebSocket and authoritative one-minute OHLCV snapshots."""

from __future__ import annotations

import asyncio
import base64
import copy
import inspect
import json
import time
import ssl

import certifi

import httpx
from google.protobuf.json_format import MessageToDict
from websockets.asyncio.client import connect
from yfinance.pricing_pb2 import PricingData

from .store import finite

SYMBOLS = ["BTC-USD", "ETH-USD", "SPY", "AAPL"]
now_ms = lambda: time.time_ns() // 1_000_000


def decode_quote(raw, received_at=None):
    received_at = now_ms() if received_at is None else received_at
    envelope = json.loads(raw)
    if envelope.get("type") != "pricing" or not isinstance(
        envelope.get("message"), str
    ):
        return None
    pricing = PricingData()
    pricing.ParseFromString(base64.b64decode(envelope["message"], validate=True))
    p = MessageToDict(pricing, preserving_proto_field_name=True)
    if p.get("id") not in SYMBOLS or not finite(p.get("price")) or not p.get("time"):
        raise ValueError("Malformed Yahoo quote")
    return dict(
        source="yahoo-stream",
        kind="quote",
        symbol=p["id"],
        interval="tick",
        sourceTime=int(p["time"]),
        receivedAt=received_at,
        orderingTime=received_at,
        payload=dict(
            price=pricing.price,
            currency=p.get("currency", "USD"),
            dayVolume=int(p["day_volume"]) if "day_volume" in p else None,
            changePercent=pricing.change_percent if "change_percent" in p else None,
            exchange=p.get("exchange"),
            marketHours=pricing.market_hours if "market_hours" in p else None,
        ),
    )


def normalize_chart(data, symbol, started, received):
    chart = data.get("chart", {})
    if chart.get("error"):
        raise ValueError(chart["error"].get("description", "Yahoo chart error"))
    results = chart.get("result") or []
    if (
        not results
        or not results[0].get("timestamp")
        or not results[0].get("indicators", {}).get("quote")
    ):
        raise ValueError("Yahoo returned no candle data")
    result, bars = results[0], {}
    q = result["indicators"]["quote"][0]
    for i, t in enumerate(result["timestamp"]):
        source_time = int(t // 60) * 60_000
        values = [
            q.get(k, [])[i] if i < len(q.get(k, [])) else None
            for k in ("open", "high", "low", "close")
        ]
        if not all(finite(v) and v > 0 for v in values):
            continue
        # Appended last-price rows must not erase the aligned minute's volume.
        if source_time in bars and t % 60:
            continue
        vol = q.get("volume", [])[i] if i < len(q.get("volume", [])) else None
        bars[source_time] = dict(
            source="yahoo-chart",
            kind="candle",
            symbol=symbol,
            interval="1m",
            sourceTime=source_time,
            receivedAt=received,
            orderingTime=started,
            payload=dict(
                zip(("open", "high", "low", "close"), values),
                volume=vol if finite(vol) and vol >= 0 else None,
                complete=source_time + 60_000 <= started,
            ),
        )
    if not bars:
        raise ValueError("Yahoo returned no valid candles")
    meta = result.get("meta", {})
    return dict(
        observations=sorted(bars.values(), key=lambda o: o["sourceTime"]),
        meta=dict(
            name=meta.get("shortName", symbol),
            currency=meta.get("currency", "USD"),
            exchange=meta.get("exchangeName", "Unknown"),
            marketTime=meta.get("regularMarketTime", 0) * 1000 or None,
        ),
    )


class YahooFeed:
    def __init__(
        self,
        store,
        on_data=None,
        on_status=None,
        poll_ms=15000,
        client=None,
        clock=now_ms,
        connector=connect,
    ):
        self.store, self.on_data, self.on_status = store, on_data, on_status
        self.poll_ms, self.clock, self.connector = poll_ms, clock, connector
        self.client = client or httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        self.owns_client = client is None
        self.stopped, self.paused, self.generation, self.attempt = True, False, 0, 0
        self.stream_task = self.poll_task = self.socket = None
        self.states = {
            "stream": dict(state="connecting", detail="Waiting for Yahoo WebSocket"),
            "chart": dict(state="connecting", detail="Waiting for Yahoo candles"),
        }
        self.symbols = {}

    def status(self):
        return copy.deepcopy(
            dict(
                **self.states,
                paused=self.paused,
                symbols=self.symbols,
                pollMs=self.poll_ms,
            )
        )

    async def _emit(self, callback, value):
        if callback:
            result = callback(value)
            if inspect.isawaitable(result):
                await result

    async def set_status(self, channel, state, detail, **extra):
        previous = self.states[channel]
        self.states[channel] = dict(previous, **extra, state=state, detail=detail)
        if previous["state"] != state or previous["detail"] != detail:
            self.store.event(channel, state, detail, self.clock())
        await self._emit(self.on_status, self.status())

    async def start(self):
        if not self.stopped:
            return
        self.stopped = False
        self._launch()

    def _launch(self):
        self.stream_task = asyncio.create_task(self.stream_loop())
        self.poll_task = asyncio.create_task(self.poll_loop())

    async def subscribe(self, socket):
        while True:
            await socket.send(json.dumps({"subscribe": SYMBOLS}))
            await asyncio.sleep(15)

    async def stream_loop(self):
        while not self.stopped and not self.paused:
            await self.set_status("stream", "connecting", "Connecting to Yahoo Finance")
            subscription = None
            try:
                async with self.connector(
                    "wss://streamer.finance.yahoo.com/?version=2",
                    ssl=ssl.create_default_context(cafile=certifi.where()),
                    origin="https://finance.yahoo.com",
                    user_agent_header="Mozilla/5.0",
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=1_000_000,
                ) as socket:
                    self.socket, self.attempt = socket, 0
                    await self.set_status(
                        "stream",
                        "connected",
                        "Connected; waiting for a pricing message",
                    )
                    subscription = asyncio.create_task(self.subscribe(socket))
                    async for raw in socket:
                        if self.paused or self.stopped:
                            break
                        try:
                            o = decode_quote(raw, self.clock())
                            if not o:
                                continue
                            results = self.store.ingest_batch([o])
                            self.symbols.setdefault(o["symbol"], {}).update(
                                lastQuoteReceivedAt=o["receivedAt"],
                                lastQuoteSourceTime=o["sourceTime"],
                            )
                            await self.set_status(
                                "stream",
                                "streaming",
                                "Receiving Yahoo pricing messages",
                                lastReceivedAt=o["receivedAt"],
                            )
                            await self._emit(self.on_data, results)
                        except (ValueError, KeyError, TypeError) as exc:
                            await self.set_status(
                                "stream", "degraded", f"Quote rejected: {exc}"
                            )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.stopped or self.paused:
                    return
                await self.set_status(
                    "stream",
                    "unavailable",
                    f"Yahoo WebSocket: {type(exc).__name__}: {exc}",
                )
            finally:
                self.socket = None
                if subscription:
                    subscription.cancel()
                    await asyncio.gather(subscription, return_exceptions=True)
            if not self.stopped and not self.paused:
                delay = min(30, 2 ** min(self.attempt, 5))
                self.attempt += 1
                await self.set_status(
                    "stream", "unavailable", f"Yahoo disconnected; retry in {delay}s"
                )
                await asyncio.sleep(delay)

    async def fetch_symbol(self, symbol):
        started, generation = self.clock(), self.generation
        latest = self.store.candles(symbol, 1)
        query = (
            dict(
                interval="1m",
                period1=latest[-1]["sourceTime"] // 1000 - 180,
                period2=started // 1000 + 60,
            )
            if latest
            else dict(interval="1m", range="1d")
        )
        try:
            response = await self.client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params=query,
            )
            if response.status_code != 200:
                raise ValueError(f"Yahoo HTTP {response.status_code}")
            data = response.json()
            if self.paused or self.stopped or generation != self.generation:
                return
            received = self.clock()
            normalized = normalize_chart(data, symbol, started, received)
            results = self.store.ingest_batch(normalized["observations"])
            self.symbols.setdefault(symbol, {}).update(
                **normalized["meta"],
                chartState="available",
                chartError=None,
                lastChartReceivedAt=received,
                lastCandleSourceTime=normalized["observations"][-1]["sourceTime"],
            )
            # The transaction is committed before any WebSocket publish.
            await self._emit(self.on_data, results)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self.paused and not self.stopped and generation == self.generation:
                self.symbols.setdefault(symbol, {}).update(
                    chartState="unavailable", chartError=f"{type(exc).__name__}: {exc}"
                )

    async def poll_once(self):
        for symbol in SYMBOLS:
            if self.paused or self.stopped:
                return
            await self.fetch_symbol(symbol)
        available = sum(
            self.symbols.get(s, {}).get("chartState") == "available" for s in SYMBOLS
        )
        await self.set_status(
            "chart",
            (
                "available"
                if available == len(SYMBOLS)
                else "degraded" if available else "unavailable"
            ),
            f"{available}/{len(SYMBOLS)} candle sources available",
            lastReceivedAt=self.clock(),
        )

    async def poll_loop(self):
        while not self.stopped and not self.paused:
            await self.poll_once()
            await asyncio.sleep(self.poll_ms / 1000)

    async def _cancel_tasks(self):
        tasks = [t for t in (self.stream_task, self.poll_task) if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.stream_task = self.poll_task = None

    async def pause(self):
        if self.paused:
            return
        self.paused, self.generation = True, self.generation + 1
        await self._cancel_tasks()
        for symbol in SYMBOLS:
            self.symbols.setdefault(symbol, {}).update(
                chartState="unavailable",
                chartError="Upstream intentionally disconnected for demonstration",
            )
        for channel in ("stream", "chart"):
            await self.set_status(
                channel,
                "unavailable",
                "Demonstration: upstream connections intentionally disconnected",
            )

    async def resume(self):
        if not self.paused or self.stopped:
            return
        self.paused = False
        self._launch()

    async def stop(self):
        self.stopped, self.generation = True, self.generation + 1
        await self._cancel_tasks()
        if self.owns_client:
            await self.client.aclose()

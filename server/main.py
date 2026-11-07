"""FastAPI HTTP/WebSocket application, with optional production Vue assets."""

from __future__ import annotations

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .store import MAX_SAFE_INTEGER, MarketStore
from .yahoo import SYMBOLS, YahooFeed, now_ms

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class DemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["disconnect", "reconnect"]


def same_origin(headers):
    # Vite forwards the browser-facing host with a same-origin proxy in dev.
    return not headers.get("origin") or headers["origin"] in (
        f"http://{headers.get('host')}",
        f"https://{headers.get('host')}",
    )


def create_app(
    *,
    store=None,
    demo_controls=None,
    poll_ms=None,
    feed_factory=YahooFeed,
    serve_client=None,
):
    demo_controls = (
        os.getenv("ENABLE_DEMO_CONTROLS", "false").lower() == "true"
        if demo_controls is None
        else demo_controls
    )
    poll_ms = (
        int(os.getenv("POLL_INTERVAL_MS", "15000")) if poll_ms is None else poll_ms
    )
    if poll_ms < 10000:
        raise ValueError("POLL_INTERVAL_MS must be >=10000")
    serve_client = (
        os.getenv("APP_ENV") == "production" if serve_client is None else serve_client
    )
    queues = set()
    owned_store = store is None

    async def publish(message):
        # Commit has already completed. Bounded per-client queues isolate slow
        # readers from the provider; reconnect restores a fresh snapshot.
        for queue in tuple(queues):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def on_data(results):
        await publish(
            dict(type="observations", results=results, stats=app.state.store.stats())
        )

    async def on_status(status):
        await publish(dict(type="status", status=status, serverTime=now_ms()))

    async def heartbeat():
        while True:
            await asyncio.sleep(5)
            await publish(
                dict(
                    type="heartbeat",
                    serverTime=now_ms(),
                    status=app.state.feed.status(),
                    stats=app.state.store.stats(),
                )
            )

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = store or MarketStore(
            os.getenv("DATABASE_PATH", "./data/market.sqlite")
        )
        app.state.feed = feed_factory(
            store=app.state.store, poll_ms=poll_ms, on_data=on_data, on_status=on_status
        )
        app.state.publish = publish
        await app.state.feed.start()
        ticker = asyncio.create_task(heartbeat())
        try:
            yield
        finally:
            ticker.cancel()
            await asyncio.gather(ticker, return_exceptions=True)
            await app.state.feed.stop()
            if owned_store:
                app.state.store.close()

    app = FastAPI(title="Marketstation", version="1.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse(status_code=400, content={"error": str(exc)})

    def valid_symbol(symbol):
        if symbol not in SYMBOLS:
            raise HTTPException(
                status_code=400, detail="Choose BTC-USD, ETH-USD, SPY, or AAPL"
            )
        return symbol

    @app.get("/api/health")
    async def health():
        return dict(
            ok=True,
            serverTime=now_ms(),
            stats=app.state.store.stats(),
            feed=app.state.feed.status(),
            demoControls=demo_controls,
            stack={"frontend": "Vue 3", "backend": "FastAPI", "database": "SQLite"},
        )

    @app.get("/api/candles")
    async def candles(symbol: str, limit: int = Query(360, ge=1, le=1440)):
        valid_symbol(symbol)
        return dict(
            symbol=symbol,
            candles=app.state.store.candles(symbol, limit),
            quote=app.state.store.quote(symbol),
        )

    @app.get("/api/receipts")
    async def receipts(symbol: str, limit: int = Query(12, ge=1, le=100)):
        valid_symbol(symbol)
        return dict(receipts=app.state.store.recent(symbol, limit))

    @app.get("/api/events")
    async def events():
        return dict(events=app.state.store.events())

    @app.get("/api/replay")
    async def replay(
        symbol: str,
        after: int = Query(0, ge=0, le=MAX_SAFE_INTEGER),
        until: int | None = Query(None, ge=0, le=MAX_SAFE_INTEGER),
        limit: int = Query(500, ge=1, le=2000),
    ):
        valid_symbol(symbol)
        high = app.state.store.stats()["lastReceiptId"] if until is None else until
        records = app.state.store.replay(symbol, after=after, until=high, limit=limit)
        return dict(
            mode="recorded",
            symbol=symbol,
            until=high,
            records=records,
            nextAfter=records[-1]["receiptId"] if records else after,
            done=len(records) < limit,
        )

    @app.post("/api/demo/feed")
    async def demo_feed(request: Request, body: DemoAction):
        if not demo_controls:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Demo controls are disabled. Set ENABLE_DEMO_CONTROLS=true locally."
                },
            )
        if not same_origin(request.headers):
            return JSONResponse(
                status_code=403, content={"error": "Same-origin request required"}
            )
        if body.action == "disconnect":
            await app.state.feed.pause()
        else:
            await app.state.feed.resume()
        return dict(feed=app.state.feed.status())

    @app.websocket("/ws")
    async def client_socket(websocket: WebSocket):
        if not same_origin(websocket.headers):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        queue = asyncio.Queue(maxsize=64)
        queues.add(queue)

        async def sender():
            while True:
                item = await queue.get()
                if item is None:
                    await websocket.close(
                        code=1013, reason="Slow client; reconnect for snapshot"
                    )
                    return
                await asyncio.wait_for(websocket.send_json(item), timeout=5)

        async def receiver():
            while True:
                # No market write commands are accepted on the client socket.
                text = await websocket.receive_text()
                if len(text) > 4096:
                    await websocket.close(code=1009)
                    return

        tasks = []
        try:
            await websocket.send_json(
                dict(
                    type="snapshot",
                    serverTime=now_ms(),
                    status=app.state.feed.status(),
                    stats=app.state.store.stats(),
                    demoControls=demo_controls,
                    symbols=[
                        dict(
                            symbol=s,
                            candles=app.state.store.candles(s),
                            quote=app.state.store.quote(s),
                            receipts=app.state.store.recent(s),
                        )
                        for s in SYMBOLS
                    ],
                )
            )
            tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (
            WebSocketDisconnect,
            RuntimeError,
            TimeoutError,
            asyncio.CancelledError,
        ):
            pass
        finally:
            queues.discard(queue)
            for task in tasks:
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks, return_exceptions=True)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def missing_api(rest):
        return JSONResponse(status_code=404, content={"error": "Unknown API route"})

    if serve_client:
        dist = ROOT / "dist"
        if not (dist / "index.html").exists():
            raise ValueError("Run npm run build before npm start")
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{rest:path}")
        async def frontend(rest):
            return FileResponse(dist / "index.html")

    return app


# A factory keeps database initialization inside FastAPI's lifespan, including tests.
if __name__ == "__main__":
    import uvicorn

    os.environ["APP_ENV"] = "production"
    uvicorn.run(
        "server.main:create_app",
        factory=True,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "3000")),
        workers=1,
    )

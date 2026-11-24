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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .store import MAX_SAFE_INTEGER, MarketStore
from .simulation import Simulations
from .ai import AIAssistant
from .ai_provider import OpenAIProvider, ProviderError
from .yahoo import SYMBOLS, YahooFeed, now_ms

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class DemoAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["disconnect", "reconnect"]


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    symbol: str
    mode: Literal["paper", "backtest"] = "backtest"
    fast: int = Field(9, ge=2, le=199)
    slow: int = Field(21, ge=3, le=200)
    initialCash: float = Field(10000, ge=100, le=1000000, multiple_of=0.01)
    feeBps: float = Field(10, ge=0, le=100)
    slippageBps: float = Field(5, ge=0, le=100)

    @model_validator(mode="after")
    def valid_windows(self):
        if self.fast >= self.slow:
            raise ValueError("Fast SMA must be shorter than slow SMA")
        return self


class AIAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str
    fast: int = Field(9, ge=2, le=199)
    slow: int = Field(21, ge=3, le=200)

    @model_validator(mode="after")
    def valid_windows(self):
        if self.fast >= self.slow:
            raise ValueError("Fast SMA must be shorter than slow SMA")
        return self


class AIControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    running: bool


class AIDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    botId: str = Field(min_length=1, max_length=64)
    requestId: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    execute: bool = True


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


class AIVisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str
    image: str = Field(min_length=30, max_length=2_800_000)
    message: str = Field(
        "Explain this chart and its moving averages.", min_length=1, max_length=2000
    )


class AudioEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sessionId: int = Field(ge=1)
    state: Literal["connected", "ended", "failure", "injected_failure"]
    detail: str = Field(min_length=1, max_length=300)


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
    ai_provider=None,
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
        app.state.simulations.sync()
        app.state.assistant.sync()
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

    async def automation():
        while True:
            await asyncio.sleep(2)
            try:
                await app.state.assistant.tick()
            except (ValueError, KeyError):
                # A control transition can invalidate a scheduled check.
                pass

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = store or MarketStore(
            os.getenv("DATABASE_PATH", "./data/market.sqlite")
        )
        app.state.simulations = Simulations(app.state.store)
        app.state.simulations.sync()
        app.state.feed = feed_factory(
            store=app.state.store, poll_ms=poll_ms, on_data=on_data, on_status=on_status
        )
        app.state.ai_provider = ai_provider or OpenAIProvider()
        app.state.assistant = AIAssistant(
            app.state.store, app.state.ai_provider, app.state.feed.status
        )
        app.state.publish = publish
        await app.state.feed.start()
        ticker = asyncio.create_task(heartbeat())
        bot_task = asyncio.create_task(automation())
        try:
            yield
        finally:
            ticker.cancel()
            bot_task.cancel()
            await asyncio.gather(ticker, bot_task, return_exceptions=True)
            await app.state.feed.stop()
            if ai_provider is None:
                await app.state.ai_provider.close()
            if owned_store:
                app.state.store.close()

    app = FastAPI(title="Marketstation", version="1.2.0", lifespan=lifespan)

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(ProviderError)
    async def bad_provider(request, exc):
        return JSONResponse(status_code=503, content={"error": str(exc)})

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

    def protect_ai(request):
        if not same_origin(request.headers):
            raise HTTPException(403, "Same-origin request required")
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 3_000_000:
            raise HTTPException(413, "AI request is too large")

    def known_bot(bot_id):
        try:
            return app.state.assistant.get_bot(bot_id)
        except KeyError:
            raise HTTPException(404, "AI simulated account not found")

    @app.get("/api/ai/status")
    async def ai_status(symbol: str):
        valid_symbol(symbol)
        app.state.assistant.sync()
        return dict(
            **app.state.ai_provider.status(),
            context=app.state.assistant.context(symbol),
            bot=app.state.assistant.bot_for(symbol),
            activities=app.state.assistant.activities(symbol),
            demoControls=demo_controls,
        )

    @app.post("/api/ai/bots")
    async def ai_bot(request: Request, body: AIAccountRequest):
        protect_ai(request)
        valid_symbol(body.symbol)
        return app.state.assistant.ensure_bot(body.symbol, body.fast, body.slow)

    @app.post("/api/ai/bots/{bot_id}/control")
    async def ai_control(bot_id: str, request: Request, body: AIControl):
        protect_ai(request)
        known_bot(bot_id)
        return app.state.assistant.set_running(bot_id, body.running)

    @app.post("/api/ai/decision")
    async def ai_decision(request: Request, body: AIDecisionRequest):
        protect_ai(request)
        known_bot(body.botId)
        return await app.state.assistant.decide(
            body.botId, body.requestId, body.execute
        )

    @app.post("/api/ai/chat")
    async def ai_chat(request: Request, body: AIChatRequest):
        protect_ai(request)
        valid_symbol(body.symbol)
        return await app.state.assistant.interact(
            body.symbol,
            body.message,
            history=[turn.model_dump() for turn in body.history],
        )

    @app.post("/api/ai/vision")
    async def ai_vision(request: Request, body: AIVisionRequest):
        protect_ai(request)
        valid_symbol(body.symbol)
        return await app.state.assistant.interact(
            body.symbol, body.message, image=body.image
        )

    @app.post("/api/ai/realtime")
    async def ai_audio(request: Request, symbol: str):
        protect_ai(request)
        valid_symbol(symbol)
        if request.headers.get("content-type", "").split(";")[0] != "application/sdp":
            raise HTTPException(415, "Audio setup requires application/sdp")
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 64_000:
                raise HTTPException(413, "Audio session offer is too large")
        try:
            sdp = payload.decode("utf-8")
        except UnicodeError:
            raise HTTPException(400, "Invalid audio session offer")
        if not sdp.startswith("v=0") or "m=audio" not in sdp:
            raise HTTPException(400, "Invalid audio session offer")
        answer, session_id = await app.state.assistant.audio(symbol, sdp)
        return Response(
            answer,
            media_type="application/sdp",
            headers={"X-Audio-Session": str(session_id)},
        )

    @app.post("/api/ai/audio-events")
    async def audio_event(request: Request, body: AudioEvent):
        protect_ai(request)
        try:
            session = app.state.assistant.activity(body.sessionId)
        except KeyError:
            raise HTTPException(404, "Audio session not found")
        if session["kind"] != "audio" or session["status"] != "negotiated":
            raise HTTPException(400, "Not an audio-session identity")
        if body.state == "injected_failure" and not demo_controls:
            raise HTTPException(403, "Demo controls are disabled")
        return app.state.assistant.record(
            session["symbol"],
            "audio",
            body.state,
            dict(sessionId=body.sessionId),
            dict(
                reason=body.detail,
                evidence="injected-browser-failure"
                if body.state == "injected_failure"
                else "browser-reported",
                model=app.state.ai_provider.audio_model,
            ),
        )

    @app.post("/api/simulations")
    def create_simulation(request: Request, body: Experiment):
        if not same_origin(request.headers):
            raise HTTPException(403, "Same-origin request required")
        valid_symbol(body.symbol)
        return app.state.simulations.create(body.model_dump())

    @app.get("/api/simulations")
    def list_simulations(symbol: str):
        valid_symbol(symbol)
        return dict(runs=app.state.simulations.list(symbol))

    @app.get("/api/simulations/{run_id}")
    def simulation(run_id: str):
        try:
            return app.state.simulations.get(run_id)
        except KeyError:
            raise HTTPException(404, "Simulation not found")

    @app.post("/api/simulations/{run_id}/pause")
    def pause_simulation(run_id: str, request: Request):
        if not same_origin(request.headers):
            raise HTTPException(403, "Same-origin request required")
        try:
            return app.state.simulations.pause(run_id)
        except KeyError:
            raise HTTPException(404, "Simulation not found")

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

    @app.get("/api/replay/recent")
    def recent_replay(symbol: str, limit: int = Query(800, ge=1, le=2000)):
        valid_symbol(symbol)
        return dict(
            mode="recorded",
            symbol=symbol,
            **app.state.store.recent_replay(symbol, limit),
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

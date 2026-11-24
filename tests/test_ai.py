"""Injected-provider checks. These are NOT evidence of a live model/audio call."""

import asyncio
from contextlib import asynccontextmanager
import base64
import json
import struct

import httpx
import pytest
from fastapi.testclient import TestClient

from server.ai import AIAssistant, image_metadata
from server.ai_provider import ModelDecision, GeminiProvider, ProviderError
from server.main import create_app
from server.store import MarketStore
from tests.test_app import FakeFeed
from tests.test_store import T, candle


class MockProvider:
    configured = True
    model = "mock-decision"
    audio_model = "mock-realtime"

    def __init__(self):
        self.calls = []
        self.action = "buy"
        self.confidence = 0.9
        self.bad = None
        self.failure = False
        self.hook = None

    def status(self):
        return dict(
            provider="mock",
            configured=self.configured,
            model=self.model,
            audioModel=self.audio_model,
        )

    async def respond(self, context, message, **options):
        self.calls.append((context, message, options))
        if self.hook:
            await self.hook()
        if self.failure:
            raise ProviderError("Injected provider outage")
        text = (
            self.bad
            if self.bad is not None
            else json.dumps(
                dict(
                    action=self.action,
                    symbol=context["symbol"],
                    snapshotId=context["snapshotId"],
                    confidence=self.confidence,
                    reason="The completed-bar SMA candidate agrees; this is only a simulation.",
                )
            )
            if options.get("decision")
            else "Mock explanation grounded in the supplied snapshot."
        )
        return dict(
            text=text,
            model=self.model,
            responseId="mock-response",
            usage={},
            evidence="mock",
            provider="mock",
        )

    @asynccontextmanager
    async def voice(self, context):
        if self.failure:
            raise ProviderError("Injected audio session outage")
        self.calls.append((context, "voice", {}))

        class MockSocket:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send(self, raw):
                message = json.loads(raw)
                content = {
                    "modelTurn": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "audio/pcm;rate=24000",
                                    "data": base64.b64encode(bytes(480)).decode(),
                                }
                            }
                        ]
                    },
                    "outputTranscription": {
                        "text": "Mock simulated-account explanation."
                    },
                    "turnComplete": True,
                }
                if "realtimeInput" in message:
                    content["inputTranscription"] = dict(
                        text="Explain this simulated account."
                    )
                await self.queue.put(json.dumps(dict(serverContent=content)))

            def __aiter__(self):
                return self

            async def __anext__(self):
                return await self.queue.get()

        yield MockSocket()


def seed(store):
    rows = []
    for index in range(25):
        at, price = T + index * 60_000, 100 + index
        rows.append(
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
        )
    store.ingest_batch(rows)


@pytest.fixture
def stack():
    store = MarketStore(":memory:")
    seed(store)
    clock = [T + 25 * 60_000 + 10_000]
    feed = dict(
        paused=False,
        stream=dict(state="streaming"),
        symbols={"BTC-USD": dict(chartState="available")},
    )
    provider = MockProvider()
    feed["symbols"]["BTC-USD"].update(
        lastQuoteSourceTime=clock[0] - 1000, lastQuoteReceivedAt=clock[0] - 1000
    )
    quote(store, clock[0] - 1000)
    assistant = AIAssistant(store, provider, lambda: feed, lambda: clock[0])
    bot = assistant.ensure_bot("BTC-USD")
    yield assistant, provider, store, clock, feed, bot
    store.close()


def quote(store, at, price=125, received=None):
    return store.ingest_batch(
        [
            dict(
                source="yahoo-stream",
                kind="quote",
                symbol="BTC-USD",
                interval="tick",
                sourceTime=at,
                receivedAt=received if received is not None else at,
                orderingTime=at,
                payload=dict(price=price),
            )
        ]
    )[0]


async def test_checked_decision_fills_only_a_later_quote_and_reconciles(stack):
    ai, provider, store, clock, _, bot = stack
    before = store.stats()
    result = await ai.decide(bot["id"], "request-valid")
    assert result["status"] == "queued"
    assert all(c["passed"] for c in result["response"]["checks"])
    assert len(provider.calls) == 1
    assert ai.get_bot(bot["id"])["fills"] == []
    ai.sync()
    assert ai.get_bot(bot["id"])["fills"] == []
    clock[0] += 1000
    receipt = quote(store, clock[0], 126)
    ai.sync()
    account = ai.get_bot(bot["id"])
    assert account["orders"][0]["status"] == "filled"
    assert account["fills"][0]["receiptId"] == receipt["receiptId"]
    assert receipt["receiptId"] > result["response"]["decisionWatermark"]
    assert account["account"]["cash"] >= 499.99
    assert account["account"]["fees"] > 0
    assert account["account"]["equity"] == pytest.approx(
        10000 + account["account"]["realizedPnl"] + account["account"]["unrealizedPnl"]
    )
    assert store.stats()["observations"] == before["observations"] + 1


async def test_idempotent_retry_does_not_call_model_or_queue_twice(stack):
    ai, provider, _, _, _, bot = stack
    first = await ai.decide(bot["id"], "same-request")
    second = await ai.decide(bot["id"], "same-request")
    assert first == second
    assert len(provider.calls) == 1
    assert len(ai.get_bot(bot["id"])["orders"]) == 1


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "{}",
        '{"action":"short"}',
        '{"action":"buy","symbol":"BTC-USD","snapshotId":"wrong","confidence":NaN,"reason":"invalid numeric value"}',
    ],
)
async def test_invalid_schema_is_audited_without_action(stack, bad):
    ai, provider, _, _, _, bot = stack
    provider.bad = bad
    result = await ai.decide(bot["id"], "invalid-response")
    assert result["status"] == "rejected"
    assert ai.get_bot(bot["id"])["account"]["cash"] == 10000
    assert ai.get_bot(bot["id"])["orders"] == []


@pytest.mark.parametrize("action,confidence", [("sell", 0.9), ("buy", 0.59)])
async def test_sma_and_confidence_veto(stack, action, confidence):
    ai, provider, _, _, _, bot = stack
    provider.action, provider.confidence = action, confidence
    result = await ai.decide(bot["id"], "veto-response")
    assert result["status"] == "rejected"
    assert ai.get_bot(bot["id"])["orders"] == []


async def test_wrong_identity_and_extra_fields_are_rejected(stack):
    ai, provider, _, _, _, bot = stack

    async def wrong():
        context = provider.calls[-1][0]
        provider.bad = json.dumps(
            dict(
                action="buy",
                symbol="AAPL",
                snapshotId=context["snapshotId"],
                confidence=0.9,
                reason="Incorrect response symbol must be rejected",
            )
        )

    provider.hook = wrong
    result = await ai.decide(bot["id"], "wrong-identity")
    assert result["status"] == "rejected"
    assert not result["response"]["checks"][0]["passed"]
    with pytest.raises(ValueError):
        ModelDecision.model_validate(
            dict(
                action="hold",
                symbol="BTC-USD",
                snapshotId="id",
                confidence=0.9,
                reason="This should not include a quantity",
                quantity=10,
            )
        )


async def test_hold_leaves_account_unchanged(stack):
    ai, provider, _, _, _, bot = stack
    provider.action = "hold"
    result = await ai.decide(bot["id"], "hold-response")
    assert result["status"] == "hold"
    assert ai.get_bot(bot["id"])["orders"] == []


async def test_review_can_call_model_on_recorded_data_but_never_trade(stack):
    ai, provider, _, clock, feed, bot = stack
    clock[0] += 1_000_000
    feed["paused"] = True
    result = await ai.decide(bot["id"], "review-response", execute=False)
    assert result["status"] == "review"
    assert result["context"]["market"]["dataMode"] == "stale/recorded/unavailable"
    assert len(provider.calls) == 1
    assert ai.get_bot(bot["id"])["orders"] == []


async def test_stale_feed_is_skipped_before_model_call(stack):
    ai, provider, _, clock, _, bot = stack
    clock[0] += 70_000
    result = await ai.decide(bot["id"], "stale-response")
    assert result["status"] == "skipped"
    assert provider.calls == []


async def test_fresh_cached_quote_without_a_current_symbol_message_is_not_live(stack):
    ai, provider, _, _, feed, bot = stack
    feed["symbols"]["BTC-USD"]["lastQuoteSourceTime"] = None
    result = await ai.decide(bot["id"], "cached-not-live")
    assert result["status"] == "skipped"
    assert result["context"]["market"]["dataMode"] == "stale/recorded/unavailable"
    assert provider.calls == []


async def test_service_outage_is_audited_and_keeps_cash(stack):
    ai, provider, _, _, _, bot = stack
    provider.failure = True
    result = await ai.decide(bot["id"], "unavailable-response")
    assert result["status"] == "unavailable"
    assert ai.get_bot(bot["id"])["account"]["cash"] == 10000


@pytest.mark.parametrize("change", ["pause", "outage", "revision", "timeout"])
async def test_inflight_response_cannot_apply_after_context_changes(stack, change):
    ai, provider, store, clock, feed, bot = stack
    ai.set_running(bot["id"], True)

    async def mutate():
        if change == "pause":
            ai.set_running(bot["id"], False)
        elif change == "outage":
            feed["paused"] = True
        elif change == "timeout":
            clock[0] += 46_000
        else:
            bar = store.candles("BTC-USD")[-1]
            store.ingest_batch(
                [
                    candle(
                        sourceTime=bar["sourceTime"],
                        receivedAt=clock[0],
                        orderingTime=clock[0],
                        payload=dict(
                            open=125,
                            high=127,
                            low=123,
                            close=126,
                            volume=12,
                            complete=True,
                        ),
                    )
                ]
            )

    provider.hook = mutate
    result = await ai.decide(bot["id"], "changed-response")
    assert result["status"] == "rejected"
    assert ai.get_bot(bot["id"])["orders"] == []


async def test_late_historical_quote_cannot_fill_and_pause_cancels_order(stack):
    ai, _, store, clock, _, bot = stack
    await ai.decide(bot["id"], "future-only")
    quote(store, clock[0], received=clock[0] - 1)
    ai.sync()
    assert ai.get_bot(bot["id"])["fills"] == []
    ai.set_running(bot["id"], True)
    assert ai.get_bot(bot["id"])["orders"][0]["status"].startswith("cancelled")


async def test_automation_checks_once_per_completed_candle(stack):
    ai, provider, _, _, _, bot = stack
    provider.action = "hold"
    ai.set_running(bot["id"], True)
    await ai.tick()
    await ai.tick()
    assert len(provider.calls) == 1
    assert ai.get_bot(bot["id"])["autoCalls"] == 1


async def test_restart_preserves_audit_account_and_disarms_automation(stack):
    ai, provider, store, clock, feed, bot = stack
    ai.set_running(bot["id"], True)
    result = await ai.decide(bot["id"], "restart-response")
    restarted = AIAssistant(store, provider, lambda: feed, lambda: clock[0])
    assert not restarted.get_bot(bot["id"])["running"]
    assert restarted.get_bot(bot["id"])["orders"][0]["status"].startswith("cancelled")
    assert restarted.activity(result["id"]) == result


async def test_chat_and_vision_are_grounded_and_read_only(stack):
    ai, provider, store, _, _, bot = stack
    before = store.stats()
    png = (
        "data:image/png;base64,"
        + base64.b64encode(
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 100, 100)
            + b"mock-png"
        ).decode()
    )
    chat = await ai.interact("BTC-USD", "Explain my account")
    vision = await ai.interact("BTC-USD", "Explain this chart", image=png)
    assert chat["context"]["account"]["cash"] == 10000
    assert vision["context"]["chartImage"]["width"] == 100
    assert provider.calls[-1][2]["image"] == png
    assert ai.get_bot(bot["id"])["orders"] == []
    assert store.stats() == before
    assert png not in json.dumps(ai.activities("BTC-USD"))
    with pytest.raises(ValueError):
        image_metadata("https://example.test/not-an-upload.png")


def test_http_validation_origin_and_audio_outage_are_distinct_from_live_evidence():
    store, provider = MarketStore(":memory:"), MockProvider()
    app = create_app(
        store=store, feed_factory=FakeFeed, serve_client=False, ai_provider=provider
    )
    with TestClient(app) as client:
        bot = client.post("/api/ai/bots", json={"symbol": "BTC-USD"}).json()
        assert (
            client.post("/api/ai/bots", json={"symbol": "BTC-USD"}).json()["id"]
            == bot["id"]
        )
        assert (
            client.post(
                "/api/ai/bots", json={"symbol": "BTC-USD", "fast": 21, "slow": 9}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/ai/bots",
                json={"symbol": "BTC-USD"},
                headers={"Origin": "https://foreign.test"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/ai/decision",
                json={"botId": "missing", "requestId": "valid-request"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/ai/vision",
                json={"symbol": "BTC-USD", "image": "https://example.test/chart.png"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/ai/realtime?symbol=BTC-USD", content="invalid"
            ).status_code
            == 404
        )
        provider.failure = True
        with client.websocket_connect("/ws/ai/voice?symbol=BTC-USD") as socket:
            error = socket.receive_json()
            assert (
                error["type"] == "error"
                and "Injected audio session outage" in error["detail"]
            )
        activity = client.get("/api/ai/status?symbol=BTC-USD").json()["activities"][0]
        assert activity["kind"] == "audio" and activity["status"] == "failure"
    store.close()


def mock_settings(name, default=""):
    return {
        "GEMINI_API_KEY": "AIza-test-not-a-real-secret-value",
        "GEMINI_MODEL": "gemini-3.5-flash-lite",
        "GEMINI_FREE_TIER_CONFIRMED": "true",
    }.get(name, default)


@pytest.mark.parametrize("failure", [401, 429, 503, "timeout", "envelope", "refusal"])
async def test_provider_failures_are_redacted(monkeypatch, failure):
    monkeypatch.setattr("server.ai_provider.setting", mock_settings)

    def transport(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive transport details", request=request)
        if failure == "envelope":
            return httpx.Response(
                200,
                json={
                    "candidates": [{"finishReason": "STOP", "content": {"parts": []}}]
                },
            )
        if failure == "refusal":
            return httpx.Response(200, json={"candidates": []})
        return httpx.Response(
            failure, text="Do not expose this provider body or credentials"
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(ProviderError) as caught:
            await GeminiProvider(client).respond({}, "test")
        assert "real-secret" not in str(caught.value)
        assert "sensitive" not in str(caught.value)
        assert "provider body" not in str(caught.value)


async def test_provider_uses_strict_schema_and_keeps_key_server_side(
    monkeypatch,
):
    monkeypatch.setattr("server.ai_provider.setting", mock_settings)
    requests = []

    def transport(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert "key=" not in str(request.url)
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=dict(
                responseId="mock-id",
                modelVersion="mock-model",
                candidates=[
                    dict(
                        finishReason="STOP",
                        content=dict(parts=[dict(text="A test response")]),
                    )
                ],
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = GeminiProvider(client)
        result = await provider.respond({"simulated": True}, "Decide", decision=True)
    assert (
        requests[0]["generationConfig"]["responseJsonSchema"]["additionalProperties"]
        is False
    )
    assert "real-secret" not in json.dumps(requests)
    assert "real-secret" not in json.dumps(result)


async def test_free_quota_failure_never_falls_back_to_a_paid_provider(monkeypatch):
    monkeypatch.setattr("server.ai_provider.setting", mock_settings)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}
            )
        )
    ) as client:
        with pytest.raises(ProviderError) as caught:
            await GeminiProvider(client).respond({}, "test")
        assert caught.value.code == "RESOURCE_EXHAUSTED"
        assert "No paid fallback" in str(caught.value)


@pytest.mark.parametrize(
    "setting_name,value",
    [("GEMINI_MODEL", "gemini-4-carbon"), ("GEMINI_FREE_TIER_CONFIRMED", "false")],
)
async def test_paid_model_or_unconfirmed_project_never_makes_a_request(
    monkeypatch, setting_name, value
):
    monkeypatch.setattr(
        "server.ai_provider.setting",
        lambda name, default="": (
            value if name == setting_name else mock_settings(name, default)
        ),
    )
    calls = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: calls.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        with pytest.raises(ProviderError):
            await GeminiProvider(client).respond({}, "test")
    assert not calls


def test_additive_schema_preserves_market_and_saved_simulations(tmp_path):
    from server.simulation import Simulations

    path = tmp_path / "existing.sqlite"
    original = MarketStore(path)
    seed(original)
    Simulations(original).create(
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
    tables = ("observations", "receipts", "heads", "simulation_runs")
    before = {
        name: [tuple(row) for row in original.db.execute("SELECT * FROM " + name)]
        for name in tables
    }
    original.db.execute("DROP TABLE ai_activity")
    original.db.execute("DROP TABLE ai_bots")
    original.close()
    migrated = MarketStore(path)
    after = {
        name: [tuple(row) for row in migrated.db.execute("SELECT * FROM " + name)]
        for name in tables
    }
    assert before == after
    assert migrated.db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    migrated.close()


def test_voice_bridge_pcm_transcripts_injection_and_reconnect_are_mocked():
    store, provider = MarketStore(":memory:"), MockProvider()
    app = create_app(
        store=store,
        feed_factory=FakeFeed,
        serve_client=False,
        ai_provider=provider,
        demo_controls=True,
    )

    def turn(socket, input_expected):
        assert socket.receive_bytes() == bytes(480)
        if input_expected:
            assert socket.receive_json()["role"] == "user"
        assert socket.receive_json()["role"] == "assistant"
        assert socket.receive_json()["type"] == "turn_complete"

    with TestClient(app) as client:
        for injected in (True, False):
            with client.websocket_connect("/ws/ai/voice?symbol=BTC-USD") as socket:
                ready = socket.receive_json()
                assert (ready["inputRate"], ready["outputRate"]) == (16000, 24000)
                turn(socket, False)
                socket.send_bytes(bytes(3200))
                turn(socket, True)
                socket.send_json({"type": "inject_failure" if injected else "end"})
                if injected:
                    assert "Injected" in socket.receive_json()["detail"]
            activities = client.get("/api/ai/status?symbol=BTC-USD").json()[
                "activities"
            ]
            ended = next(
                a
                for a in activities
                if a["context"].get("sessionId") == ready["sessionId"]
            )
            assert ended["status"] == ("injected_failure" if injected else "ended")
            assert ended["response"]["inputBytes"] == 3200
            assert ended["response"]["outputBytes"] == 960
            assert ended["response"]["inputTranscriptObserved"]
            assert ended["response"]["completedTurns"] == 2
    store.close()


def test_voice_foreign_origin_single_session_and_invalid_frame_are_rejected():
    from starlette.websockets import WebSocketDisconnect

    store, provider = MarketStore(":memory:"), MockProvider()
    app = create_app(
        store=store,
        feed_factory=FakeFeed,
        serve_client=False,
        ai_provider=provider,
        demo_controls=False,
    )
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/ai/voice?symbol=BTC-USD",
                headers={"Origin": "https://foreign.test"},
            ):
                pass
        assert not provider.calls
        with client.websocket_connect("/ws/ai/voice?symbol=BTC-USD") as first:
            assert first.receive_json()["type"] == "ready"
            with client.websocket_connect("/ws/ai/voice?symbol=BTC-USD") as second:
                assert "already active" in second.receive_json()["detail"]
            assert len(provider.calls) == 1
            # Consume the mock greeting before checking malformed microphone PCM.
            first.receive_bytes()
            first.receive_json()
            first.receive_json()
            first.send_bytes(b"odd")
            assert "Invalid audio frame" in first.receive_json()["detail"]
    store.close()


async def test_live_vision_keeps_image_and_question_in_one_turn(monkeypatch):
    monkeypatch.setattr("server.ai_provider.setting", mock_settings)
    messages = []

    class Socket:
        async def send(self, raw):
            messages.append(json.loads(raw))

        async def recv(self):
            return '{"setupComplete":{}}'

        def __aiter__(self):
            return self

        async def __anext__(self):
            return json.dumps(
                {
                    "serverContent": {
                        "outputTranscription": {"text": "Mock image interpretation."},
                        "turnComplete": True,
                    }
                }
            )

    @asynccontextmanager
    async def connector(url, **kwargs):
        assert url.startswith("wss://generativelanguage.googleapis.com/")
        assert "key=" not in url
        assert kwargs["ssl"].check_hostname
        yield Socket()

    p = GeminiProvider(voice_connector=connector)
    try:
        result = await p.respond(
            {"simulated": True}, "Describe image", image="data:image/png;base64,TEST"
        )
        assert result["text"] == "Mock image interpretation."
        assert result["requestedModel"] == "gemini-3.8-live"
        parts = messages[1]["clientContent"]["turns"][0]["parts"]
        assert parts[0]["inlineData"] == {"mimeType": "image/png", "data": "TEST"}
        assert "Describe image" in parts[1]["text"]
        assert "real-secret" not in json.dumps(messages)
    finally:
        await p.close()


async def test_transient_capacity_retries_once_same_model_but_quota_never_retries(
    monkeypatch,
):
    monkeypatch.setattr("server.ai_provider.setting", mock_settings)
    for failure, expected in [(503, 2), (429, 1)]:
        calls = []

        def transport(request):
            calls.append(str(request.url))
            return httpx.Response(failure, json={"error": {"status": "UNAVAILABLE"}})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            with pytest.raises(ProviderError):
                await GeminiProvider(client).respond({}, "test")
        assert len(calls) == expected
        assert len(set(calls)) == 1
        assert all("gemini-3.5-flash-lite:generateContent" in url for url in calls)

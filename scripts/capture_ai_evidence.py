"""Opt-in real-provider verification against the local app; never mocks success.

Uses the explicitly confirmed Gemini free tier and the application voice proxy.
Label the optional WAV origin; this probe does not claim browser-microphone proof.
"""

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import uuid
import wave

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from server.ai import image_metadata
from server.ai_provider import ProviderError


async def audio_probe(base, symbol, path, description):
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (
            1,
            2,
            16000,
        ):
            raise ValueError("Verification WAV must be mono PCM16 at 16 kHz")
        pcm = wav.readframes(wav.getnframes())
    if not 3200 <= len(pcm) <= 960000:
        raise ValueError("Verification audio must be 0.1–30 seconds")
    chunks, transcripts, ready = [], [], None
    started = time.monotonic()
    async with asyncio.timeout(65):
        async with connect(
            base.replace("http", "ws", 1) + "/ws/ai/voice?symbol=" + symbol,
            origin=base,
            max_size=2_000_000,
            open_timeout=15,
        ) as socket:

            async def turn():
                nonlocal ready
                async for raw in socket:
                    if isinstance(raw, bytes):
                        chunks.append(raw)
                        continue
                    event = json.loads(raw)
                    if event["type"] == "error":
                        raise ProviderError(event["detail"])
                    if event["type"] == "ready":
                        ready = event
                    if event["type"] == "transcript":
                        transcripts.append(dict(role=event["role"], text=event["text"]))
                    if event["type"] == "turn_complete":
                        return
                raise ProviderError("Voice connection closed before the turn completed")

            await turn()  # Observe the initial spoken greeting, then send audio.
            greeting = list(transcripts)
            transcripts.clear()
            chunks.clear()
            for offset in range(0, len(pcm), 3200):
                await socket.send(pcm[offset : offset + 3200])
                await asyncio.sleep(0.1)
            for _ in range(12):
                await socket.send(bytes(3200))
                await asyncio.sleep(0.1)
            await turn()
            await socket.send(json.dumps(dict(type="end")))
    output = b"".join(chunks)
    incoming = " ".join(t["text"] for t in transcripts if t["role"] == "user")
    outgoing = " ".join(t["text"] for t in transcripts if t["role"] == "assistant")
    if not output or not incoming or not outgoing or ready is None:
        raise ProviderError(
            "Two-way audio/transcripts were incomplete; no success is claimed"
        )
    target = Path("data/part-4-3-audio-response.wav")
    target.parent.mkdir(exist_ok=True)
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(output)
    return dict(
        evidence="live Gemini audio through FastAPI WebSocket; not browser-microphone evidence",
        inputOrigin=description,
        requestedModel=ready["model"],
        sessionId=ready["sessionId"],
        inputSeconds=len(pcm) / 32000,
        outputSeconds=len(output) / 48000,
        outputSha256=hashlib.sha256(output).hexdigest(),
        inputTranscript=incoming,
        outputTranscript=outgoing,
        greeting=greeting,
        elapsedSeconds=round(time.monotonic() - started, 2),
    )


async def capture(args, result):
    if args.base not in (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ):
        raise ValueError("Use a supported loopback workstation URL")
    async with httpx.AsyncClient(base_url=args.base, timeout=45) as client:

        async def api(path, body=None):
            response = await (
                client.get(path) if body is None else client.post(path, json=body)
            )
            if response.is_error:
                raise ValueError(
                    "Workstation route returned HTTP " + str(response.status_code)
                )
            return response.json()

        state = await api("/api/ai/status?symbol=" + args.symbol)
        if not state["configured"]:
            raise ValueError("Configure a private provider key before this live check")
        bot = await api("/api/ai/bots", dict(symbol=args.symbol))
        decision = await api(
            "/api/ai/decision",
            dict(
                botId=bot["id"], requestId="evidence-" + uuid.uuid4().hex, execute=True
            ),
        )
        result["decision"] = decision
        if decision["status"] not in ("queued", "hold"):
            raise ValueError(
                "Live decision was "
                + decision["status"]
                + ": "
                + decision["response"].get("reason", "checks did not pass")
            )
        if decision["response"].get("evidence") != "live-provider":
            raise ValueError("A mock response cannot satisfy live-provider evidence")
        result["chat"] = await api(
            "/api/ai/chat",
            dict(
                symbol=args.symbol,
                message="Explain this simulated account and the latest checked decision. State what remains uncertain.",
            ),
        )
        if result["chat"]["status"] != "completed":
            raise ValueError("Live grounded chat did not complete")
        if args.chart:
            if time.time() - args.chart.stat().st_mtime > 600:
                raise ValueError(
                    "Capture a fresh chart PNG; the supplied image is over ten minutes old"
                )
            image = (
                "data:image/png;base64,"
                + base64.b64encode(args.chart.read_bytes()).decode()
            )
            image_metadata(image)
            result["vision"] = await api(
                "/api/ai/vision",
                dict(
                    symbol=args.symbol,
                    image=image,
                    message="Interpret this actual chart image; distinguish visible evidence, exact indicators and uncertainty.",
                ),
            )
            if result["vision"]["status"] != "completed":
                raise ValueError("Live chart interpretation did not complete")
        if decision["status"] == "queued":
            for _ in range(20):
                state = await api("/api/ai/status?symbol=" + args.symbol)
                if any(
                    o.get("activityId") == decision["id"] and o["status"] == "filled"
                    for o in state["bot"]["orders"]
                ):
                    break
                await asyncio.sleep(1)
        state = await api("/api/ai/status?symbol=" + args.symbol)
        result["resultingAccount"] = state["bot"]
        if args.audio_input:
            if not args.audio_description:
                raise ValueError(
                    "Label the audio origin with --audio-description (microphone, prerecorded, or synthetic)"
                )
            result["audio"] = await audio_probe(
                args.base, args.symbol, args.audio_input, args.audio_description
            )
        result["checks"] = dict(
            liveDecision=True,
            groundedChat=True,
            actualImageInterpreted=bool(result.get("vision")),
            providerAudioInputAndOutput=bool(result.get("audio")),
            simulatedOutcome=decision["status"] == "hold"
            or any(
                o.get("activityId") == decision["id"] and o["status"] == "filled"
                for o in state["bot"]["orders"]
            ),
            browserSpokenExchange="requires separate observed browser/user demonstration",
        )
        result["completeProviderChecks"] = all(
            v for k, v in result["checks"].items() if k != "browserSpokenExchange"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    parser.add_argument(
        "--symbol", choices=("BTC-USD", "ETH-USD", "SPY", "AAPL"), default="BTC-USD"
    )
    parser.add_argument("--chart", type=Path)
    parser.add_argument("--audio-input", type=Path)
    parser.add_argument("--audio-description")
    parser.add_argument(
        "--output", type=Path, default=Path("data/part-4-3-live-run.json")
    )
    args = parser.parse_args()
    result = dict(
        capturedAt=datetime.now(timezone.utc).isoformat(),
        evidence="Actual provider requests; failures never become mocked successes",
        completeProviderChecks=False,
    )
    try:
        asyncio.run(capture(args, result))
    except (
        ValueError,
        ProviderError,
        httpx.HTTPError,
        TimeoutError,
        OSError,
        WebSocketException,
    ) as exc:
        # Our messages are bounded; do not print request/header exception reprs.
        result["failure"] = (
            str(exc)[:600]
            if isinstance(exc, (ValueError, ProviderError))
            else "Network, file, or audio probe failed; inspect the local environment"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                completeProviderChecks=result["completeProviderChecks"],
                failure=result.get("failure"),
                checks=result.get("checks"),
            ),
            indent=2,
        )
    )
    raise SystemExit(0 if result["completeProviderChecks"] else 1)

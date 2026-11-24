"""Opt-in real-provider verification against the local app; never mocks success.

Calls can consume paid API credits. An optional WAV is uploaded to Realtime;
label its origin explicitly. This probe does not claim browser-microphone proof.
"""

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import time
import uuid
import wave

import certifi
import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from server.ai import image_metadata
from server.ai_provider import OpenAIProvider, ProviderError, setting


async def audio_probe(context, path, description):
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (
            1,
            2,
            24000,
        ):
            raise ValueError("Verification WAV must be mono PCM16 at 24 kHz")
        pcm = wav.readframes(wav.getnframes())
    if not 4800 <= len(pcm) <= 1_440_000:
        raise ValueError("Verification audio must be 0.1–30 seconds")
    provider = OpenAIProvider()
    chunks, transcript, input_transcript, actual_model = [], "", "", None
    started = time.monotonic()
    try:
        async with asyncio.timeout(55):
            async with connect(
                "wss://api.openai.com/v1/realtime?model=" + provider.audio_model,
                additional_headers={
                    "Authorization": "Bearer " + setting("OPENAI_API_KEY")
                },
                ssl=ssl.create_default_context(cafile=certifi.where()),
                max_size=4_000_000,
                open_timeout=15,
            ) as socket:
                session = provider.realtime_session(context)
                session["audio"]["input"].update(
                    format={"type": "audio/pcm", "rate": 24000}, turn_detection=None
                )
                session["audio"]["output"]["format"] = {
                    "type": "audio/pcm",
                    "rate": 24000,
                }
                await socket.send(
                    json.dumps(dict(type="session.update", session=session))
                )
                async for raw in socket:
                    event = json.loads(raw)
                    if event["type"] == "error":
                        raise ProviderError(
                            "The live Realtime probe returned a provider error. No audio success is claimed."
                        )
                    if event["type"] == "session.updated":
                        actual_model = event.get("session", {}).get("model")
                        break
                for offset in range(0, len(pcm), 9600):
                    await socket.send(
                        json.dumps(
                            dict(
                                type="input_audio_buffer.append",
                                audio=base64.b64encode(
                                    pcm[offset : offset + 9600]
                                ).decode(),
                            )
                        )
                    )
                    await asyncio.sleep(0.05)
                await socket.send(json.dumps(dict(type="input_audio_buffer.commit")))
                await socket.send(json.dumps(dict(type="response.create")))
                async for raw in socket:
                    event = json.loads(raw)
                    kind = event["type"]
                    if kind == "error":
                        raise ProviderError(
                            "The live Realtime probe returned an audio-session error."
                        )
                    if kind == "response.output_audio.delta":
                        chunks.append(base64.b64decode(event["delta"]))
                    if kind == "response.output_audio_transcript.done":
                        transcript = event.get("transcript", "")
                    if kind == "conversation.item.input_audio_transcription.completed":
                        input_transcript = event.get("transcript", "")
                    if kind == "response.done":
                        if event.get("response", {}).get("status") != "completed":
                            raise ProviderError(
                                "Realtime audio did not complete successfully."
                            )
                        break
        output = b"".join(chunks)
        if not output or not transcript:
            raise ProviderError(
                "No returned audio/transcript was observed; the probe is incomplete."
            )
        target = Path("data/part-4-3-audio-response.wav")
        target.parent.mkdir(exist_ok=True)
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(output)
        return dict(
            evidence="live-provider WebSocket audio exchange; not browser-microphone evidence",
            inputOrigin=description,
            model=actual_model,
            requestedModel=provider.audio_model,
            inputSeconds=len(pcm) / 48000,
            outputSeconds=len(output) / 48000,
            outputSha256=hashlib.sha256(output).hexdigest(),
            inputTranscript=input_transcript,
            outputTranscript=transcript,
            elapsedSeconds=round(time.monotonic() - started, 2),
        )
    finally:
        await provider.close()


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
                state["context"], args.audio_input, args.audio_description
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

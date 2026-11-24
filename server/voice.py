"""Same-origin PCM streaming bridge to Gemini Live; no credentials in the browser."""

import asyncio
import base64
import json

from fastapi import WebSocketDisconnect
from .ai_provider import ProviderError


async def voice_session(websocket, assistant, provider, symbol, lock, demo_controls):
    await websocket.accept()
    if lock.locked():
        await websocket.send_json(
            dict(
                type="error",
                detail="A voice session is already active. End it before reconnecting.",
            )
        )
        await websocket.close(code=1013)
        return
    session_id = None
    counts = dict(
        inputBytes=0,
        outputBytes=0,
        completedTurns=0,
        inputTranscriptObserved=False,
        outputTranscriptObserved=False,
    )
    end_status, end_detail = "ended", "Voice transport ended; raw audio was not stored"
    tasks = []

    async def safe_message(value):
        try:
            await websocket.send_json(value)
        except (WebSocketDisconnect, RuntimeError):
            pass

    try:
        async with lock:
            async with asyncio.timeout(120):
                context = assistant.context(symbol)
                async with provider.voice(context) as upstream:
                    activity = assistant.record(
                        symbol,
                        "audio",
                        "negotiated",
                        context,
                        dict(
                            provider="Google Gemini",
                            requestedModel=provider.audio_model,
                            reason="Gemini Live acknowledged setup; audio transport and spoken exchange are verified separately",
                            evidence="live-provider-setup",
                        ),
                    )
                    session_id = activity["id"]
                    await websocket.send_json(
                        dict(
                            type="ready",
                            sessionId=session_id,
                            inputRate=16000,
                            outputRate=24000,
                            capturedAt=context["capturedAt"],
                            model=provider.audio_model,
                        )
                    )
                    await upstream.send(
                        json.dumps(
                            dict(
                                clientContent=dict(
                                    turns=[
                                        dict(
                                            role="user",
                                            parts=[
                                                dict(
                                                    text="Greet me in one brief sentence with the snapshot symbol. All trading is simulated."
                                                )
                                            ],
                                        )
                                    ],
                                    turnComplete=True,
                                )
                            )
                        )
                    )

                    async def from_browser():
                        while True:
                            message = await websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                return
                            pcm = message.get("bytes")
                            if pcm is not None:
                                if not 0 < len(pcm) <= 32000 or len(pcm) % 2:
                                    raise ProviderError(
                                        "Invalid audio frame. Reconnect with a supported browser."
                                    )
                                counts["inputBytes"] += len(pcm)
                                await upstream.send(
                                    json.dumps(
                                        dict(
                                            realtimeInput=dict(
                                                audio=dict(
                                                    mimeType="audio/pcm;rate=16000",
                                                    data=base64.b64encode(pcm).decode(),
                                                )
                                            )
                                        )
                                    )
                                )
                            else:
                                raw = message.get("text", "")
                                if len(raw) > 1024:
                                    raise ProviderError("Invalid voice control message")
                                try:
                                    command = json.loads(raw)
                                except ValueError:
                                    raise ProviderError(
                                        "Invalid voice control message"
                                    ) from None
                                if command == {"type": "end"}:
                                    return
                                if (
                                    command == {"type": "inject_failure"}
                                    and demo_controls
                                ):
                                    raise ProviderError(
                                        "Injected audio interruption; reconnect to recover.",
                                        code="INJECTED_FAILURE",
                                    )
                                raise ProviderError("Unsupported voice control message")

                    async def from_provider():
                        input_text, output_text = "", ""
                        async for raw in upstream:
                            event = json.loads(raw)
                            if "error" in event or "goAway" in event:
                                raise ProviderError(
                                    "Gemini Live ended the audio session. Reconnect after checking free-tier quota."
                                )
                            content = event.get("serverContent", {})
                            for part in content.get("modelTurn", {}).get("parts", []):
                                audio = part.get("inlineData")
                                if audio:
                                    if not audio.get("mimeType", "").startswith(
                                        "audio/pcm"
                                    ):
                                        raise ProviderError(
                                            "Unsupported live audio format"
                                        )
                                    pcm = base64.b64decode(audio["data"], validate=True)
                                    if len(pcm) > 256000 or len(pcm) % 2:
                                        raise ProviderError("Invalid live audio output")
                                    counts["outputBytes"] += len(pcm)
                                    await websocket.send_bytes(pcm)
                            incoming = content.get("inputTranscription", {}).get(
                                "text", ""
                            )
                            outgoing = content.get("outputTranscription", {}).get(
                                "text", ""
                            )
                            input_text += incoming
                            output_text += outgoing
                            counts["inputTranscriptObserved"] |= bool(incoming.strip())
                            counts["outputTranscriptObserved"] |= bool(outgoing.strip())
                            if content.get("interrupted"):
                                await websocket.send_json(dict(type="interrupted"))
                            if content.get("turnComplete"):
                                for role, text in (
                                    ("user", input_text),
                                    ("assistant", output_text),
                                ):
                                    if text.strip():
                                        await websocket.send_json(
                                            dict(
                                                type="transcript", role=role, text=text
                                            )
                                        )
                                input_text, output_text = "", ""
                                counts["completedTurns"] += 1
                                await websocket.send_json(dict(type="turn_complete"))

                    tasks = [
                        asyncio.create_task(from_browser()),
                        asyncio.create_task(from_provider()),
                    ]
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
    except WebSocketDisconnect:
        pass
    except TimeoutError:
        end_detail = "Two-minute voice limit reached; reconnect for fresh context"
        await safe_message(dict(type="ended", detail=end_detail))
    except ProviderError as exc:
        end_status = "injected_failure" if exc.code == "INJECTED_FAILURE" else "failure"
        end_detail = str(exc)
        await safe_message(dict(type="error", detail=end_detail))
    except (ValueError, TypeError, KeyError, RuntimeError):
        end_status, end_detail = (
            "failure",
            "Voice protocol failed. Microphone transport closed; reconnect to recover.",
        )
        await safe_message(dict(type="error", detail=end_detail))
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        assistant.record(
            symbol,
            "audio",
            end_status,
            dict(sessionId=session_id),
            dict(
                provider="Google Gemini",
                reason=end_detail,
                evidence="injected-voice-failure"
                if end_status == "injected_failure"
                else "server-observed-voice-transport",
                **counts,
            ),
        )
        try:
            await websocket.close()
        except RuntimeError:
            pass

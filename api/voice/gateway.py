"""The single WebSocket the browser talks to.

Inbound: hello, text, audio, barge_in, approve, language, reset.
Outbound: ready, state, level, partial, transcript, agent, audio, confirm,
demand, phase, negotiation, vendor, offers, admin, approval, notice, error.

No session starts until ``hello`` arrives, so the greeting always uses the
language the client actually asked for.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .pcm import b64decode_pcm
from .session import VoiceSession

log = logging.getLogger("negoai.gateway")

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket) -> None:
    await websocket.accept()

    # One writer at a time: several turns can emit concurrently.
    send_lock = asyncio.Lock()

    async def send(payload: dict[str, Any]) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    session: Optional[VoiceSession] = None

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if message.get("bytes"):
                if session is not None:
                    await session.handle_audio(message["bytes"])
                continue

            raw = message.get("text")
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            kind = payload.get("type")

            if kind == "hello":
                mode = payload.get("mode", "live")
                language = payload.get("language", "kn-IN")
                if session is not None:
                    await session.close()
                session = VoiceSession(send, mode=mode, language=language)
                await session.start()
                continue

            if kind == "ping":
                await send({"type": "pong"})
                continue

            if session is None:
                await send({"type": "error", "message": "Send hello before other messages."})
                continue

            if kind == "text":
                session._spawn(session.handle_text(payload.get("text", "")))
            elif kind == "audio":
                data = b64decode_pcm(payload.get("pcm", ""))
                if data:
                    session._spawn(session.handle_audio(data))
            elif kind == "playback_done":
                utterance_id = payload.get("utterance_id")
                epoch = payload.get("epoch")
                if isinstance(utterance_id, int) and isinstance(epoch, int):
                    await session.playback_done(utterance_id, epoch)
            elif kind == "barge_in":
                session._spawn(session.barge_in())
            elif kind == "control":
                action = payload.get("action")
                if action == "pause":
                    await session.pause()
                elif action == "resume":
                    await session.resume()
                elif action == "stop":
                    await session.stop()
                elif action == "skip":
                    await session.skip()
            elif kind == "approve":
                session._spawn(
                    session.approve(payload.get("decision", "approved"), payload.get("note", ""))
                )
            elif kind == "language":
                await session.set_language(payload.get("language", "en-IN"))
                await send({"type": "ready", **session.ready_payload()})
            elif kind == "reset":
                await session.configure(
                    mode=payload.get("mode", session.mode),
                    language=payload.get("language", session.language),
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - transport level
        log.warning("voice socket error: %s", exc)
    finally:
        if session is not None:
            await session.close()

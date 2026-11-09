"""The WebSocket contract, through FastAPI's real TestClient socket."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from api.main import app


def test_guided_demo_over_the_socket_reaches_admin():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice") as socket:
            socket.send_json({"type": "hello", "mode": "guided", "language": "en-IN"})
            kinds = set()
            admin = None
            for _ in range(800):
                message = socket.receive_json()
                kinds.add(message["type"])
                if message["type"] == "agent":
                    socket.send_json({
                        "type": "playback_done",
                        "utterance_id": message["utterance_id"],
                        "epoch": message["epoch"],
                    })
                elif message["type"] == "audio":
                    socket.send_json({
                        "type": "playback_done",
                        "utterance_id": message["utterance_id"],
                        "epoch": message["epoch"],
                    })
                if message["type"] == "admin":
                    admin = message
                    break
            assert "ready" in kinds
            assert "vendor" in kinds
            assert "offers" in kinds
            assert admin is not None
            assert admin["total_qty"] == 360
            assert admin["savings"] == 1440


def test_typed_demand_gets_a_confirmation_card():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice") as socket:
            socket.send_json({"type": "hello", "mode": "live", "language": "en-IN"})
            socket.send_json({"type": "text", "text": "Three water cans every week"})
            confirmed = False
            for _ in range(120):
                message = socket.receive_json()
                if message["type"] == "agent":
                    socket.send_json({
                        "type": "playback_done",
                        "utterance_id": message["utterance_id"],
                        "epoch": message["epoch"],
                    })
                if message["type"] == "confirm":
                    confirmed = True
                    assert "three" in message["text"].lower()
                    break
            assert confirmed


def test_language_switch_returns_a_ready_event():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice") as socket:
            socket.send_json({"type": "hello", "mode": "live", "language": "en-IN"})
            socket.send_json({"type": "language", "language": "kn-IN"})
            switched = False
            for _ in range(120):
                message = socket.receive_json()
                if message["type"] == "agent":
                    socket.send_json({
                        "type": "playback_done",
                        "utterance_id": message["utterance_id"],
                        "epoch": message["epoch"],
                    })
                if message["type"] == "ready" and message.get("language") == "kn-IN":
                    switched = True
                    break
            assert switched


def test_malformed_and_early_messages_are_safe():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice") as socket:
            socket.send_text("not json")
            socket.send_json({"type": "text", "text": "early"})
            error = socket.receive_json()
            assert error["type"] == "error"


def test_stop_during_typed_text_speech_takes_effect_within_200ms():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice") as socket:
            socket.send_json({"type": "hello", "mode": "live", "language": "en-IN"})
            greeting_finished = False
            while not greeting_finished:
                message = socket.receive_json()
                if message["type"] == "agent":
                    socket.send_json({
                        "type": "playback_done",
                        "utterance_id": message["utterance_id"],
                        "epoch": message["epoch"],
                    })
                if message.get("type") == "state" and message.get("orb") == "listening":
                    greeting_finished = True

            socket.send_json({"type": "text", "text": "Three water cans every week"})
            typed_speech_started = False
            while not typed_speech_started:
                message = socket.receive_json()
                typed_speech_started = message["type"] == "agent"

            started = time.monotonic()
            socket.send_json({"type": "control", "action": "stop"})
            stopped = False
            while not stopped:
                message = socket.receive_json()
                stopped = message.get("type") == "control" and message.get("action") == "stopped"
            assert time.monotonic() - started < 0.2

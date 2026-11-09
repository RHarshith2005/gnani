"""The WebSocket contract, through FastAPI's real TestClient socket."""

from __future__ import annotations

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

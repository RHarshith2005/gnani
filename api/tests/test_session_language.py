from __future__ import annotations

import asyncio

from api.config import Settings
from api.voice.session import VoiceSession, language_mismatch


def test_script_mismatch_detection():
    assert language_mismatch("मैं पड़ोसी हूँ", "kn-IN")
    assert language_mismatch("ನನಗೆ ನೀರು ಬೇಕು", "hi-IN")
    assert language_mismatch("ನನಗೆ ನೀರು ಬೇಕು", "en-IN")
    assert language_mismatch("मुझे पानी चाहिए", "en-IN")

    assert not language_mismatch("नमस्ते, मुझे पानी चाहिए", "hi-IN")
    assert not language_mismatch("ನನಗೆ ನೀರು ಬೇಕು", "kn-IN")
    # Code-mixing is normal: Latin words and digits are always allowed.
    assert not language_mismatch("Water can, three, weekly", "kn-IN")
    assert not language_mismatch("three water cans", "en-IN")


def test_background_talker_never_reaches_intake():
    events = []

    async def send(payload):
        events.append(payload)

    session = VoiceSession(send, language="kn-IN")
    asyncio.run(
        session._on_final_transcript("मैं पड़ोसी हूँ, मुझे भी हर हफ्ते पानी चाहिए।")
    )

    assert session.intake.product is None
    assert session.intake.qty is None
    assert session.language == "kn-IN"
    assert not any(e["type"] == "transcript" for e in events)
    notice = next(e for e in events if e["type"] == "notice")
    assert "another language" in notice["text"]
    assert "Kannada" in notice["text"]


def test_dead_stt_is_reconnected_on_next_audio(monkeypatch):
    events = []

    async def send(payload):
        events.append(payload)

    session = VoiceSession(
        send,
        language="kn-IN",
        config=Settings(gnani_api_key="test", gnani_key_id="test"),
    )

    class Dead:
        alive = False

        async def send_audio(self, data):
            raise AssertionError("dead stream must not receive audio")

    class Live:
        alive = True

        def __init__(self):
            self.chunks = []

        async def send_audio(self, data):
            self.chunks.append(data)

    session.stt = Dead()
    live = Live()

    async def restart():
        session.stt = live

    monkeypatch.setattr(session, "_restart_stt", restart)
    asyncio.run(session.handle_audio(b"\x00" * 1024))

    assert session.stt is live
    assert live.chunks == [b"\x00" * 1024]

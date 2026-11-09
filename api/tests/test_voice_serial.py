from __future__ import annotations

import asyncio
import time

from api.config import Settings
from api.voice.session import VoiceSession


class FakeTimbre:
    enabled = True

    def __init__(self, *, latency: float = 1.5, duration: float = 0.1) -> None:
        self.latency = latency
        self.duration = duration

    async def synthesize(self, text, language, *, voice=None):
        await asyncio.sleep(self.latency)
        return b"\x00\x00" * int(16000 * self.duration)

    def distinct_voice(self, language, preferred):
        return preferred

    async def aclose(self):
        return None


class FakePrisma:
    alive = True

    def __init__(self) -> None:
        self.frames = []

    async def send_audio(self, data):
        self.frames.append(data)

    async def close(self):
        return None


def make_session(events, *, latency=1.5, duration=0.1, auto_ack=True):
    session = None

    async def send(payload):
        events.append((time.monotonic(), dict(payload)))
        if not auto_ack or session is None:
            return
        if payload["type"] == "agent" and payload["tts"] == "browser":
            await session.playback_done(payload["utterance_id"], payload["epoch"])
        elif payload["type"] == "audio":
            async def ack():
                await asyncio.sleep(session.fake_duration)
                await session.playback_done(payload["utterance_id"], payload["epoch"])

            asyncio.create_task(ack())

    session = VoiceSession(
        send,
        mode="guided",
        config=Settings(
            gnani_api_key="test-key",
            gnani_key_id="test-key",
            demo_pace=0.01,
            credit_budget=10_000_000,
            session_tts_chars=10_000_000,
        ),
    )
    session.tts = FakeTimbre(latency=latency, duration=duration)
    session.fake_duration = duration
    return session


def test_speaks_are_serial_and_audio_ids_increase():
    async def scenario():
        events = []
        session = make_session(events)
        await asyncio.gather(session.speak("First line"), session.speak("Second line"))
        audio = [event for _, event in events if event["type"] == "audio"]
        ids = [event["utterance_id"] for event in audio]
        assert len(ids) == len(set(ids)) == 2
        assert ids == sorted(ids)
        states = [event["orb"] for _, event in events if event["type"] == "state"]
        assert max_running_speaks(states) == 1
        await session.close()

    asyncio.run(scenario())


def max_running_speaks(states):
    active = maximum = 0
    for state in states:
        if state == "speaking":
            active += 1
            maximum = max(maximum, active)
        elif state in ("idle", "listening"):
            active = 0
    return maximum


def test_orb_stays_speaking_until_real_clip_acknowledgement():
    async def scenario():
        events = []
        session = make_session(events, duration=0.12)
        await session.speak("A line with real audio")
        audio_time = next(t for t, event in events if event["type"] == "audio")
        listening_time = next(
            t for t, event in events if event["type"] == "state" and event["orb"] == "idle"
        )
        assert listening_time >= audio_time + 0.12 + 0.39
        await session.close()

    asyncio.run(scenario())


def test_half_duplex_drops_mic_finals_and_agent_echoes():
    async def scenario():
        events = []
        session = make_session(events, latency=0, duration=0)
        prisma = FakePrisma()
        session.stt = prisma
        session.agent_speaking = True
        await session.handle_audio(b"\x00" * 1024)
        await session._on_final_transcript("three water cans every week")
        assert prisma.frames == []
        assert session.intake.product is None

        session.agent_speaking = False
        session._recent_agent_lines.append(session._normalise_line("Three water cans, please."))
        await session._on_final_transcript("three water cans please")
        assert session.intake.product is None
        assert not any(event.get("role") == "resident" for _, event in events)
        await session.close()

    asyncio.run(scenario())


def test_negotiation_text_is_silent_and_notices_are_rate_limited():
    async def scenario():
        events = []
        session = make_session(events, latency=0, duration=0)
        session.phase = "negotiation"
        await session.handle_text("hello")
        await session.handle_text("hello again")
        notices = [event for _, event in events if event["type"] == "notice"]
        assert len(notices) == 1
        assert not any(event["type"] == "agent" for _, event in events)
        await session.close()

    asyncio.run(scenario())


def test_barge_in_cancels_pending_synthesis_without_late_audio():
    async def scenario():
        events = []
        session = make_session(events)
        session.phase = "intake"
        speech = asyncio.create_task(session.speak("Cancelled utterance"))
        while not any(event["type"] == "agent" for _, event in events):
            await asyncio.sleep(0.005)
        utterance_id = next(
            event["utterance_id"] for _, event in events if event["type"] == "agent"
        )
        await session.barge_in()
        await speech
        assert not any(
            event["type"] == "audio" and event["utterance_id"] == utterance_id
            for _, event in events
        )
        assert any(event["type"] == "interrupt" for _, event in events)
        await session.close()

    asyncio.run(scenario())


def test_missing_playback_ack_uses_bounded_timeout():
    async def scenario():
        events = []
        session = make_session(events, latency=0, duration=0.01, auto_ack=False)
        started = time.monotonic()
        await session.speak("No acknowledgement")
        elapsed = time.monotonic() - started
        assert elapsed >= 1.0
        assert elapsed < 1.6
        await session.close()

    asyncio.run(scenario())

"""Reproduce speech serialization, half-duplex gating and playback timing.

Run ``python scripts/overlap_repro.py A B C``. The fake Timbre service waits
1.5 seconds before returning PCM; scenario C's fake browser acknowledges
playback four seconds after receiving the clip.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import Settings
from api.voice.session import VoiceSession


class FakeTimbre:
    enabled = True

    def __init__(self, duration: float) -> None:
        self.duration = duration

    async def synthesize(self, text: str, language: str, *, voice: str | None = None) -> bytes:
        await asyncio.sleep(1.5)
        return b"\x00\x00" * int(16_000 * self.duration)

    def distinct_voice(self, language: str, preferred: str) -> str:
        return preferred

    async def aclose(self) -> None:
        return None


class FakePrisma:
    alive = True

    def __init__(self) -> None:
        self.frames: list[bytes] = []

    async def send_audio(self, data: bytes) -> None:
        self.frames.append(data)

    async def close(self) -> None:
        return None


async def run_scenario(name: str) -> None:
    events: list[tuple[float, dict]] = []
    session: VoiceSession

    async def send(payload: dict) -> None:
        sent_at = time.monotonic()
        events.append((sent_at, dict(payload)))
        if payload["type"] == "audio" and name == "C":
            async def acknowledge() -> None:
                await asyncio.sleep(4)
                await session.playback_done(payload["utterance_id"], payload["epoch"])

            asyncio.create_task(acknowledge())
        elif payload["type"] == "audio":
            async def acknowledge_short() -> None:
                await asyncio.sleep(len(session.fake_pcm) / (2 * 16_000))
                await session.playback_done(payload["utterance_id"], payload["epoch"])

            asyncio.create_task(acknowledge_short())
        elif payload["type"] == "agent" and payload["tts"] == "browser":
            await session.playback_done(payload["utterance_id"], payload["epoch"])

    duration = 4.0 if name == "C" else 0.05
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
    session.tts = FakeTimbre(duration)
    session.fake_pcm = b"\x00\x00" * int(16_000 * duration)

    if name == "A":
        await asyncio.gather(session.speak("First utterance"), session.speak("Second utterance"))
        utterances = [event for _, event in events if event["type"] == "audio"]
        ids = [event["utterance_id"] for event in utterances]
        assert len(ids) == len(set(ids)) == 2 and ids == sorted(ids)
        states = [event["orb"] for _, event in events if event["type"] == "state"]
        assert max_running_speaks(states) == 1
    elif name == "B":
        prisma = FakePrisma()
        session.stt = prisma
        session.agent_speaking = True
        await session.handle_audio(b"\x00" * 1024)
        await session._on_final_transcript("three water cans every week")
        session.agent_speaking = False
        session.phase = "negotiation"
        await session.handle_text("I heard the supplier")
        assert not prisma.frames
        assert not any(event.get("role") == "resident" for _, event in events)
        assert not any(event["type"] == "agent" for _, event in events)
    elif name == "C":
        started = time.monotonic()
        await session.speak("Four second playback clip")
        audio_at = next(t for t, event in events if event["type"] == "audio")
        idle_at = next(
            t for t, event in events if event["type"] == "state" and event["orb"] == "idle"
        )
        assert idle_at >= audio_at + 4.39
        assert time.monotonic() - started >= 5.89
    await session.close()


def max_running_speaks(states: list[str]) -> int:
    active = maximum = 0
    for state in states:
        if state == "speaking":
            active += 1
            maximum = max(maximum, active)
        elif state in ("idle", "listening"):
            active = 0
    return maximum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="+", choices=("A", "B", "C"))
    args = parser.parse_args()
    for scenario in args.scenarios:
        asyncio.run(run_scenario(scenario))
        print(f"Scenario {scenario}: PASS")


if __name__ == "__main__":
    main()

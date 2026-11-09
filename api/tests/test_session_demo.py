from __future__ import annotations

import asyncio
import json

from api.voice.session import VoiceSession


async def run_demo(language: str = "en-IN") -> list[dict]:
    events: list[dict] = []
    session = None

    async def send(payload: dict) -> None:
        events.append(json.loads(json.dumps(payload, default=str)))
        if session is not None and payload.get("type") == "agent":
            await session.playback_done(payload["utterance_id"], payload["epoch"])

    session = VoiceSession(send, mode="guided", language=language)
    await session.start()

    for _ in range(1500):
        if not session.tasks:
            break
        await asyncio.sleep(0.02)
    await session.close()
    return events


def test_guided_demo_runs_end_to_end():
    events = asyncio.run(run_demo("en-IN"))
    kinds = [event["type"] for event in events]

    for expected in ("ready", "agent", "transcript", "confirm", "negotiation", "vendor", "offers", "admin"):
        assert expected in kinds, f"missing {expected}"

    vendors = {event["vendor_id"] for event in events if event["type"] == "vendor"}
    assert len(vendors) == 3

    offers_events = [event for event in events if event["type"] == "offers"]
    assert offers_events, "no offer snapshots emitted"
    final_offers = offers_events[-1]["offers"]
    assert all(offer["eligible"] for offer in final_offers)
    assert all(offer["effective"] > 0 for offer in final_offers)

    admin = [event for event in events if event["type"] == "admin"][-1]
    assert admin["total_qty"] == 360
    assert admin["savings"] == 1440
    assert "Bengaluru Aqua" in admin["best"]["vendor_name"]
    assert admin["risks"]
    assert admin["summary_kn"]
    assert "LLM" in admin["summary_en"]


def test_public_negotiation_state_hides_committee_ceiling():
    events = asyncio.run(run_demo("en-IN"))
    negotiation_events = [event for event in events if event["type"] == "negotiation"]
    assert negotiation_events
    for event in negotiation_events:
        assert "target" not in event
        assert "max" not in event
        assert "target_price" not in event
        assert "max_price" not in event


def test_kannada_demo_speaks_kannada_numbers():
    events = asyncio.run(run_demo("kn-IN"))
    agent_lines = [event["text"] for event in events if event["type"] == "agent"]
    assert any("ರೂಪಾಯಿ" in line for line in agent_lines)
    assert any("ಕ್ಯಾನ್" in line for line in agent_lines)

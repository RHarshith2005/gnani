"""LLM adapter: JSON extraction and the no-key fallback."""

from __future__ import annotations

import asyncio

from api.agents.llm import LLMClient, _parse_json
from api.config import Settings


def test_parses_plain_fenced_and_embedded_json():
    assert _parse_json('{"say": "hi"}') == {"say": "hi"}
    assert _parse_json('```json\n{"say": "hi"}\n```') == {"say": "hi"}
    assert _parse_json('Sure: {"say": "hi"} done') == {"say": "hi"}
    assert _parse_json("no json here") is None
    assert _parse_json("") is None


def test_disabled_client_never_calls_the_network():
    client = LLMClient(Settings(llm_api_key=""))
    assert client.enabled is False
    assert asyncio.run(client.complete_json("system", "user")) is None

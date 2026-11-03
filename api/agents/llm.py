"""Optional LLM adapter (OpenAI-compatible, JSON mode).

Without ``LLM_API_KEY`` the orchestrator falls back to the deterministic
composer. Either way the engine owns every number; this module only turns a
directive into a sentence.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx

from ..config import Settings, settings as default_settings

log = logging.getLogger("negoai.llm")

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


class LLMClient:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or default_settings
        self.enabled = self.config.has_llm
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.llm_timeout)
        return self._client

    async def complete_json(self, system: str, user: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None
        payload = {
            "model": self.config.llm_model,
            "temperature": self.config.llm_temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = await self._get_client().post(
                f"{self.config.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _parse_json(content)
            if parsed is None:
                log.warning("LLM returned non-JSON content")
            return parsed
        except Exception as exc:  # network, auth, schema — fall back to composer
            log.warning("LLM call failed: %s", exc)
            return None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

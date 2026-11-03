"""Guard rails around the LLM.

The model may phrase a turn but it may not invent a number. Any price it claims
to have heard must appear in the transcript, and any price it proposes must sit
inside the range the engine allows for that turn.
"""

from __future__ import annotations

import re
from typing import Any, Optional

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[float]:
    if not text:
        return set()
    found: set[float] = set()
    for match in NUMBER_RE.findall(text):
        try:
            found.add(float(match))
        except ValueError:
            continue
    # Spelled-out prices ("nineteen rupees", "twenty one") are the norm in a
    # voice transcript, so parse consecutive number words as well as singles.
    from ..speech.numbers import parse_number

    whole = parse_number(text)
    if whole is not None:
        found.add(float(whole))

    words = re.findall(r"[A-Za-z]+|[\u0900-\u097F]+|[\u0C80-\u0CFF]+", text)
    for word in words:
        parsed = parse_number(word)
        if parsed is not None:
            found.add(float(parsed))
    return found


def _coerce(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number > 1_000_000:
        return None
    return number


def sanitize_offer(
    extracted: dict[str, Any] | None,
    *,
    transcript: str,
    floor_hint: float = 1.0,
    ceiling_hint: Optional[float] = None,
) -> tuple[Optional[dict[str, float]], list[str]]:
    """Return (clean offer, issues). ``None`` means "ignore this extraction"."""
    issues: list[str] = []
    if not extracted:
        return None, ["no offer extracted"]

    seen = numbers_in(transcript)
    clean: dict[str, float] = {}

    unit_price = _coerce(extracted.get("unit_price"))
    if unit_price is None:
        return None, ["missing unit_price"]
    if unit_price < floor_hint:
        return None, [f"unit_price {unit_price} below plausible floor"]
    if ceiling_hint is not None and unit_price > ceiling_hint:
        issues.append(f"unit_price {unit_price} above allowed ceiling")
        return None, issues
    if seen and not any(abs(unit_price - value) < 0.51 for value in seen):
        return None, [f"unit_price {unit_price} not supported by transcript"]

    clean["unit_price"] = unit_price
    for key in ("delivery_charge", "min_qty", "valid_days"):
        value = _coerce(extracted.get(key))
        if value is not None:
            clean[key] = value
    return clean, issues


def validate_turn_payload(payload: dict[str, Any] | None, *, allowed_actions: set[str]) -> dict[str, Any]:
    """Ensure the LLM returned the JSON shape the orchestrator expects."""
    if not isinstance(payload, dict):
        return {}
    say = payload.get("say")
    if not isinstance(say, str) or not say.strip():
        return {}
    intent = str(payload.get("intent") or "").strip()
    if intent and intent not in allowed_actions:
        return {}
    cleaned = {"say": say.strip()[:400], "intent": intent}
    language = payload.get("language")
    if isinstance(language, str) and language:
        cleaned["language"] = language
    offer = payload.get("offer_extracted")
    if isinstance(offer, dict):
        cleaned["offer_extracted"] = offer
    return cleaned

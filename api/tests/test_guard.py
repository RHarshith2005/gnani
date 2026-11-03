from __future__ import annotations

from api.agents.guard import numbers_in, sanitize_offer, validate_turn_payload


def test_numbers_in_transcript_digits_and_words():
    found = numbers_in("I can do 21 rupees, or nineteen rupees if you take two hundred")
    assert 21.0 in found
    assert 19.0 in found


def test_accepts_price_that_was_actually_said():
    clean, issues = sanitize_offer(
        {"unit_price": 21, "delivery_charge": 0},
        transcript="Twenty one rupees per can.",
        ceiling_hint=22,
    )
    assert clean is not None
    assert clean["unit_price"] == 21
    assert issues == []


def test_rejects_invented_price():
    clean, issues = sanitize_offer(
        {"unit_price": 12},
        transcript="I said twenty one rupees.",
        ceiling_hint=22,
    )
    assert clean is None
    assert "not supported by transcript" in issues[0]


def test_rejects_price_above_ceiling():
    clean, issues = sanitize_offer(
        {"unit_price": 24},
        transcript="Twenty four rupees.",
        ceiling_hint=22,
    )
    assert clean is None
    assert clean is None and issues


def test_missing_offer_is_rejected():
    clean, issues = sanitize_offer(None, transcript="hello")
    assert clean is None
    assert issues


def test_turn_payload_requires_say_and_known_intent():
    assert validate_turn_payload(None, allowed_actions={"counter"}) == {}
    assert validate_turn_payload({"say": ""}, allowed_actions={"counter"}) == {}
    assert (
        validate_turn_payload(
            {"say": "We can do nineteen rupees.", "intent": "counter"},
            allowed_actions={"counter"},
        )["intent"]
        == "counter"
    )
    assert (
        validate_turn_payload(
            {"say": "Something", "intent": "accept_everything"},
            allowed_actions={"counter"},
        )
        == {}
    )

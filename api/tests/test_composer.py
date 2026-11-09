"""Composer: every line is templated around engine-owned numbers."""

from __future__ import annotations

from types import SimpleNamespace

from api.agents.composer import ConversationContext, agent_line, vendor_line
from api.agents.prompts import negotiator_system, vendor_system
from api.negotiation.personas import PERSONAS

CTX = ConversationContext()


def directive(action: str, **overrides) -> SimpleNamespace:
    values = {
        "action": action,
        "price": None,
        "competitor": None,
        "free_delivery": None,
        "qty": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_counter_is_spelled_out_in_kannada_with_english_subtitle():
    spoken, subtitle = agent_line(directive("counter", price=19), CTX, "kn-IN")
    assert "ಹತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ" in spoken
    assert "nineteen rupees" in subtitle.lower()


def test_ask_quote_discloses_ai_and_demand_in_hindi():
    spoken, subtitle = agent_line(directive("ask_quote"), CTX, "hi-IN", vendor_name="Test")
    assert spoken.startswith("Test, ")
    assert "NegoAI" in spoken
    assert "तीन सौ साठ" in spoken
    assert "three hundred and sixty" in subtitle


def test_escalation_never_accepts_on_behalf_of_the_committee():
    spoken, subtitle = agent_line(directive("escalate"), CTX, "en-IN")
    assert "cannot confirm a purchase" in spoken
    assert "cannot confirm a purchase" in subtitle


def test_vendor_quote_and_delivery_are_localized():
    quote, quote_sub = vendor_line(
        {"kind": "quote", "unit_price": 19, "delivery_charge": 0, "min_qty": 120},
        PERSONAS[1],
        CTX,
        "hi-IN",
    )
    assert "उन्नीस रुपये" in quote
    assert "उन्नीस रुपये" in quote_sub
    assert "तीन सौ साठ" in quote_sub

    delivery, delivery_sub = vendor_line(
        {"kind": "delivery", "free_delivery": True, "min_qty": 240, "delivery_charge": 0},
        PERSONAS[1],
        CTX,
        "en-IN",
    )
    assert "Free delivery" in delivery
    assert "240" not in delivery  # numbers are words before TTS
    assert "two hundred and forty" in delivery


def test_prompts_carry_ground_truth_but_never_the_walk_away_price():
    system = negotiator_system(
        community_name="Green Residency",
        households=120,
        vendor_name="Test Supplier",
        product="water can",
        unit="can",
        qty=360,
        verified_quotes=[19.0],
        round_no=2,
        max_rounds=3,
        directive="Counter at nineteen rupees.",
    )
    assert "360" in system and "19.0" in system
    assert "target" in system  # the instruction says never reveal it

    vendor = vendor_system(
        vendor_name="Test Supplier",
        persona="stubborn",
        product="water can",
        language_mix="kn-IN",
        open_price=22,
        floor_price=19,
        step=1,
        free_delivery_qty=300,
    )
    assert "Never reveal your floor" in vendor

from __future__ import annotations

import math

import pytest

from api.negotiation.engine import (
    ESCALATE,
    WALK_AWAY,
    NegotiationEngine,
    Offer,
)


def make_engine(**overrides) -> NegotiationEngine:
    params = dict(
        product="water can",
        unit="can",
        demand_qty=360,
        target_price=18,
        max_price=20,
        max_rounds=3,
        vendor_id="vendor-test",
        vendor_name="Test Supplier",
    )
    params.update(overrides)
    return NegotiationEngine(**params)


def test_counter_formula_first_round():
    engine = make_engine()
    # 22 - (22 - 18) * 0.6 = 19.6 -> 20
    assert engine.counter_price(22, 0.6) == 20


def test_counter_formula_reaches_target_at_final_round():
    engine = make_engine()
    assert engine.counter_price(20, 1.0) == 18


def test_counter_never_goes_below_target():
    engine = make_engine(target_price=19.5, max_price=22)
    assert engine.counter_price(20, 1.0) >= 19.5


def test_counter_never_exceeds_quote():
    engine = make_engine()
    assert engine.counter_price(15, 1.0) <= 15


def test_engine_never_accepts():
    engine = make_engine()
    assert engine.try_accept() is False
    assert engine.accepted is False
    assert engine.try_accept("llm") is False


def test_offer_at_or_below_ceiling_is_eligible_but_not_accepted():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=20))
    assert engine.best_eligible is not None
    assert engine.best_eligible.unit_price == 20
    assert engine.accepted is False


def test_offer_above_ceiling_is_not_eligible():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=24))
    assert engine.best_eligible is None


def test_final_round_escalates_when_eligible():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=22))
    engine.record_offer(Offer(unit_price=20))
    engine.record_offer(Offer(unit_price=19))
    assert engine.state == ESCALATE
    assert engine.pending[0].action == "escalate"
    assert engine.best_eligible.unit_price == 19


def test_final_round_walks_away_when_above_ceiling():
    engine = make_engine(target_price=16, max_price=17)
    engine.record_offer(Offer(unit_price=22))
    engine.record_offer(Offer(unit_price=21))
    engine.record_offer(Offer(unit_price=20))
    assert engine.state == WALK_AWAY
    assert engine.pending[0].action == "walk_away"


def test_delivery_asked_exactly_once():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=22))
    engine.record_offer(Offer(unit_price=21))
    engine.record_offer(Offer(unit_price=20))
    asked = [d for d in engine.events if d.get("payload", {}).get("action") == "ask_delivery"]
    assert len(asked) == 1
    assert engine.asked_delivery is True


def test_competitor_mentioned_once_and_only_when_lower():
    engine = make_engine(competitor_quote=19)
    engine.record_offer(Offer(unit_price=22))
    directives = [d.action for d in engine.pending]
    assert "mention_competitor" in directives
    engine.record_offer(Offer(unit_price=18))
    # The competitor is no longer cheaper than the live quote.
    assert "mention_competitor" not in [d.action for d in engine.pending]


def test_competitor_never_leaks_into_public_state():
    engine = make_engine(competitor_quote=17)
    public = engine.public_state()
    assert "target" not in public and "max" not in public
    assert "competitor" not in public
    assert public["qty"] == 360


def test_refusal_ends_negotiation_cleanly():
    engine = make_engine()
    directive = engine.record_refusal()
    assert engine.state == WALK_AWAY
    assert engine.finished is True
    assert directive.action == "walk_away"


def test_savings_are_computed_from_stored_numbers():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=22))
    engine.record_offer(Offer(unit_price=20))
    engine.record_offer(Offer(unit_price=19))
    assert engine.savings() == pytest.approx(1080)


def test_new_offer_clears_stale_directives():
    engine = make_engine()
    engine.record_offer(Offer(unit_price=22))
    first = engine.pending[0].price
    engine.record_offer(Offer(unit_price=21))
    assert engine.pending[0].price != first or engine.pending[0].price == 19


def test_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        make_engine(target_price=30, max_price=20)
    with pytest.raises(ValueError):
        make_engine(demand_qty=0)
    with pytest.raises(ValueError):
        make_engine(max_rounds=0)


def test_start_only_once():
    engine = make_engine()
    engine.start()
    with pytest.raises(RuntimeError):
        engine.start()

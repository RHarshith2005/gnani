"""Persistence layer: seed safety, aggregation, offers and audit ordering."""

from __future__ import annotations

from api import db


def test_seed_is_idempotent():
    conn = db.init_db()
    db.seed(conn)
    first = db.aggregate_demand()["total_qty"]
    db.seed(conn)
    assert db.aggregate_demand()["total_qty"] == first
    assert first >= 360


def test_confirmed_demand_increases_the_aggregate():
    before = db.aggregate_demand()["total_qty"]
    db.save_demand(
        resident_id=None,
        community_id=db.COMMUNITY_ID,
        product="water can",
        qty=4,
        frequency="weekly",
        delivery_day="Saturday",
        language="kn-IN",
    )
    assert db.aggregate_demand()["total_qty"] == before + 4


def test_events_are_ordered_and_payloads_roundtrip():
    negotiation_id = db.create_negotiation(product="water can", qty=360, language="kn-IN")
    db.add_event(negotiation_id, actor="engine", type="ask_quote", payload={"price": None})
    db.add_event(negotiation_id, actor="negoai", type="counter", payload={"price": 18})

    events = db.get_events(negotiation_id)
    assert [event["type"] for event in events] == ["ask_quote", "counter"]
    assert events[0]["payload"] == {"price": None}
    assert events[1]["payload"]["price"] == 18


def test_offers_and_negotiation_lookup():
    negotiation_id = db.create_negotiation(product="water can", qty=360, language="en-IN")
    db.save_offer(
        negotiation_id,
        vendor_id="vendor-friendly",
        product="water can",
        unit_price=19,
        delivery_charge=0,
        min_qty=120,
        valid_days=5,
        round_no=2,
        eligible=True,
    )
    offers = db.list_offers(negotiation_id)
    assert len(offers) == 1
    assert offers[0]["eligible"] is True
    assert offers[0]["unit_price"] == 19

    negotiation = db.get_negotiation(negotiation_id)
    assert negotiation["community"] == "Green Residency"
    assert negotiation["qty"] == 360
    assert db.get_negotiation("missing-negotiation") is None


def test_sessions_list_names_the_community():
    with TestClientSession() as present:
        assert present


class TestClientSession:
    """Tiny context shim so this test does not need the web stack."""

    def __enter__(self) -> bool:
        negotiation_id = db.create_negotiation(product="water can", qty=360, language="kn-IN")
        sessions = db.list_sessions(limit=50)
        match = [row for row in sessions if row["id"] == negotiation_id]
        assert match and match[0]["community"] == "Green Residency"
        return True

    def __exit__(self, *exc) -> None:
        return None

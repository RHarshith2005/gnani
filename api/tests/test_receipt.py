"""Tamper-evident receipt: deterministic chain, tamper detection, totals."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import db
from api.main import app
from api.receipt import GENESIS, build_receipt

EVENTS = [
    {"ts": "2026-11-09T10:00:00Z", "actor": "negoai", "type": "ask_quote", "payload": {}},
    {"ts": "2026-11-09T10:00:02Z", "actor": "vendor", "type": "offer", "payload": {"unit_price": 22}},
    {"ts": "2026-11-09T10:00:05Z", "actor": "negoai", "type": "counter", "payload": {"price": 19}},
    {"ts": "2026-11-09T10:00:09Z", "actor": "vendor", "type": "offer", "payload": {"unit_price": 19}},
    {"ts": "2026-11-09T10:00:12Z", "actor": "admin", "type": "approval", "payload": {"decision": "approved"}},
]

OFFERS = [
    {"vendor_id": "vendor-friendly", "unit_price": 22, "delivery_charge": 0, "eligible": False},
    {"vendor_id": "vendor-friendly", "unit_price": 19, "delivery_charge": 0, "eligible": True},
]


def make_receipt(events=None):
    return build_receipt(
        negotiation_id="neg-test",
        community="Green Residency",
        product="water can",
        qty=360,
        events=events or EVENTS,
        offers=OFFERS,
        issued_at="2026-11-09T10:00:15Z",
    )


def test_chain_is_deterministic_and_complete():
    first = make_receipt()
    second = make_receipt()
    assert first["chain_head"] == second["chain_head"]
    assert len(first["chain_head"]) == 64
    assert first["genesis"] == GENESIS
    assert first["event_count"] == len(EVENTS)
    assert len(first["blocks"]) == len(EVENTS)
    assert first["blocks"][0]["digest"] != first["blocks"][1]["digest"]


def test_editing_one_row_changes_the_head():
    tampered = [dict(event) for event in EVENTS]
    tampered[1] = {**tampered[1], "payload": {"unit_price": 18}}
    assert make_receipt(tampered)["chain_head"] != make_receipt()["chain_head"]

    deleted = EVENTS[:-1]
    assert make_receipt(deleted)["chain_head"] != make_receipt()["chain_head"]


def test_totals_come_from_stored_offers_only():
    receipt = make_receipt()
    assert receipt["first_quote"] == 22
    assert receipt["best_offer"]["unit_price"] == 19
    assert receipt["savings"] == 1080
    assert receipt["approval"]["decision"] == "approved"


def test_receipt_endpoint_and_missing_session():
    negotiation_id = db.create_negotiation(product="water can", qty=360, language="en-IN")
    db.add_event(negotiation_id, actor="negoai", type="ask_quote", payload={"price": None})
    db.save_offer(
        negotiation_id,
        vendor_id="vendor-friendly",
        product="water can",
        unit_price=22,
        delivery_charge=0,
        min_qty=120,
        valid_days=5,
        round_no=1,
        eligible=False,
    )
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
    db.add_event(negotiation_id, actor="admin", type="approval", payload={"decision": "approved"})

    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{negotiation_id}/receipt")
        assert response.status_code == 200
        body = response.json()
        assert body["negotiation_id"] == negotiation_id
        assert body["event_count"] == 2
        assert body["savings"] == 1080
        assert body["product"] == "water can"

        missing = client.get("/api/sessions/does-not-exist/receipt")
        assert missing.status_code == 404

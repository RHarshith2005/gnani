"""Run NegoAI against all three simulated suppliers in text mode.

    python scripts/run_negotiation.py

Fast, no audio, no keys: the engine decides every number, the composer speaks
it, and every offer is written to vendor_offers and negotiation_events.
Exit code 0 means all personas finished within max_rounds and the audit trail
has at least one eligible offer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / "api" / ".env")
except Exception:
    pass

from api import db  # noqa: E402
from api.agents.composer import ConversationContext, agent_line, vendor_line  # noqa: E402
from api.negotiation.engine import (  # noqa: E402
    ASK_QUOTE,
    ESCALATE_ACTION,
    MENTION_COMPETITOR,
    WALK_AWAY_ACTION,
    NegotiationEngine,
)
from api.negotiation.personas import PERSONAS, SimVendor  # noqa: E402

COMMUNITY = {"id": db.COMMUNITY_ID, "name": "Green Residency", "households": 120}
QTY = 360
TARGET_PRICE = 18
MAX_PRICE = 20
MAX_ROUNDS = 3
LANG = os.environ.get("NEGOTIATION_LANG", "en-IN")


def line(actor: str, text: str, subtitle: str = "") -> None:
    print(f"{actor:>10}: {text}")
    if subtitle and subtitle != text:
        print(f"{'':>10}  ({subtitle})")


def run_persona(persona, negotiation_id: str, ctx: ConversationContext) -> dict:
    engine = NegotiationEngine(
        product="water can",
        unit="can",
        demand_qty=QTY,
        target_price=TARGET_PRICE,
        max_price=MAX_PRICE,
        max_rounds=MAX_ROUNDS,
        competitor_quote=None,
        vendor_id=persona.vendor_id,
        vendor_name=persona.name,
        community=COMMUNITY["name"],
        households=COMMUNITY["households"],
    )
    sim = SimVendor(persona, demand_qty=QTY)
    print(f"\n=== {persona.name} ({persona.personality}) ===")

    first_quote = None
    best_eligible = None
    offers = []

    def agent_turn(directive) -> None:
        spoken, subtitle = agent_line(
            directive, ctx, LANG, vendor_name=engine.vendor_name
        )
        line("NegoAI", spoken, subtitle)
        db.add_event(
            negotiation_id,
            actor="negoai",
            type=directive.action,
            payload={"text": spoken, "subtitle": subtitle, "price": directive.price},
        )

    def vendor_turn(agent_price=None) -> None:
        nonlocal first_quote, best_eligible
        offer = sim.quote(agent_price=agent_price)
        engine.record_offer(offer)
        offers.append(offer)
        if offer.unit_price <= MAX_PRICE + 1e-9:
            best_eligible = offer
        if first_quote is None:
            first_quote = offer.unit_price
        eligible = offer.unit_price <= MAX_PRICE + 1e-9
        db.save_offer(
            negotiation_id,
            vendor_id=engine.vendor_id,
            product=engine.product,
            unit_price=offer.unit_price,
            delivery_charge=offer.delivery_charge,
            min_qty=offer.min_qty,
            valid_days=offer.valid_days,
            round_no=offer.round,
            eligible=eligible,
        )
        spoken, subtitle = vendor_line(
            {
                "kind": "quote",
                "unit_price": offer.unit_price,
                "delivery_charge": offer.delivery_charge,
                "min_qty": offer.min_qty,
            },
            persona,
            ctx,
            LANG,
        )
        line("Vendor", spoken, subtitle)
        db.add_event(
            negotiation_id, actor="vendor", type="offer", payload=offer.to_dict()
        )

    def delivery_turn() -> None:
        terms = sim.delivery_terms()
        engine.record_delivery(
            free=terms["free_delivery"],
            charge=terms["delivery_charge"],
            min_qty=terms["min_qty"],
        )
        spoken, subtitle = vendor_line(
            {"kind": "delivery", **terms}, persona, ctx, LANG
        )
        line("Vendor", spoken, subtitle)
        db.add_event(
            negotiation_id, actor="vendor", type="delivery_terms", payload=terms
        )

    directive = engine.start()
    agent_turn(directive)
    vendor_turn()

    for _ in range(20):
        directive = engine.next_directive()
        if directive is None:
            break
        agent_turn(directive)
        if directive.action in (ESCALATE_ACTION, WALK_AWAY_ACTION):
            break
        if directive.action == MENTION_COMPETITOR:
            continue
        if directive.action == "ask_delivery":
            delivery_turn()
            continue
        vendor_turn(directive.price)

    db.update_negotiation(
        negotiation_id,
        state=engine.state,
        round_no=engine.round,
        first_quote=first_quote,
        best_quote=best_eligible.unit_price if best_eligible else None,
    )
    db.add_event(
        negotiation_id,
        actor="engine",
        type="result",
        payload={
            "vendor": persona.name,
            "state": engine.state,
            "rounds": engine.round,
            "prices": [offer.unit_price for offer in offers],
            "eligible": best_eligible.unit_price if best_eligible else None,
            "savings": engine.savings(),
        },
    )
    print(
        f"{'':>10}  prices {[offer.unit_price for offer in offers]} · "
        f"state {engine.state} · eligible "
        f"{best_eligible.unit_price if best_eligible else 'none'}"
    )
    return {
        "persona": persona.personality,
        "rounds": engine.round,
        "state": engine.state,
        "prices": [offer.unit_price for offer in offers],
        "eligible": best_eligible.unit_price if best_eligible else None,
        "accepted": engine.accepted,
    }


def main() -> int:
    db.init_db()
    db.seed(db.connect())
    ctx = ConversationContext(
        community=COMMUNITY["name"],
        households=COMMUNITY["households"],
        product="water can",
        unit="can",
        qty=QTY,
    )
    negotiation_id = db.create_negotiation(
        community_id=COMMUNITY["id"],
        product="water can",
        qty=QTY,
        language=LANG,
        state=ASK_QUOTE,
        max_rounds=MAX_ROUNDS,
    )
    print(f"NegoAI vs three simulated suppliers — {QTY} water cans/week, {LANG}")
    print(f"audit trail: negotiation_id={negotiation_id}")

    results = [run_persona(persona, negotiation_id, ctx) for persona in PERSONAS]

    print("\n=== summary ===")
    for result in results:
        print(
            f"{result['persona']:<26} rounds={result['rounds']} "
            f"state={result['state']:<18} eligible={result['eligible']} "
            f"accepted={result['accepted']} prices={result['prices']}"
        )

    finished = all(result["rounds"] <= MAX_ROUNDS for result in results)
    offered = any(result["eligible"] is not None for result in results)
    no_accepts = all(result["accepted"] is False for result in results)
    print(
        f"\nDone when all three personas finish in <= {MAX_ROUNDS} rounds, offers "
        f"are stored, and the agent never accepts: "
        f"{'PASS' if finished and offered and no_accepts else 'FAIL'}"
    )
    return 0 if finished and offered and no_accepts else 1


if __name__ == "__main__":
    raise SystemExit(main())

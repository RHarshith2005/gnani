"""Tamper-evident negotiation receipt.

The event log is append-only, so a receipt can be recomputed from it at any
time. Each event is hashed together with the previous digest, forming a chain:
copy the chain head when the deal is approved, and any later edit or deletion
of the stored rows produces a different head. Totals are derived from stored
offers only — the same numbers the committee saw, never an LLM's.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

GENESIS = "0" * 64
SCHEMA = "negoai.receipt/v1"
ALGORITHM = "sha256-chain/v1"


def canonical(value: Any) -> str:
    """Stable JSON encoding: same rows always hash to the same digest."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def build_receipt(
    *,
    negotiation_id: str,
    community: str,
    product: str,
    qty: int,
    events: list[dict[str, Any]],
    offers: list[dict[str, Any]],
    issued_at: str,
) -> dict[str, Any]:
    previous = GENESIS
    blocks: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        node = {
            "i": index,
            "ts": event.get("ts"),
            "actor": event.get("actor"),
            "type": event.get("type"),
            "payload": event.get("payload") or {},
            "prev": previous,
        }
        digest = hashlib.sha256(canonical(node).encode("utf-8")).hexdigest()
        blocks.append(
            {
                "index": index,
                "type": node["type"],
                "actor": node["actor"],
                "digest": digest,
            }
        )
        previous = digest

    first_by_vendor: dict[str, float] = {}
    eligible: list[dict[str, Any]] = []
    for offer in offers:
        vendor = str(offer.get("vendor_id") or "")
        price = float(offer.get("unit_price") or 0)
        if vendor and vendor not in first_by_vendor:
            first_by_vendor[vendor] = price
        if offer.get("eligible"):
            eligible.append(offer)

    opening = max(first_by_vendor.values()) if first_by_vendor else None
    best: Optional[dict[str, Any]] = None
    if eligible:
        best = min(
            eligible,
            key=lambda item: (
                float(item["unit_price"]) * qty + float(item.get("delivery_charge") or 0),
                float(item["unit_price"]),
            ),
        )
    savings = (
        round((opening - float(best["unit_price"])) * qty, 2)
        if opening is not None and best is not None
        else 0.0
    )

    approval = None
    for event in reversed(events):
        if event.get("type") == "approval":
            approval = event.get("payload") or {}
            break

    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "negotiation_id": negotiation_id,
        "community": community,
        "product": product,
        "qty": qty,
        "issued_at": issued_at,
        "event_count": len(events),
        "genesis": GENESIS,
        "chain_head": previous,
        "first_quote": opening,
        "best_offer": best,
        "savings": savings,
        "approval": approval,
        "blocks": blocks,
    }

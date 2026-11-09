"""Three simulated suppliers with hidden floors.

The synthetic-data rule means no real vendor is called. Each persona has its own
opening quote, floor, concession step and delivery policy; the blueprint asks
for stubborn, friendly-volume-hungry and cheap-but-slow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .engine import Offer


@dataclass(frozen=True)
class VendorPersona:
    vendor_id: str
    name: str
    personality: str
    description: str
    open_price: float
    floor_price: float
    step: float
    min_qty: int
    free_delivery_qty: int
    delivery_charge: float
    delivery_days: int
    valid_days: int
    voice: str = "Avinash"
    product: str = "water can"

    def to_dict(self) -> dict:
        # Floors are deliberately absent: the browser never sees them.
        return {
            "vendor_id": self.vendor_id,
            "name": self.name,
            "personality": self.personality,
            "description": self.description,
            "min_qty": self.min_qty,
            "delivery_days": self.delivery_days,
            "delivery_charge": self.delivery_charge,
            "free_delivery_qty": self.free_delivery_qty,
            "valid_days": self.valid_days,
            "voice": self.voice,
            "product": self.product,
        }


PERSONAS: tuple[VendorPersona, ...] = (
    VendorPersona(
        vendor_id="vendor-stubborn",
        name="Sri Lakshmi Water Agency",
        personality="stubborn",
        description="Family-run, moves a rupee a round, talks about diesel.",
        open_price=22,
        floor_price=19,
        step=1,
        min_qty=60,
        free_delivery_qty=300,
        delivery_charge=60,
        delivery_days=2,
        valid_days=7,
        voice="Avinash",
    ),
    VendorPersona(
        vendor_id="vendor-friendly",
        name="Bengaluru Aqua Distributors",
        personality="friendly volume-hungry",
        description="Wants the whole society, drops fast for bulk.",
        open_price=22,
        floor_price=18,
        step=2,
        min_qty=120,
        free_delivery_qty=240,
        delivery_charge=0,
        delivery_days=1,
        valid_days=5,
        voice="Devansh",
    ),
    VendorPersona(
        vendor_id="vendor-cheap-slow",
        name="Cauvery Can Supply",
        personality="cheap but slow",
        description="Lowest price, three-day delivery, will not budge much.",
        open_price=21,
        floor_price=17,
        step=1.5,
        min_qty=200,
        free_delivery_qty=500,
        delivery_charge=40,
        delivery_days=3,
        valid_days=10,
        voice="Prakash",
    ),
)


class SimVendor:
    """Deterministic haggling brain for a demo persona."""

    def __init__(self, persona: VendorPersona, *, demand_qty: int = 360) -> None:
        self.persona = persona
        self.demand_qty = demand_qty
        self.last_price: Optional[float] = None
        self.quotes: list[float] = []
        self.delivery_asked = False

    # ------------------------------------------------------------------ offers
    def quote(self, agent_price: Optional[float] = None) -> Offer:
        p = self.persona
        if self.last_price is None:
            price = p.open_price
        else:
            proposed = self.last_price - p.step
            if agent_price is not None:
                # Never jump straight past the buyer's number, but do concede.
                proposed = min(proposed, agent_price + p.step)
            price = max(p.floor_price, proposed)
            if agent_price is not None and agent_price >= p.floor_price:
                price = min(price, agent_price) if price > agent_price else price
        price = float(round(price))
        price = max(p.floor_price, price)
        self.last_price = price
        self.quotes.append(price)
        return Offer(
            unit_price=price,
            delivery_charge=p.delivery_charge,
            min_qty=p.min_qty,
            valid_days=p.valid_days,
            delivery_days=p.delivery_days,
            vendor_id=p.vendor_id,
            vendor_name=p.name,
            round=len(self.quotes),
            source="simulated",
        )

    def delivery_terms(self) -> dict:
        p = self.persona
        free_included = max(p.min_qty, p.free_delivery_qty)
        free = self.demand_qty >= free_included
        self.delivery_asked = True
        return {
            "free_delivery": free,
            "delivery_charge": 0.0 if free else p.delivery_charge,
            "min_qty": free_included,
            "delivery_days": p.delivery_days,
            "valid_days": p.valid_days,
        }

    def accepts(self, price: float) -> bool:
        return price >= self.persona.floor_price


PRIMARY_PERSONA = PERSONAS[1]

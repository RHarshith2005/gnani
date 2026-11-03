"""The negotiation engine.

Design rule from the blueprint: **the engine decides, the LLM speaks.**
Every number in the conversation is produced here and nowhere else. The engine
never accepts an offer — at most it marks an offer *eligible* and escalates to
the committee. That property is enforced by ``try_accept`` and covered by tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

ASK_QUOTE = "ASK_QUOTE"
FINAL = "FINAL"
ESCALATE = "ESCALATE_TO_ADMIN"
WALK_AWAY = "WALK_AWAY"

#: Concession schedule: counter_k = quote - (quote - target) * factor[k-1]
COUNTER_FACTORS: tuple[float, float, float] = (0.6, 0.8, 1.0)

DELIVERY_ACK = "ack_delivery"
COUNTER = "counter"
MENTION_COMPETITOR = "mention_competitor"
ASK_DELIVERY = "ask_delivery"
ESCALATE_ACTION = "escalate"
WALK_AWAY_ACTION = "walk_away"


@dataclass
class Offer:
    """A vendor quote, exactly as extracted from the transcript."""

    unit_price: float
    delivery_charge: float = 0.0
    min_qty: Optional[int] = None
    valid_days: Optional[int] = None
    delivery_days: Optional[int] = None
    vendor_id: str = ""
    vendor_name: str = ""
    round: int = 0
    source: str = "simulated"

    @property
    def effective_weekly_cost(self) -> float:
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "unit_price": _money(self.unit_price),
            "delivery_charge": _money(self.delivery_charge),
            "min_qty": self.min_qty,
            "valid_days": self.valid_days,
            "delivery_days": self.delivery_days,
            "round": self.round,
            "source": self.source,
        }


def _money(value: float) -> float | int:
    """Prices are whole rupees in practice; keep ints clean for the UI."""
    if value is None:
        return 0
    rounded = round(float(value), 2)
    return int(rounded) if rounded == int(rounded) else rounded


@dataclass
class Directive:
    """One turn instruction, produced by the engine and rendered by the agent."""

    action: str
    price: Optional[float] = None
    factor: Optional[float] = None
    qty: Optional[int] = None
    competitor: Optional[float] = None
    round: int = 0
    max_rounds: int = 3
    free_delivery: Optional[bool] = None
    delivery_charge: Optional[float] = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "price": _money(self.price) if self.price is not None else None,
            "qty": self.qty,
            "competitor": _money(self.competitor) if self.competitor is not None else None,
            "round": self.round,
            "max_rounds": self.max_rounds,
            "free_delivery": self.free_delivery,
            "note": self.note,
        }

    def as_instruction(self, *, product: str, unit: str, community: str, households: int) -> str:
        """English directive handed to the LLM (server-side only)."""
        head = (
            f"You are speaking to the supplier of {product} for {community}, "
            f"{households} households. Round {self.round} of {self.max_rounds}."
        )
        if self.action == ASK_QUOTE.lower() or self.action == "ask_quote":
            step = (
                f"Introduce yourself as an AI assistant, state the verified demand of "
                f"{self.qty or 0} {unit} per week, and ask for their best price per {unit}. "
                "Do not name any price."
            )
        elif self.action == COUNTER:
            step = (
                f"Counter at exactly {_money(self.price)} rupees per {unit}. "
                f"Mention the bulk demand of {self.qty or 0} {unit} a week. "
                "Do not offer any other number, discount or commitment."
            )
        elif self.action == ASK_DELIVERY:
            step = (
                "Ask once whether they will deliver free to the society gate, "
                f"now that the price has moved. Suggested price to keep: {_money(self.price)} rupees."
            )
        elif self.action == MENTION_COMPETITOR:
            step = (
                f"Say you have a verified competing quote of {_money(self.competitor)} rupees per {unit} "
                "and ask whether they can match it. This is real recorded data — use only this number."
            )
        elif self.action == ESCALATE_ACTION:
            step = (
                "Thank the supplier and say the offer will go to the community committee for "
                "approval. State that you cannot confirm a purchase."
            )
        elif self.action == WALK_AWAY_ACTION:
            step = (
                "Politely end the negotiation: the offer is above the community's ceiling. "
                "Do not name the ceiling."
            )
        elif self.action == DELIVERY_ACK:
            step = (
                "Acknowledge the delivery terms briefly, then counter at "
                f"{_money(self.price)} rupees if a counter remains."
            )
        else:
            step = "Continue the negotiation with one question at a time."
        return f"{head} {step} Never reveal target or ceiling prices."


class NegotiationEngine:
    """Deterministic, side-effect-free until the owner persists events."""

    def __init__(
        self,
        *,
        product: str,
        unit: str,
        demand_qty: int,
        target_price: float,
        max_price: float,
        max_rounds: int = 3,
        competitor_quote: Optional[float] = None,
        vendor_id: str = "",
        vendor_name: str = "",
        community: str = "Green Residency",
        households: int = 120,
    ) -> None:
        if demand_qty <= 0:
            raise ValueError("demand_qty must be positive")
        if target_price <= 0 or max_price <= 0:
            raise ValueError("prices must be positive")
        if target_price > max_price:
            raise ValueError("target_price cannot exceed max_price")
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")

        self.product = product
        self.unit = unit
        self.demand_qty = int(demand_qty)
        self.target_price = float(target_price)
        self.max_price = float(max_price)
        self.max_rounds = int(max_rounds)
        self.competitor_quote = competitor_quote
        self.vendor_id = vendor_id
        self.vendor_name = vendor_name
        self.community = community
        self.households = households

        self.round = 0
        self.state = ASK_QUOTE
        self.history: list[Offer] = []
        self.best_eligible: Optional[Offer] = None
        self.pending: list[Directive] = []
        self.events: list[dict[str, Any]] = []
        self.asked_delivery = False
        self.mentioned_competitor = False
        self.delivery_free: Optional[bool] = None
        self.delivery_charge: Optional[float] = None
        self.finished = False
        self.accepted = False
        self.started = False

    # ------------------------------------------------------------------ start
    def start(self) -> Directive:
        if self.started or self.round or self.history:
            raise RuntimeError("negotiation already started")
        self.started = True
        directive = Directive(
            action="ask_quote",
            qty=self.demand_qty,
            round=1,
            max_rounds=self.max_rounds,
            note=(
                f"Open with AI disclosure and verified demand of {self.demand_qty} "
                f"{self.unit} per week."
            ),
        )
        self.events.append(
            {"actor": "engine", "type": "ask_quote", "payload": directive.to_dict()}
        )
        return directive

    # -------------------------------------------------------------- directives
    def next_directive(self) -> Optional[Directive]:
        if self.pending:
            return self.pending.pop(0)
        return None

    def peek_directive(self) -> Optional[Directive]:
        return self.pending[0] if self.pending else None

    # ------------------------------------------------------------------ maths
    def counter_price(self, quote: float, factor: float) -> float:
        """quote - (quote - target) * factor, never below target, never above quote."""
        raw = float(quote) - (float(quote) - self.target_price) * factor
        raw = max(self.target_price, raw)
        raw = min(raw, float(quote))
        rounded = round(raw)
        if rounded < self.target_price:
            rounded = math.ceil(self.target_price - 1e-9)
        if rounded > quote:
            rounded = math.floor(quote)
        return float(rounded)

    @property
    def first_quote(self) -> Optional[Offer]:
        return self.history[0] if self.history else None

    @property
    def latest_quote(self) -> Optional[Offer]:
        return self.history[-1] if self.history else None

    def savings(self) -> Optional[float]:
        """Weekly savings versus the first quote, from stored numbers only."""
        if not self.history or not self.best_eligible:
            return None
        delta = self.first_quote.unit_price - self.best_eligible.unit_price
        if delta <= 0:
            return 0.0
        return round(delta * self.demand_qty, 2)

    def set_competitor(self, price: Optional[float]) -> None:
        """Feed a genuinely recorded competing quote; never an invented one."""
        if price is None:
            return
        if self.competitor_quote is None or price < self.competitor_quote:
            self.competitor_quote = float(price)

    # --------------------------------------------------------------- offers
    def record_offer(self, offer: Offer) -> list[Directive]:
        if self.finished:
            raise RuntimeError("negotiation already finished")
        # Directives built for an older quote are stale the moment a new offer
        # lands; drop them so the agent never counters a price that moved.
        self.pending.clear()
        self.round += 1
        offer.round = self.round
        offer.vendor_id = offer.vendor_id or self.vendor_id
        offer.vendor_name = offer.vendor_name or self.vendor_name
        self.history.append(offer)

        if offer.unit_price <= self.max_price + 1e-9:
            if self.best_eligible is None or offer.unit_price < self.best_eligible.unit_price:
                self.best_eligible = offer

        self.events.append(
            {
                "actor": "vendor",
                "type": "offer",
                "payload": {**offer.to_dict(), "eligible": offer.unit_price <= self.max_price + 1e-9},
            }
        )

        if self.round >= self.max_rounds:
            return self._finish(offer)

        factor = COUNTER_FACTORS[min(self.round - 1, len(COUNTER_FACTORS) - 1)]
        counter = self.counter_price(offer.unit_price, factor)
        self.state = f"COUNTER_{self.round}"

        directives: list[Directive] = []

        if (
            self.competitor_quote is not None
            and not self.mentioned_competitor
            and self.competitor_quote < offer.unit_price
        ):
            self.mentioned_competitor = True
            directives.append(
                Directive(
                    action=MENTION_COMPETITOR,
                    competitor=self.competitor_quote,
                    price=counter,
                    round=self.round,
                    max_rounds=self.max_rounds,
                )
            )

        if not self.asked_delivery and self.round >= 2:
            self.asked_delivery = True
            directives.append(
                Directive(
                    action=ASK_DELIVERY,
                    price=counter,
                    round=self.round,
                    max_rounds=self.max_rounds,
                    note="Ask for free delivery exactly once, after the price has moved.",
                )
            )

        directives.append(
            Directive(
                action=COUNTER,
                price=counter,
                factor=factor,
                qty=self.demand_qty,
                round=self.round,
                max_rounds=self.max_rounds,
                note=(
                    f"Counter at {_money(counter)} for {self.demand_qty} {self.unit} a week. "
                    "Bulk demand is the lever."
                ),
            )
        )
        self.pending.extend(directives)
        for directive in directives:
            self.events.append(
                {"actor": "engine", "type": directive.action, "payload": directive.to_dict()}
            )
        return directives

    def record_delivery(
        self,
        *,
        free: bool,
        charge: Optional[float] = None,
        min_qty: Optional[int] = None,
    ) -> None:
        self.delivery_free = bool(free)
        self.delivery_charge = 0.0 if free else float(charge or 0.0)
        self.events.append(
            {
                "actor": "vendor",
                "type": "delivery_terms",
                "payload": {
                    "free_delivery": self.delivery_free,
                    "delivery_charge": _money(self.delivery_charge or 0),
                    "min_qty": min_qty,
                },
            }
        )
        # The queued counter carries the delivery acknowledgement.
        for directive in self.pending:
            if directive.action == COUNTER:
                directive.free_delivery = self.delivery_free
                directive.delivery_charge = self.delivery_charge

    def record_refusal(self, reason: str = "vendor declined to quote") -> Directive:
        """A vendor who refuses ends this negotiation cleanly."""
        self.state = WALK_AWAY
        self.finished = True
        self.events.append(
            {"actor": "vendor", "type": "refusal", "payload": {"reason": reason}}
        )
        return Directive(
            action=WALK_AWAY_ACTION,
            round=self.round,
            max_rounds=self.max_rounds,
            note=reason,
        )

    def _finish(self, offer: Offer) -> list[Directive]:
        self.state = ESCALATE if self.best_eligible else WALK_AWAY
        self.finished = True
        self.pending = []
        if self.best_eligible:
            directive = Directive(
                action=ESCALATE_ACTION,
                price=self.best_eligible.unit_price,
                round=self.round,
                max_rounds=self.max_rounds,
                note=(
                    f"Offer of {_money(self.best_eligible.unit_price)} is at or below the "
                    "committee ceiling. Escalate for approval; do not accept."
                ),
            )
        else:
            directive = Directive(
                action=WALK_AWAY_ACTION,
                price=offer.unit_price,
                round=self.round,
                max_rounds=self.max_rounds,
                note="No offer reached the committee ceiling.",
            )
        self.events.append(
            {"actor": "engine", "type": self.state.lower(), "payload": directive.to_dict()}
        )
        self.pending.append(directive)
        return [directive]

    # ------------------------------------------------------------------ guard
    def try_accept(self, actor: str = "agent") -> bool:
        """The agent may never accept. Exists so tests can prove it."""
        self.accepted = False
        self.events.append(
            {
                "actor": actor,
                "type": "accept_rejected",
                "payload": {"reason": "Only the committee can approve an offer."},
            }
        )
        return False

    def assert_offer_in_range(self, offer: Offer) -> bool:
        """Bounds check used to validate LLM-extracted numbers."""
        return 0 < offer.unit_price <= self.max_price * 1.5

    # ------------------------------------------------------------------ views
    def public_state(self) -> dict[str, Any]:
        """Safe for the browser: no target, no ceiling, no floor."""
        return {
            "state": self.state,
            "round": self.round,
            "maxRounds": self.max_rounds,
            "product": self.product,
            "unit": self.unit,
            "qty": self.demand_qty,
            "firstQuote": _money(self.first_quote.unit_price) if self.first_quote else None,
            "bestQuote": _money(self.best_eligible.unit_price) if self.best_eligible else None,
            "finished": self.finished,
        }

    def summary_numbers(self) -> dict[str, Any]:
        """Internal, engine-owned numbers for the admin summary."""
        return {
            "product": self.product,
            "unit": self.unit,
            "total_qty": self.demand_qty,
            "first_quote": self.first_quote.unit_price if self.first_quote else None,
            "best_eligible": self.best_eligible.to_dict() if self.best_eligible else None,
            "savings": self.savings(),
            "rounds": self.round,
            "state": self.state,
            "free_delivery": self.delivery_free,
            "delivery_charge": self.delivery_charge,
        }

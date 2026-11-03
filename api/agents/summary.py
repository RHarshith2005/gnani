"""Admin summary, computed only from stored numbers (blueprint §3D)."""

from __future__ import annotations

from typing import Any, Optional

from ..speech.numbers import spell_number, spell_price, unit_word


def _money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    rounded = round(float(value), 2)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.2f}"


def build_admin_summary(
    *,
    community: str,
    households: int,
    product: str,
    unit: str,
    qty: int,
    engines: list[dict[str, Any]],
    language: str = "en-IN",
) -> dict[str, Any]:
    """``engines`` is one summary_numbers() dict per vendor, all engine-owned."""
    offers: list[dict[str, Any]] = []
    for item in engines:
        if not item.get("best_eligible"):
            continue
        best = dict(item["best_eligible"])
        best["vendor_name"] = best.get("vendor_name") or item.get("vendor_name")
        best["delivery_days"] = best.get("delivery_days")
        best["effective"] = round(best["unit_price"] * qty + (best.get("delivery_charge") or 0), 2)
        best["savings"] = round((item["first_quote"] - best["unit_price"]) * qty, 2) if item.get("first_quote") else 0
        best["first_quote"] = item.get("first_quote")
        offers.append(best)

    offers.sort(key=lambda o: (o["effective"], o["unit_price"]))
    eligible = offers
    best = offers[0] if offers else None

    first_quotes = [item["first_quote"] for item in engines if item.get("first_quote")]
    opening = max(first_quotes) if first_quotes else None
    savings = max(0.0, round((opening - best["unit_price"]) * qty, 2)) if best and opening else 0.0

    risks: list[str] = []
    if best:
        if best.get("min_qty") and best["min_qty"] > qty:
            risks.append(
                f"Minimum order of {best['min_qty']} {unit_word(product, 'en-IN')} exceeds the "
                f"{qty} confirmed this week."
            )
        if best.get("delivery_charge"):
            risks.append(
                f"Delivery costs {_money(best['delivery_charge'])} per trip, so the weekly "
                f"effective cost is {_money(best['effective'])}."
            )
        if best.get("delivery_days") and best["delivery_days"] >= 3:
            risks.append(
                f"Delivery takes {best['delivery_days']} days, which is slower than the "
                "one-day options on the table."
            )
        valid = best.get("valid_days")
        if valid:
            risks.append(f"Price holds for {valid} days only; the next order needs a fresh quote.")
    if not offers:
        risks.append("No quote came in at or below the committee ceiling this week.")

    vendor = best["vendor_name"] if best else "no vendor"
    reason = (
        f"lowest effective weekly cost at {_money(best['effective'])} rupees including delivery"
        if best
        else "no offer qualified"
    )
    summary_en = (
        f"Recommend {vendor} for {qty} {unit_word(product, 'en-IN')} a week: {reason}. "
        f"Weekly saving versus the highest opening quote is {_money(savings)} rupees. "
        + (f"Approve a one-week order at {_money(best['unit_price'])} rupees per "
           f"{unit_word(product, 'en-IN', plural=False)}. " if best else "No approval possible. ")
        + "No number here was produced by an LLM."
    )

    if best:
        summary_kn = (
            f"ವಾರಕ್ಕೆ {spell_number(qty, 'kn-IN')} {unit_word(product, 'kn-IN')} ಗೆ "
            f"{vendor} ರವರನ್ನು ಶಿಫಾರಸು ಮಾಡುತ್ತೇವೆ — "
            f"ಒಂದು {unit_word(product, 'kn-IN', plural=False)} ಗೆ "
            f"{spell_price(best['unit_price'], 'kn-IN')}. "
            f"ವಾರಕ್ಕೆ ಉಳಿತಾಯ {spell_price(savings, 'kn-IN')}. ಸಮಿತಿ ಒಪ್ಪಿಗೆ ಬೇಕು."
        )
    else:
        summary_kn = (
            "ಈ ವಾರ ಯಾವುದೇ ಕೊಟೇಶನ್ ಮಿತಿಯೊಳಗೆ ಬರಲಿಲ್ಲ. ಸಮಿತಿ ನಿರ್ಧಾರ ಬೇಕು."
        )

    return {
        "community": community,
        "households": households,
        "product": product,
        "unit": unit_word(product, "en-IN", plural=False),
        "total_qty": qty,
        "first_quote": opening,
        "best": best,
        "offers": offers,
        "savings": savings,
        "risks": risks,
        "summary_en": summary_en,
        "summary_kn": summary_kn,
        "language": language,
    }

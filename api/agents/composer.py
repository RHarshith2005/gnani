"""Deterministic, localized speech built from engine directives.

Every sentence here is templated around numbers that already exist in the
engine. That is what makes the scripted fallback trustworthy: with no LLM key
the demo still speaks correctly, and with an LLM the same numbers are passed in
as ground truth and validated on the way out.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..negotiation.engine import (
    ASK_DELIVERY,
    COUNTER,
    DELIVERY_ACK,
    ESCALATE_ACTION,
    MENTION_COMPETITOR,
    WALK_AWAY_ACTION,
    Directive,
)
from ..negotiation.personas import VendorPersona
from ..speech.numbers import normalise, spell_number, spell_price, unit_word


@dataclass(frozen=True)
class ConversationContext:
    community: str = "Green Residency"
    households: int = 120
    product: str = "water can"
    unit: str = "can"
    qty: int = 360

    @property
    def units(self) -> str:
        return unit_word(self.product, "en-IN")


def _parts(directive: Directive, ctx: ConversationContext, lang: str) -> dict[str, str]:
    return {
        "qty_words": spell_number(ctx.qty, lang),
        "units": unit_word(ctx.product, lang),
        "unit": unit_word(ctx.product, lang, plural=False),
        "price_words": spell_price(directive.price, lang) if directive.price is not None else "",
        "competitor_words": spell_price(directive.competitor, lang)
        if directive.competitor is not None
        else "",
        "community": ctx.community,
        "households": spell_number(ctx.households, lang),
    }


# --------------------------------------------------------------------------- agent
def agent_line(
    directive: Directive,
    ctx: ConversationContext,
    lang: str = "en-IN",
    *,
    vendor_name: str = "",
) -> tuple[str, str]:
    """Return (spoken text in `lang`, English subtitle)."""
    lang = normalise(lang)
    p = _parts(directive, ctx, lang)
    english = _parts(directive, ctx, "en-IN")
    action = directive.action
    free = directive.free_delivery
    greeting = f"{vendor_name}, " if vendor_name else ""

    if action in ("ask_quote", "ASK_QUOTE"):
        if lang == "kn-IN":
            spoken = (
                f"ನಮಸ್ಕಾರ, ನಾನು ನೆಗೋಎಐ, ಒಬ್ಬ ಎಐ ಸಹಾಯಕ. {p['community']} ಸೊಸೈಟಿಯ "
                f"{p['households']} ಮನೆಗಳ ಪರವಾಗಿ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಮಗೆ ವಾರಕ್ಕೆ "
                f"{p['qty_words']} {p['units']} ಬೇಕು. ಒಂದು {p['unit']} ಗೆ ನಿಮ್ಮ ಕೊನೆಯ ಬೆಲೆ ಎಷ್ಟು?"
            )
        elif lang == "hi-IN":
            spoken = (
                f"नमस्ते, मैं NegoAI हूँ, एक एआई सहायक। {p['community']} की {p['households']} "
                f"घरों की ओर से बात कर रहा हूँ। हमें हर हफ्ते {p['qty_words']} {p['units']} चाहिए। "
                f"एक {p['unit']} का आपका सबसे अच्छा दाम क्या है?"
            )
        else:
            spoken = (
                f"Hello, I am NegoAI, an AI assistant speaking for {p['community']}, "
                f"{p['households']} households. We need {p['qty_words']} {p['units']} every week. "
                f"What is your best price per {p['unit']}?"
            )
        subtitle = (
            f"Hello, I am NegoAI, an AI assistant speaking for {english['community']}, "
            f"{english['households']} households. We need {english['qty_words']} {english['units']} "
            f"every week. What is your best price per {english['unit']}?"
        )
        return greeting + spoken, subtitle

    if action == COUNTER:
        lead = ""
        if free is True:
            lead = {
                "en-IN": "With free delivery, ",
                "hi-IN": "मुफ़्त डिलीवरी के साथ, ",
                "kn-IN": "ಉಚಿತ ಡೆಲಿವರಿ ಸೇರಿಸಿ, ",
            }[lang]
        if lang == "kn-IN":
            spoken = (
                f"ಅದು ನಮ್ಮ ಮಿತಿಗಿಂತ ಹೆಚ್ಚು. {lead}ವಾರಕ್ಕೆ {p['qty_words']} {p['units']} ಗೆ "
                f"ಒಂದು {p['unit']} {p['price_words']} ಮಾಡಬಹುದೇ?"
            )
        elif lang == "hi-IN":
            spoken = (
                f"यह हमारी सीमा से ज़्यादा है। {lead}हफ्ते में {p['qty_words']} {p['units']} पर "
                f"एक {p['unit']} {p['price_words']} कर सकते हैं?"
            )
        else:
            spoken = (
                f"That is above our range. {lead}We can do {p['price_words']} per {p['unit']} "
                f"for {p['qty_words']} {p['units']} a week."
            )
        subtitle = (
            f"That is above our range. {lead.lower().capitalize() if lead else ''}We can do "
            f"{english['price_words']} per {english['unit']} for {english['qty_words']} "
            f"{english['units']} a week."
        )
        return spoken, subtitle

    if action == ASK_DELIVERY:
        if lang == "kn-IN":
            return (
                "ಬೆಲೆ ಒಪ್ಪಿಗೆಯಾದರೆ, ಸೊಸೈಟಿ ಗೇಟ್ ವರೆಗೆ ಉಚಿತ ಡೆಲಿವರಿ ಮಾಡುತ್ತೀರಾ?",
                "If the price works, will you deliver free to the society gate?",
            )
        if lang == "hi-IN":
            return (
                "अगर दाम तय हो जाए, तो सोसाइटी गेट तक मुफ़्त डिलीवरी करेंगे?",
                "If the price works, will you deliver free to the society gate?",
            )
        return (
            "If the price works, will you deliver free to the society gate?",
            "If the price works, will you deliver free to the society gate?",
        )

    if action == MENTION_COMPETITOR:
        if lang == "kn-IN":
            return (
                f"ನಮಗೆ ಒಂದು {p['unit']} ಗೆ {p['competitor_words']} ಎಂಬ ಖಚಿತ ಕೊಟೇಶನ್ ಇದೆ. "
                "ಅದಕ್ಕೆ ಸರಿಹೊಂದಿಸಬಹುದೇ?",
                f"We have a verified quote of {english['competitor_words']} per {english['unit']}. "
                "Can you match it?",
            )
        if lang == "hi-IN":
            return (
                f"हमारे पास एक {p['unit']} के {p['competitor_words']} का सत्यापित कोटेशन है। "
                "क्या आप उतना कर सकते हैं?",
                f"We have a verified quote of {english['competitor_words']} per {english['unit']}. "
                "Can you match it?",
            )
        return (
            f"We have a verified quote of {english['competitor_words']} per {english['unit']}. "
            "Can you match it?",
            f"We have a verified quote of {english['competitor_words']} per {english['unit']}. "
            "Can you match it?",
        )

    if action == ESCALATE_ACTION:
        if lang == "kn-IN":
            return (
                "ಧನ್ಯವಾದ. ಈ ಆಫರ್ ಸೊಸೈಟಿ ಸಮಿತಿಯ ಒಪ್ಪಿಗೆಗೆ ಹೋಗುತ್ತದೆ — ನಾನು ಖರೀದಿ "
                "ಖಚಿತಪಡಿಸಲಾರೆ.",
                "Thank you. This offer goes to the community committee for approval — "
                "I cannot confirm a purchase.",
            )
        if lang == "hi-IN":
            return (
                "धन्यवाद। यह ऑफर सोसाइटी कमेटी की मंज़ूरी के लिए जाएगा — मैं खरीद की पुष्टि "
                "नहीं कर सकता।",
                "Thank you. This offer goes to the community committee for approval — "
                "I cannot confirm a purchase.",
            )
        return (
            "Thank you. This offer goes to the community committee for approval — "
            "I cannot confirm a purchase.",
            "Thank you. This offer goes to the community committee for approval — "
            "I cannot confirm a purchase.",
        )

    if action == WALK_AWAY_ACTION:
        if lang == "kn-IN":
            return (
                "ಇದು ನಮ್ಮ ಮಿತಿಗಿಂತ ಹೆಚ್ಚು, ಈ ವಾರ ಬಿಟ್ಟುಬಿಡುತ್ತೇವೆ. ಧನ್ಯವಾದ.",
                "That is above our ceiling, so we will pass this week. Thank you.",
            )
        if lang == "hi-IN":
            return (
                "यह हमारी सीमा से बाहर है, इसलिए इस हफ्ते नहीं ले पाएँगे। धन्यवाद।",
                "That is above our ceiling, so we will pass this week. Thank you.",
            )
        return (
            "That is above our ceiling, so we will pass this week. Thank you for your time.",
            "That is above our ceiling, so we will pass this week. Thank you for your time.",
        )

    if action == DELIVERY_ACK:
        return ("Noted, thank you.", "Noted, thank you.")

    return ("Let me come back to that.", "Let me come back to that.")


# -------------------------------------------------------------------------- vendor
PERSONA_LEAD = {
    "stubborn": {
        "en-IN": "Diesel costs are up, but",
        "hi-IN": "डीज़ल महंगा है, फिर भी",
        "kn-IN": "ಡೀಸೆಲ್ ದರ ಏರಿದೆ, ಆದರೂ",
    },
    "friendly volume-hungry": {
        "en-IN": "For the whole society,",
        "hi-IN": "पूरी सोसाइटी के लिए,",
        "kn-IN": "ಇಡೀ ಸೊಸೈಟಿಗೆ,",
    },
    "cheap but slow": {
        "en-IN": "Lowest rate, but",
        "hi-IN": "सबसे कम दर, लेकिन",
        "kn-IN": "ಕಡಿಮೆ ದರ, ಆದರೆ",
    },
}


def vendor_line(
    reply: dict,
    persona: VendorPersona,
    ctx: ConversationContext,
    lang: str = "en-IN",
) -> tuple[str, str]:
    """Return (spoken line, English subtitle) for a simulated vendor reply."""
    lang = normalise(lang)
    kind = reply.get("kind", "quote")
    lead = PERSONA_LEAD.get(persona.personality, {}).get(lang, "")

    if kind == "delivery":
        free = reply.get("free_delivery")
        min_qty = reply.get("min_qty") or 0
        charge = reply.get("delivery_charge") or 0
        days = persona.delivery_days
        if free:
            spoken = {
                "en-IN": f"Free delivery above {spell_number(min_qty, 'en-IN')} cans, to the gate. Delivery in {spell_number(days, 'en-IN')} days.",
                "hi-IN": f"{spell_number(min_qty, 'hi-IN')} कैन से ऊपर गेट तक मुफ़्त डिलीवरी, {spell_number(days, 'hi-IN')} दिन में।",
                "kn-IN": f"{spell_number(min_qty, 'kn-IN')} ಕ್ಯಾನ್ ಮೇಲೆ ಗೇಟ್ ವರೆಗೆ ಉಚಿತ ಡೆಲಿವರಿ, {spell_number(days, 'kn-IN')} ದಿನದಲ್ಲಿ.",
            }[lang]
            subtitle = (
                f"Free delivery above {spell_number(min_qty, 'en-IN')} cans to the gate, "
                f"in {spell_number(days, 'en-IN')} days."
            )
        else:
            spoken = {
                "en-IN": f"Delivery is {spell_price(charge, 'en-IN')} per trip, in {spell_number(days, 'en-IN')} days.",
                "hi-IN": f"डिलीवरी {spell_price(charge, 'hi-IN')} प्रति ट्रिप, {spell_number(days, 'hi-IN')} दिन में।",
                "kn-IN": f"ಡೆಲಿವರಿ ಪ್ರತಿ ಟ್ರಿಪ್ {spell_price(charge, 'kn-IN')}, {spell_number(days, 'kn-IN')} ದಿನದಲ್ಲಿ.",
            }[lang]
            subtitle = (
                f"Delivery is {spell_price(charge, 'en-IN')} per trip, in "
                f"{spell_number(days, 'en-IN')} days."
            )
        return spoken, subtitle

    if kind == "refuse":
        return (
            {
                "en-IN": "That rate is not possible. Try someone else.",
                "hi-IN": "इस दाम पर नहीं हो सकता। किसी और से पूछ लीजिए।",
                "kn-IN": "ಆ ದರಕ್ಕೆ ಸಾಧ್ಯವಿಲ್ಲ. ಬೇರೆ ಎಡೆಯಲ್ಲಿ ನೋಡಿ.",
            }[lang],
            "That rate is not possible. Try someone else.",
        )

    price = reply.get("unit_price")
    price_words = spell_price(price, lang) if price is not None else ""
    qty_words = spell_number(ctx.qty, lang)
    if lang == "kn-IN":
        spoken = f"{lead} ವಾರಕ್ಕೆ {qty_words} {unit_word(ctx.product, 'kn-IN')} ಗೆ ಒಂದು {unit_word(ctx.product, 'kn-IN', plural=False)} {price_words}."
    elif lang == "hi-IN":
        spoken = f"{lead} हफ्ते में {qty_words} {unit_word(ctx.product, 'hi-IN')} पर एक {unit_word(ctx.product, 'hi-IN', plural=False)} {price_words}."
    else:
        spoken = (
            f"{lead} {price_words} per {unit_word(ctx.product, 'en-IN', plural=False)} "
            f"for {qty_words} {unit_word(ctx.product, 'en-IN')} a week."
        )
    subtitle = (
        f"{price_words} per {unit_word(ctx.product, 'en-IN', plural=False)} for "
        f"{qty_words} {unit_word(ctx.product, 'en-IN')} a week."
    )
    return spoken, subtitle

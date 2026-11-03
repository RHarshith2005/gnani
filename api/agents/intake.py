"""Resident demand collector (blueprint §3A).

One question at a time, quantity read back in words, only confirmed quantities
count. Deterministic so it works with no LLM and is testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..speech.numbers import (
    normalise,
    parse_number,
    spell_number,
    unit_word,
)

PRODUCT_KEYWORDS = {
    "water can": ("water", "can", "cans", "ಕ್ಯಾನ್", "ನೀರ", "पानी", "कैन"),
    "milk": ("milk", "ಹಾಲು", "दूध", "packet"),
    "vegetables": ("vegetable", "veg", "ತರಕಾರಿ", "सब्ज़ी", "सब्जी"),
}

AFFIRM = (
    "yes", "yeah", "correct", "right", "confirm", "ok", "okay", "sure", "haan", "ha",
    "ಹೌದು", "ಸರಿ", "ಹಾ", "हाँ", "हां", "ठीक", "सही", "जी",
)
NEGATE = ("no", "not", "wrong", "change", "इल्ल", "ಇಲ್ಲ", "नहीं", "ना", "गलत")

DAYS = {
    "monday": "Monday", "mon": "Monday", "सोमवार": "Monday", "ಸೋಮವಾರ": "Monday",
    "tuesday": "Tuesday", "tue": "Tuesday", "मंगलवार": "Tuesday", "ಮಂಗಳವಾರ": "Tuesday",
    "wednesday": "Wednesday", "wed": "Wednesday", "बुधवार": "Wednesday", "ಬುಧವಾರ": "Wednesday",
    "thursday": "Thursday", "thu": "Thursday", "गुरुवार": "Thursday", "ಗುರುವಾರ": "Thursday",
    "friday": "Friday", "fri": "Friday", "शुक्रवार": "Friday", "ಶುಕ್ರವಾರ": "Friday",
    "saturday": "Saturday", "sat": "Saturday", "शनिवार": "Saturday", "ಶನಿವಾರ": "Saturday",
    "sunday": "Sunday", "sun": "Sunday", "रविवार": "Sunday", "ಭಾನುವಾರ": "Sunday",
    "tomorrow": "Tomorrow", "कल": "Tomorrow", "ನಾಳೆ": "Tomorrow",
}

DAY_ALIASES = {
    "monday": "Monday", "mon": "Monday", "सोमवार": "Monday", "ಸೋಮವಾರ": "Monday",
    "tuesday": "Tuesday", "tue": "Tuesday", "मंगलवार": "Tuesday", "ಮಂಗಳವಾರ": "Tuesday",
    "wednesday": "Wednesday", "wed": "Wednesday", "बुधवार": "Wednesday", "ಬುಧವಾರ": "Wednesday",
    "thursday": "Thursday", "thu": "Thursday", "गुरुवार": "Thursday", "ಗುರುವಾರ": "Thursday",
    "friday": "Friday", "fri": "Friday", "शुक्रवार": "Friday", "ಶುಕ್ರವಾರ": "Friday",
    "saturday": "Saturday", "sat": "Saturday", "शनिवार": "Saturday", "ಶನಿವಾರ": "Saturday",
    "sunday": "Sunday", "sun": "Sunday", "रविवार": "Sunday", "ಭಾನುವಾರ": "Sunday",
}


@dataclass
class IntakeReply:
    kind: str  # ask | confirm | done | clarify
    say: str
    subtitle: str
    stage: str
    slots: dict
    done: bool = False


@dataclass
class IntakeState:
    language: str = "kn-IN"
    product: Optional[str] = None
    qty: Optional[int] = None
    frequency: str = "weekly"
    delivery_day: Optional[str] = None
    flat_number: Optional[str] = None
    confirmed: bool = False
    stage: str = "product"
    attempts: int = 0
    extra: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers
    def slots(self) -> dict:
        return {
            "product": self.product,
            "qty": self.qty,
            "frequency": self.frequency,
            "delivery_day": self.delivery_day,
            "flat_number": self.flat_number,
            "language": self.language,
            "confirmed": self.confirmed,
        }

    def detect_language(self, text: str) -> str:
        if re.search(r"[\u0C80-\u0CFF]", text):
            return "kn-IN"
        if re.search(r"[\u0900-\u097F]", text):
            return "hi-IN"
        if re.search(r"[A-Za-z]", text):
            return "en-IN" if self.language != "kn-IN" else self.language
        return self.language

    def _product_from(self, text: str) -> Optional[str]:
        lower = text.lower()
        for product, keywords in PRODUCT_KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                return product
        return None

    def _affirm(self, text: str) -> bool:
        lower = text.lower().strip()
        return any(word in lower.split() or word in lower for word in AFFIRM)

    def _negate(self, text: str) -> bool:
        lower = text.lower().strip()
        return any(word in lower for word in NEGATE)

    def _flat(self, text: str) -> Optional[str]:
        match = re.search(r"([A-Za-z]?[-/]?\d{1,4}[A-Za-z]?)", text)
        if match:
            value = match.group(1)
            if any(ch.isdigit() for ch in value):
                return value.upper()
        return None

    def _confirm_reply(self) -> IntakeReply:
        lang = self.language
        units = unit_word(self.product or "water can", lang)
        qty_words = spell_number(self.qty or 0, lang)
        confirm = {
            "en-IN": f"{qty_words} {units} every week — correct?",
            "hi-IN": f"हर हफ्ते {qty_words} {units} — सही है?",
            "kn-IN": f"ವಾರಕ್ಕೆ {qty_words} {units} — ಸರಿಯೇ?",
        }[lang]
        subtitle = (
            f"{spell_number(self.qty or 0, 'en-IN')} "
            f"{unit_word(self.product or 'water can', 'en-IN')} every week — correct?"
        )
        return IntakeReply("confirm", confirm, subtitle, self.stage, self.slots())

    # -------------------------------------------------------------------- speech
    def _question(self, stage: str) -> tuple[str, str]:
        lang = self.language
        units = unit_word(self.product or "water can", lang)
        english_units = unit_word(self.product or "water can", "en-IN")
        if stage == "product":
            return {
                "en-IN": "What do you need this week — water cans, milk or vegetables?",
                "hi-IN": "इस हफ्ते क्या चाहिए — पानी के कैन, दूध या सब्ज़ी?",
                "kn-IN": "ಈ ವಾರ ಏನು ಬೇಕು — ನೀರಿನ ಕ್ಯಾನ್, ಹಾಲು ಅಥವಾ ತರಕಾರಿ?",
            }[lang], "What do you need this week — water cans, milk or vegetables?"
        if stage == "quantity":
            return {
                "en-IN": f"How many {english_units} every week?",
                "hi-IN": f"हर हफ्ते कितने {units} चाहिए?",
                "kn-IN": f"ವಾರಕ್ಕೆ ಎಷ್ಟು {units} ಬೇಕು?",
            }[lang], f"How many {english_units} every week?"
        if stage == "delivery_day":
            return {
                "en-IN": "Which day should it be delivered?",
                "hi-IN": "किस दिन डिलीवरी चाहिए?",
                "kn-IN": "ಯಾವ ದಿನ ಡೆಲಿವರಿ ಬೇಕು?",
            }[lang], "Which day should it be delivered?"
        if stage == "flat":
            return {
                "en-IN": "And which flat number should I add this to?",
                "hi-IN": "और किस फ्लैट नंबर पर जोड़ूँ?",
                "kn-IN": "ಮತ್ತು ಯಾವ ಫ್ಲಾಟ್ ನಂಬರ್‌ಗೆ ಸೇರಿಸಲಿ?",
            }[lang], "And which flat number should I add this to?"
        return ("", "")

    # --------------------------------------------------------------------- flow
    def handle(self, text: str) -> IntakeReply:
        text = (text or "").strip()
        self.language = self.detect_language(text)
        lang = self.language

        if self.stage == "product":
            product = self._product_from(text)
            if not product:
                say, sub = self._question("product")
                return IntakeReply("ask", say, sub, self.stage, self.slots())
            self.product = product
            # "three water cans" carries product and quantity in one breath.
            qty = parse_number(text, lang)
            if qty is not None and 0 < qty <= 5000:
                self.qty = qty
                self.stage = "confirm"
                return self._confirm_reply()
            self.stage = "quantity"
            say, sub = self._question("quantity")
            return IntakeReply("ask", say, sub, self.stage, self.slots())

        if self.stage in ("quantity", "confirm"):
            if self.stage == "confirm":
                if self._affirm(text) and not self._negate(text):
                    self.confirmed = True
                    self.stage = "delivery_day"
                    say, sub = self._question("delivery_day")
                    return IntakeReply("ask", say, sub, self.stage, self.slots())
                if self._negate(text):
                    self.stage = "quantity"
                    self.confirmed = False
                    self.qty = None
                    say, sub = self._question("quantity")
                    return IntakeReply("ask", say, sub, self.stage, self.slots())

            qty = parse_number(text, lang)
            if qty is None or qty <= 0 or qty > 5000:
                self.attempts += 1
                say, sub = self._question("quantity")
                clarify = {
                    "en-IN": "Sorry, I did not catch a number. ",
                    "hi-IN": "माफ़ कीजिए, संख्या समझ नहीं आई। ",
                    "kn-IN": "ಕ್ಷಮಿಸಿ, ಸಂಖ್ಯೆ ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ",
                }[lang]
                return IntakeReply(
                    "clarify",
                    clarify + say,
                    "Sorry, I did not catch a number. " + sub,
                    self.stage,
                    self.slots(),
                )

            self.qty = qty
            self.stage = "confirm"
            return self._confirm_reply()

        if self.stage == "delivery_day":
            lower = text.lower()
            day = next((value for key, value in DAY_ALIASES.items() if key in lower), None)
            if day is None:
                if not text or len(text) > 40:
                    say, sub = self._question("delivery_day")
                    return IntakeReply("ask", say, sub, self.stage, self.slots())
                day = text[:40]
            self.delivery_day = day
            self.stage = "flat"
            say, sub = self._question("flat")
            return IntakeReply("ask", say, sub, self.stage, self.slots())

        if self.stage == "flat":
            flat = self._flat(text) or (text[:12].upper() if text else None)
            if not flat:
                say, sub = self._question("flat")
                return IntakeReply("ask", say, sub, self.stage, self.slots())
            self.flat_number = flat
            self.stage = "done"
            units = unit_word(self.product or "water can", lang)
            qty_words = spell_number(self.qty or 0, lang)
            day = self.delivery_day or ""
            say = {
                "en-IN": f"Added. {qty_words} {units} every week, {day} delivery. The community will negotiate and share the result — no price promised today.",
                "hi-IN": f"जोड़ दिया। हर हफ्ते {qty_words} {units}, {day} डिलीवरी। समुदाय मोल-भाव करके बताएगा — आज कोई दाम वादा नहीं।",
                "kn-IN": f"ಸೇರಿಸಲಾಗಿದೆ. ವಾರಕ್ಕೆ {qty_words} {units}, {day} ಡೆಲಿವರಿ. ಸಮುದಾಯ ಮಾತುಕತೆ ನಡೆಸಿ ಫಲಿತಾಂಶ ತಿಳಿಸುತ್ತದೆ — ಇಂದು ಬೆಲೆ ಭರವಸೆ ಇಲ್ಲ.",
            }[lang]
            subtitle = (
                f"Added. {spell_number(self.qty or 0, 'en-IN')} "
                f"{unit_word(self.product or 'water can', 'en-IN')} every week, {day} delivery. "
                "The community will negotiate and share the result — no price promised today."
            )
            return IntakeReply("done", say, subtitle, self.stage, self.slots(), done=True)

        return IntakeReply("done", "This requirement is already saved.", "This requirement is already saved.", self.stage, self.slots(), done=True)

    # ------------------------------------------------------------------ guided
    def scripted_turn(self, text: str) -> IntakeReply:
        """Same flow, used by the guided demo with a fixed resident script."""
        return self.handle(text)

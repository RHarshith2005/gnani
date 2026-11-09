"""Numbers as spoken words.

Gnani's docs require numbers, dates and currency to be passed to TTS as spoken
words, so every price and quantity is spelled out before synthesis. The same
maps run backwards to parse a resident's demand ("three hundred sixty",
"ಮೂರು ನೂರು ಅರವತ್ತು").
"""

from __future__ import annotations

import re
from typing import Optional

SUPPORTED = ("en-IN", "hi-IN", "kn-IN")

# --------------------------------------------------------------------------- English
EN_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
EN_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _en_below_100(n: int) -> str:
    if n < 20:
        return EN_ONES[n]
    tens, ones = divmod(n, 10)
    return EN_TENS[tens] + (f"-{EN_ONES[ones]}" if ones else "")


def _en_below_1000(n: int) -> str:
    if n < 100:
        return _en_below_100(n)
    hundreds, rest = divmod(n, 100)
    out = f"{EN_ONES[hundreds]} hundred"
    if rest:
        out += f" and {_en_below_100(rest)}"
    return out


def spell_en(n: int) -> str:
    n = int(n)
    if n < 0:
        return f"minus {spell_en(-n)}"
    if n == 0:
        return "zero"
    parts: list[str] = []
    for value, name in ((10_000_000, "crore"), (100_000, "lakh"), (1_000, "thousand")):
        if n >= value:
            count, n = divmod(n, value)
            parts.append(f"{_en_below_1000(count)} {name}")
    if n:
        parts.append(_en_below_1000(n))
    return " ".join(parts)


# ---------------------------------------------------------------------------- Hindi
HI = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छह", 7: "सात",
    8: "आठ", 9: "नौ", 10: "दस", 11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह",
    15: "पंद्रह", 16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस", 26: "छब्बीस",
    27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 30: "तीस", 31: "इकतीस", 32: "बत्तीस",
    33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस", 36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस",
    39: "उनतालीस", 40: "चालीस", 41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस",
    44: "चवालीस", 45: "पैंतालीस", 46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस",
    49: "उनचास", 50: "पचास", 51: "इक्यावन", 52: "बावन", 53: "तिरपन", 54: "चौवन",
    55: "पचपन", 56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन", 59: "उनसठ", 60: "साठ",
    61: "इकसठ", 62: "बासठ", 63: "तिरसठ", 64: "चौंसठ", 65: "पैंसठ", 66: "छियासठ",
    67: "सड़सठ", 68: "अड़सठ", 69: "उनहत्तर", 70: "सत्तर", 71: "इकहत्तर", 72: "बहत्तर",
    73: "तिहत्तर", 74: "चौहत्तर", 75: "पचहत्तर", 76: "छिहत्तर", 77: "सतहत्तर",
    78: "अठहत्तर", 79: "उनासी", 80: "अस्सी", 81: "इक्यासी", 82: "बयासी", 83: "तिरासी",
    84: "चौरासी", 85: "पचासी", 86: "छियासी", 87: "सत्तासी", 88: "अट्ठासी", 89: "नवासी",
    90: "नब्बे", 91: "इक्यानवे", 92: "बानवे", 93: "तिरानवे", 94: "चौरानवे",
    95: "पंचानवे", 96: "छियानवे", 97: "सत्तानवे", 98: "अट्ठानवे", 99: "निन्यानवे",
    100: "सौ",
}


def spell_hi(n: int) -> str:
    n = int(n)
    if n < 0:
        return f"माइनस {spell_hi(-n)}"
    if n <= 100:
        return HI[n]
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        out = f"{HI[hundreds]} सौ"
        if rest:
            out += f" {HI[rest]}"
        return out
    parts: list[str] = []
    for value, name in ((10_000_000, "करोड़"), (100_000, "लाख"), (1_000, "हज़ार")):
        if n >= value:
            count, n = divmod(n, value)
            parts.append(f"{spell_hi(count)} {name}")
    if n:
        parts.append(spell_hi(n))
    return " ".join(parts)


# -------------------------------------------------------------------------- Kannada
KN_BASE = {
    0: "ಸೊನ್ನೆ", 1: "ಒಂದು", 2: "ಎರಡು", 3: "ಮೂರು", 4: "ನಾಲ್ಕು", 5: "ಐದು", 6: "ಆರು",
    7: "ಏಳು", 8: "ಎಂಟು", 9: "ಒಂಬತ್ತು", 10: "ಹತ್ತು", 11: "ಹನ್ನೊಂದು", 12: "ಹನ್ನೆರಡು",
    13: "ಹದಿಮೂರು", 14: "ಹದಿನಾಲ್ಕು", 15: "ಹದಿನೈದು", 16: "ಹದಿನಾರು", 17: "ಹದಿನೇಳು",
    18: "ಹದಿನೆಂಟು", 19: "ಹತ್ತೊಂಬತ್ತು", 20: "ಇಪ್ಪತ್ತು", 30: "ಮೂವತ್ತು", 40: "ನಲವತ್ತು",
    50: "ಐವತ್ತು", 60: "ಅರವತ್ತು", 70: "ಎಪ್ಪತ್ತು", 80: "ಎಂಬತ್ತು", 90: "ತೊಂಬತ್ತು",
    100: "ನೂರು",
}

KN = dict(KN_BASE)
# Kannada compounds are regular: stem (drop the final ು) + the unit word.
_KN_STEMS = {20: "ಇಪ್ಪತ್ತ", 30: "ಮೂವತ್ತ", 40: "ನಲವತ್ತ", 50: "ಐವತ್ತ", 60: "ಅರವತ್ತ", 70: "ಎಪ್ಪತ್ತ", 80: "ಎಂಬತ್ತ", 90: "ತೊಂಬತ್ತ"}
for _tens in (20, 30, 40, 50, 60, 70, 80, 90):
    for _unit in range(1, 10):
        KN[_tens + _unit] = f"{_KN_STEMS[_tens]}{KN[_unit]}"


def spell_kn(n: int) -> str:
    n = int(n)
    if n < 0:
        return f"ಮೈನಸ್ {spell_kn(-n)}"
    if n <= 100:
        return KN[n]
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        out = f"{KN[hundreds]} ನೂರು"
        if rest:
            out += f" {spell_kn(rest)}"
        return out
    parts: list[str] = []
    for value, name in ((10_000_000, "ಕೋಟಿ"), (100_000, "ಲಕ್ಷ"), (1_000, "ಸಾವಿರ")):
        if n >= value:
            count, n = divmod(n, value)
            parts.append(f"{spell_kn(count)} {name}")
    if n:
        parts.append(spell_kn(n))
    return " ".join(parts)


# -------------------------------------------------------------------------- helpers
def normalise(lang: str) -> str:
    lang = (lang or "en-IN").strip()
    if lang in SUPPORTED:
        return lang
    prefix = lang.split("-")[0].lower()
    return {"kn": "kn-IN", "ka": "kn-IN", "hi": "hi-IN", "en": "en-IN"}.get(prefix, "en-IN")


def spell_number(n: int, lang: str = "en-IN") -> str:
    lang = normalise(lang)
    if lang == "hi-IN":
        return spell_hi(n)
    if lang == "kn-IN":
        return spell_kn(n)
    return spell_en(n)


CURRENCY = {
    "en-IN": ("rupee", "rupees"),
    "hi-IN": ("रुपया", "रुपये"),
    "kn-IN": ("ರೂಪಾಯಿ", "ರೂಪಾಯಿ"),
}

PAISE = {"en-IN": "paise", "hi-IN": "पैसे", "kn-IN": "ಪೈಸೆ"}


def spell_price(amount: float, lang: str = "en-IN") -> str:
    """`19` -> "nineteen rupees" / "उन्नीस रुपये" / "ಹತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ"."""
    lang = normalise(lang)
    amount = float(amount or 0)
    whole = int(amount)
    paise = round((amount - whole) * 100)
    singular, plural = CURRENCY[lang]
    word = singular if whole == 1 else plural
    out = f"{spell_number(whole, lang)} {word}"
    if paise:
        out += f" {PAISE[lang]} {spell_number(paise, lang)}"
    return out


UNIT_WORDS = {
    "water can": {"en-IN": "water cans", "hi-IN": "पानी के कैन", "kn-IN": "ನೀರಿನ ಕ್ಯಾನ್"},
    "water": {"en-IN": "water cans", "hi-IN": "पानी के कैन", "kn-IN": "ನೀರಿನ ಕ್ಯಾನ್"},
    "milk": {"en-IN": "milk packets", "hi-IN": "दूध के पैकेट", "kn-IN": "ಹಾಲಿನ ಪ್ಯಾಕೆಟ್"},
    "vegetables": {"en-IN": "vegetable baskets", "hi-IN": "सब्ज़ी की टोकरी", "kn-IN": "ತರಕಾರಿ ಬುಟ್ಟಿ"},
}


def unit_word(unit: str, lang: str = "en-IN", *, plural: bool = True) -> str:
    lang = normalise(lang)
    key = (unit or "unit").lower()
    word = UNIT_WORDS.get(key, {}).get(lang, key)
    # Only English marks the plural with an -s; Kannada and Hindi use the same
    # form for one and many here.
    if not plural and lang == "en-IN" and word.endswith("s"):
        return word[:-1]
    return word


# --------------------------------------------------------------------------- parsing
REVERSE_EN = {word: value for value, word in enumerate(EN_ONES)}
REVERSE_EN.update({word: index * 10 for index, word in enumerate(EN_TENS) if word})
for tens_index, tens in enumerate(EN_TENS):
    if not tens:
        continue
    for ones in range(1, 10):
        REVERSE_EN[f"{tens}-{EN_ONES[ones]}"] = tens_index * 10 + ones

REVERSE_HI = {word: value for value, word in HI.items() if value <= 100}
# Common spellings people actually type (no chandrabindu) still parse.
REVERSE_HI.update({"पांच": 5, "पंद्रह": 15, "पैंतीस": 35, "पचास": 50})
REVERSE_KN = {word: value for value, word in KN.items() if value <= 100}

_REVERSE = {"en-IN": REVERSE_EN, "hi-IN": REVERSE_HI, "kn-IN": REVERSE_KN}

_HUNDREDS = {"hundred", "सौ", "ನೂರು"}
_THOUSANDS = {"thousand", "हज़ार", "ಸಾವಿರ"}


def parse_number(text: str, lang: str = "en-IN") -> Optional[int]:
    """Best-effort number out of a spoken phrase; digits win, then word sums."""
    if not text:
        return None
    digits = re.search(r"\d+", text.replace(",", ""))
    if digits:
        return int(digits.group(0))

    lang = normalise(lang)
    tokens = re.split(r"[\s,.]+", text.lower())
    table = _REVERSE[lang]
    # Try every language's vocabulary — code-mixed speech is the norm.
    tables = [table] + [t for key, t in _REVERSE.items() if key != lang]

    total = 0
    current = 0
    found = False
    gap = False
    for token in tokens:
        # "one hundred and twenty" is one group; "and" must not split it.
        if token in {"and", "plus", "और", "मತ್ತು"}:
            continue
        value = None
        if token in _HUNDREDS:
            value = 100
        elif token in _THOUSANDS:
            value = 1000
        else:
            for candidate in tables:
                if token in candidate:
                    value = candidate[token]
                    break
        if value is None:
            if found:
                gap = True
            continue
        if found and gap:
            # A second separated group is a restatement ("three cans ... three
            # cans"), not an addition. The first quantity wins.
            break
        gap = False
        found = True
        if value == 100:
            current = (current or 1) * 100
        elif value >= 1000:
            total += (current or 1) * value
            current = 0
        else:
            current += value
    if not found:
        return None
    return total + current

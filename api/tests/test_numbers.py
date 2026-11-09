from __future__ import annotations

from api.speech.numbers import (
    parse_number,
    spell_number,
    spell_price,
    unit_word,
)


def test_english_price():
    assert spell_price(19, "en-IN") == "nineteen rupees"
    assert spell_price(1, "en-IN") == "one rupee"


def test_hindi_quantity():
    assert spell_number(360, "hi-IN") == "तीन सौ साठ"
    assert spell_price(19, "hi-IN") == "उन्नीस रुपये"


def test_kannada_quantity():
    assert spell_number(3, "kn-IN") == "ಮೂರು"
    assert spell_number(360, "kn-IN") == "ಮೂರು ನೂರು ಅರವತ್ತು"
    assert spell_price(19, "kn-IN") == "ಹತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ"


def test_parse_english_words():
    assert parse_number("Three water cans every week") == 3
    assert parse_number("three hundred sixty cans") == 360
    assert parse_number("Please send 12 cans") == 12


def test_parse_hindi_and_kannada_words():
    assert parse_number("तीन पानी के कैन", "hi-IN") == 3
    assert parse_number("ಮೂರು ನೂರು ಅರವತ್ತು ಕ್ಯಾನ್", "kn-IN") == 360
    assert parse_number("निन्यानवे", "hi-IN") == 99


def test_restated_quantity_is_not_summed():
    # Noisy rooms repeat the same request; the second group is a restatement.
    assert (
        parse_number(
            "ನನಗೆ ವಾರಕ್ಕೆ ಮೂರು ನೀರಿನ ಕ್ಯಾನ್ ಬೇಕು, ದಯವಿಟ್ಟು ವಾರಕ್ಕೆ ಮೂರು ಕ್ಯಾನ್ ಕೊಡಿ",
            "kn-IN",
        )
        == 3
    )
    assert parse_number("three water cans, three water cans", "en-IN") == 3
    # "and" stays inside one number group.
    assert parse_number("three hundred and sixty cans", "en-IN") == 360


def test_parse_returns_none_for_no_number():
    assert parse_number("water cans please") is None
    assert parse_number("") is None


def test_unit_words():
    assert unit_word("water can", "en-IN") == "water cans"
    assert unit_word("water can", "en-IN", plural=False) == "water can"
    assert unit_word("water can", "kn-IN") == "ನೀರಿನ ಕ್ಯಾನ್"
    assert unit_word("water can", "hi-IN") == "पानी के कैन"

from __future__ import annotations

from api.agents.intake import IntakeState


def test_english_flow_confirms_only_after_yes():
    state = IntakeState(language="en-IN")
    first = state.handle("Three water cans every week")
    assert first.kind == "confirm"
    assert state.qty == 3
    assert state.confirmed is False

    second = state.handle("yes, correct")
    assert second.stage == "delivery_day"
    assert state.confirmed is True

    state.handle("Saturday")
    done = state.handle("B-402")
    assert done.done is True
    assert state.flat_number == "B-402"
    assert state.delivery_day == "Saturday"


def test_kannada_flow():
    state = IntakeState(language="kn-IN")
    first = state.handle("ನನಗೆ ವಾರಕ್ಕೆ ಮೂರು ನೀರಿನ ಕ್ಯಾನ್ ಬೇಕು")
    assert state.language == "kn-IN"
    assert state.product == "water can"
    assert first.kind == "confirm"
    assert "ಮೂರು" in first.say

    state.handle("ಹೌದು, ಸರಿ")
    assert state.confirmed is True
    state.handle("ಶನಿವಾರ")
    done = state.handle("ಬಿ-402")
    assert done.done is True


def test_hindi_flow():
    state = IntakeState(language="hi-IN")
    first = state.handle("मुझे हर हफ्ते पांच पानी के कैन चाहिए")
    assert state.language == "hi-IN"
    assert state.qty == 5
    assert first.kind == "confirm"
    state.handle("हाँ, सही है")
    assert state.confirmed is True


def test_code_mixed_english_kannada():
    state = IntakeState(language="kn-IN")
    result = state.handle("Water can, three, weekly")
    assert state.product == "water can"
    assert state.qty == 3
    assert result.kind == "confirm"


def test_misheard_number_asks_again_and_never_guesses():
    state = IntakeState(language="en-IN")
    state.handle("water cans")
    reply = state.handle("just some cans")
    assert reply.kind == "clarify"
    assert state.qty is None
    assert state.confirmed is False


def test_negation_returns_to_quantity():
    state = IntakeState(language="en-IN")
    state.handle("Three water cans")
    reply = state.handle("no, change it")
    assert reply.stage == "quantity"
    assert state.confirmed is False

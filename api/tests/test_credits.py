"""Credit guard and voice separation for the audio negotiation (Prompt 10)."""

from __future__ import annotations

from api.speech.gnani import GnaniTTSService, TTSCreditGuard


def test_credit_guard_stops_at_the_session_cap():
    guard = TTSCreditGuard(budget=1_000, session_cap=10)
    assert guard.allow(6) is True
    assert guard.allow(4) is True
    assert guard.allow(1) is False
    assert guard.exhausted is True
    # An exhausted guard never resumes, so the UI stays in text mode.
    assert guard.allow(1) is False


def test_vendor_voice_differs_from_the_negotiator():
    service = GnaniTTSService()
    for language in ("kn-IN", "hi-IN", "en-IN"):
        default = service.voice_for(language)
        chosen = service.distinct_voice(language, default)
        assert chosen != default

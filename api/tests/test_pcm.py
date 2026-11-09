"""Audio plumbing: RMS, base64 transport and linear resampling."""

from __future__ import annotations

import struct

from api.voice.pcm import b64decode_pcm, b64encode_pcm, resample_pcm16, rms


def test_rms_of_silence_and_a_tone():
    assert rms(b"") == 0.0
    tone = struct.pack("<8h", *([1000] * 8))
    assert 0.0 < rms(tone) <= 1.0
    assert rms(b"\x00") == 0.0  # odd byte count is ignored


def test_base64_roundtrip_and_invalid_input():
    data = struct.pack("<4h", 1, -2, 3, -4)
    assert b64decode_pcm(b64encode_pcm(data)) == data
    assert b64decode_pcm("not-base64!!") == b""


def test_resample_halves_the_sample_count():
    source = struct.pack("<100h", *([0] * 100))
    out = resample_pcm16(source, 16000, 8000)
    assert len(out) == 100  # 50 samples x 2 bytes
    assert resample_pcm16(source, 16000, 16000) == source

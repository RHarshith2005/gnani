"""PCM helpers shared by the gateway, the STT bridge and tests."""

from __future__ import annotations

import base64
import math
from array import array


def rms(pcm16: bytes) -> float:
    """Root-mean-square of a PCM16 little-endian buffer, normalised to 0..1."""
    if not pcm16:
        return 0.0
    usable = len(pcm16) - (len(pcm16) % 2)
    if usable <= 0:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm16[:usable])
    if not samples:
        return 0.0
    total = 0
    for sample in samples:
        total += sample * sample
    return min(1.0, math.sqrt(total / len(samples)) / 32768.0)


def b64decode_pcm(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception:
        return b""


def b64encode_pcm(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear resample for callers that cannot negotiate 16 kHz."""
    if src_rate == dst_rate or not data:
        return data
    source = array("h")
    source.frombytes(data[: len(data) - (len(data) % 2)])
    if not source:
        return b""
    ratio = src_rate / dst_rate
    out_len = int(len(source) / ratio)
    out = array("h", bytes(2 * out_len))
    last = len(source) - 1
    for i in range(out_len):
        position = i * ratio
        index = int(position)
        frac = position - index
        nxt = index + 1 if index < last else index
        value = source[index] * (1 - frac) + source[nxt] * frac
        out[i] = max(-32768, min(32767, int(value)))
    return out.tobytes()

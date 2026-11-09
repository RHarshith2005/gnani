"""The Gnani wire contract, pinned without touching the network."""

from __future__ import annotations

import asyncio
import struct

from api.config import Settings
from api.speech.gnani import (
    STT_FRAME_BYTES,
    GnaniSTTStream,
    GnaniTTSService,
    pcm_from_wav,
)


def _settings() -> Settings:
    return Settings(gnani_api_key="test-key", gnani_key_id="test-key")


class FakeResponse:
    status_code = 200
    text = ""
    headers = {"content-type": "application/octet-stream"}
    content = b"\x01\x00" * 320

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []

    async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
        self.calls.append((url, json, headers))
        return FakeResponse()


def test_tts_request_matches_the_documented_contract():
    service = GnaniTTSService(_settings())
    client = FakeClient()
    service._client = client  # type: ignore[assignment]

    pcm = asyncio.run(service.synthesize("ನಮಸ್ಕಾರ", "kn-IN"))

    assert pcm == FakeResponse.content
    url, payload, headers = client.calls[0]
    assert url.endswith("/api/v1/tts/inference")
    assert headers["X-API-Key-ID"] == "test-key"
    assert payload["model"] == "timbre-v3.0"
    assert payload["language"] == "kn-IN"
    assert payload["voice"] == "Shivani"
    assert payload["audio_config"] == {
        "sample_rate": 16000,
        "num_channels": 1,
        "sample_width": 2,
        "encoding": "linear_pcm",
        "container": "raw",
    }


def test_wav_header_is_stripped_for_the_browser_player():
    body = b"\x02\x00" * 16
    wav = (
        b"RIFF"
        + struct.pack("<I", 36 + len(body))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + b"\x01\x00\x01\x00"
        + struct.pack("<II", 16000, 32000)
        + b"\x02\x00\x10\x00"
        + b"data"
        + struct.pack("<I", len(body))
        + body
    )
    assert pcm_from_wav(wav) == body
    assert pcm_from_wav(body) == body


def test_stt_handshake_carries_language_model_vad_and_keyterms():
    stream = GnaniSTTStream(
        language="kn-IN",
        on_partial=_ignore,
        on_final=_ignore,
        on_error=_ignore,
        config=_settings(),
    )
    headers = stream.headers()

    assert headers["x-api-key-id"] == "test-key"
    assert headers["language_code"] == "kn-IN"
    assert headers["model"] == "prisma-v3.0"
    assert headers["x-sample-rate"] == "16000"
    assert headers["x-min-silence-ms"] == "700"
    assert "keyterms" in headers and "NegoAI" in headers["keyterms"]


def test_audio_is_rechunked_into_1024_byte_frames():
    stream = GnaniSTTStream(
        language="en-IN",
        on_partial=_ignore,
        on_final=_ignore,
        on_error=_ignore,
        config=_settings(),
    )
    sent: list[bytes] = []

    class FakeSocket:
        async def send(self, frame: bytes) -> None:
            sent.append(frame)

    stream._ws = FakeSocket()  # type: ignore[assignment]

    async def scenario() -> None:
        await stream.send_audio(b"a" * (STT_FRAME_BYTES + 500))
        await stream.send_audio(b"b" * 600)

    asyncio.run(scenario())
    assert [len(frame) for frame in sent] == [STT_FRAME_BYTES, STT_FRAME_BYTES]


async def _ignore(_text: str) -> None:
    return None

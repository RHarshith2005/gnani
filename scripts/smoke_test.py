"""One Kannada STT call and one Kannada TTS call against the real APIs.

    python scripts/smoke_test.py

Requires GNANI_API_KEY (or GNANI_KEY_ID) in the environment or api/.env.
The STT leg streams a synthetic tone — it proves auth and the socket, not
recognition quality. TTS output is written next to this script as out.wav.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / "api" / ".env")
except Exception:
    pass

import httpx

STT_URL = os.environ.get("GNANI_STT_URL", "wss://api.vachana.ai/stt/v3/stream")
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
KEY = os.environ.get("GNANI_KEY_ID") or os.environ.get("GNANI_API_KEY", "")
LANG = "kn-IN"
VOICE = os.environ.get("GNANI_VOICE_KN", "Nalini")


def write_wav(path: Path, pcm: bytes, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)


async def tts_call() -> bytes | None:
    text = "ನಮಸ್ಕಾರ, ಇದು ನೆಗೋಎಐ ಧ್ವನಿ ಪರೀಕ್ಷೆ."
    payload = {
        "text": text,
        "language": LANG,
        "voice": VOICE,
        "model": os.environ.get("GNANI_TTS_MODEL", "timbre-v2.5"),
        "sample_rate": 16000,
        "encoding": "pcm_s16le",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            TTS_URL,
            json=payload,
            headers={"X-API-Key-ID": KEY, "Content-Type": "application/json"},
        )
        print(f"TTS HTTP {response.status_code} ({response.headers.get('content-type')})")
        if response.status_code >= 400:
            print(response.text[:400])
            return None
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("audio/") or content_type == "application/octet-stream":
            return response.content
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.content
        audio = data.get("audio") or data.get("audio_base64") or data.get("pcm")
        return base64.b64decode(audio) if isinstance(audio, str) else None


async def stt_call() -> None:
    import websockets

    config = {
        "type": "config",
        "language": LANG,
        "encoding": "pcm_s16le",
        "sample_rate": 16000,
        "channels": 1,
    }
    async with websockets.connect(
        STT_URL, additional_headers={"X-API-Key-ID": KEY}, max_size=2**22
    ) as socket:
        await socket.send(json.dumps(config))
        # 0.5 s of a quiet 440 Hz tone, 1024-byte frames as the docs require.
        import math
        import struct

        frames = []
        for index in range(8000):
            sample = int(1200 * math.sin(2 * math.pi * 440 * index / 16000))
            frames.append(struct.pack("<h", sample))
        pcm = b"".join(frames)
        for offset in range(0, len(pcm), 1024):
            await socket.send(pcm[offset : offset + 1024])
        print("STT frames sent; waiting up to 6 s for any server event…")
        try:
            message = await asyncio.wait_for(socket.recv(), timeout=6)
            print("STT event:", str(message)[:300])
        except asyncio.TimeoutError:
            print("STT connected and accepted frames (no transcript for a tone, as expected).")


async def main() -> int:
    if not KEY:
        print("GNANI_API_KEY / GNANI_KEY_ID is not set — nothing to smoke-test.")
        print("The app still runs: scripted agent + browser voice.")
        return 2
    print(f"Using language {LANG} and voice {VOICE}")
    pcm = await tts_call()
    if pcm:
        out = ROOT / "out.wav"
        write_wav(out, pcm)
        print(f"Saved {len(pcm)} bytes of PCM to {out}")
    else:
        print("TTS returned no audio; check the model/voice names on your account.")
    await stt_call()
    return 0 if pcm else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

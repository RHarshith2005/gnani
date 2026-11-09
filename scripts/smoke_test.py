"""Live Gnani roundtrip: synthesize with Timbre, transcribe with Prisma.

    python scripts/smoke_test.py

Reads GNANI_API_KEY from ``api/.env`` or the environment and exercises the
same clients the app uses (``GnaniTTSService`` / ``GnaniSTTStream``), in
Kannada, Hindi and English. Saved audio: ``out_kn.wav``, ``out_hi.wav``,
``out_en.wav``. Exits non-zero if any language returns no audio or no
transcript.
"""

from __future__ import annotations

import asyncio
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / "api" / ".env")
except Exception:
    pass

from api.config import Settings  # noqa: E402
from api.speech.gnani import GnaniSTTStream, GnaniTTSService  # noqa: E402

TEXTS = {
    "kn-IN": "ನಮಸ್ಕಾರ! ಇದು ನೆಗೋಎಐ ಧ್ವನಿ ಪರೀಕ್ಷೆ. ನಮಗೆ ವಾರಕ್ಕೆ ಮೂರು ನೂರು ಅರವತ್ತು ನೀರಿನ ಕ್ಯಾನ್ ಬೇಕು.",
    "hi-IN": "नमस्ते! यह नेगोएआई की आवाज़ परीक्षा है। हमें हर हफ्ते तीन सौ साठ पानी के कैन चाहिए।",
    "en-IN": "Hello! This is the NegoAI voice test. We need three hundred sixty water cans every week.",
}
CODE = {"kn-IN": "kn", "hi-IN": "hi", "en-IN": "en"}


def write_wav(path: Path, pcm: bytes, rate: int) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)


async def transcribe(pcm: bytes, language: str, config: Settings) -> str:
    finals: list[str] = []
    errors: list[str] = []

    async def on_partial(text: str) -> None:
        print(f"   partial: {text}")

    async def on_final(text: str) -> None:
        finals.append(text)

    async def on_error(message: str) -> None:
        errors.append(message)

    stream = GnaniSTTStream(
        language=language,
        on_partial=on_partial,
        on_final=on_final,
        on_error=on_error,
        config=config,
    )
    if not await stream.start():
        print(f"   STT did not connect: {errors[-1] if errors else 'unknown error'}")
        return ""
    try:
        # Real-time cadence: 1,024 bytes is 32 ms at 16 kHz.
        for offset in range(0, len(pcm), 1024):
            await stream.send_audio(pcm[offset : offset + 1024])
            await asyncio.sleep(0.032)
        await stream.send_audio(b"\x00" * 1024 * 40)  # silence closes the VAD segment
        for _ in range(200):
            if finals or errors:
                break
            await asyncio.sleep(0.05)
    finally:
        await stream.close()
    if errors and not finals:
        print(f"   STT error: {errors[-1]}")
    return " ".join(finals)


async def main() -> int:
    config = Settings()
    if not config.has_gnani:
        print("GNANI_API_KEY is not set — add it to api/.env or the environment.")
        return 2
    print(
        f"model={config.gnani_stt_model} / {config.gnani_tts_model} "
        f"rate={config.gnani_sample_rate}"
    )
    tts = GnaniTTSService(config)
    failures = 0
    try:
        for language, text in TEXTS.items():
            print(f"\n[{language}] {text}")
            started = time.monotonic()
            pcm = await tts.synthesize(text, language)
            if not pcm:
                print("   TTS returned no audio")
                failures += 1
                continue
            print(
                f"   TTS {len(pcm)} bytes in {int((time.monotonic() - started) * 1000)} ms"
            )
            out = ROOT / f"out_{CODE[language]}.wav"
            write_wav(out, pcm, config.gnani_sample_rate)
            transcript = await transcribe(pcm, language, config)
            if not transcript:
                failures += 1
                continue
            print(f"   STT: {transcript}")
    finally:
        await tts.aclose()
    print("\nPASS" if failures == 0 else f"\nFAIL ({failures} language(s))")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

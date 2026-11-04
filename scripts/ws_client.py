"""Drive the voice gateway from a terminal.

    python scripts/ws_client.py --mode guided --lang kn-IN
    python scripts/ws_client.py --wav kannada.wav --lang kn-IN
    python scripts/ws_client.py --text "three water cans every week"

Guided mode prints every server event until the admin summary arrives. With
``--wav`` the file is streamed as 16 kHz mono PCM16 in 1024-byte frames; with
``--text`` the transcript is sent as if the resident had spoken it. Both prove
the same contract the browser uses: one socket, one brain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / "api" / ".env")
except Exception:
    pass

import websockets  # noqa: E402

# Windows consoles default to cp1252, which cannot print Kannada or Hindi.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_wav(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit("Expected mono 16-bit PCM wav.")
        return handle.readframes(handle.getnframes()), handle.getframerate()


async def stream_wav(socket, path: Path) -> None:
    pcm, rate = read_wav(path)
    print(f"streaming {len(pcm)} bytes from {path.name} at {rate} Hz")
    frame = int(rate * 0.064) * 2  # ~64 ms per send
    for offset in range(0, len(pcm), frame):
        await socket.send(pcm[offset : offset + frame])
        await asyncio.sleep(0.064)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws/voice")
    parser.add_argument("--mode", default="guided", choices=("live", "guided"))
    parser.add_argument("--lang", default="kn-IN")
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    seen = 0
    done = False
    started = time.monotonic()

    async with websockets.connect(args.url, max_size=2**24) as socket:
        await socket.send(json.dumps({"type": "hello", "mode": args.mode, "language": args.lang}))

        async def receive() -> None:
            nonlocal seen, done
            async for message in socket:
                if isinstance(message, bytes):
                    continue
                try:
                    event = json.loads(message)
                except json.JSONDecodeError:
                    continue
                seen += 1
                kind = event.get("type")
                if kind == "agent":
                    label = "vendor-audio" if event.get("role") == "vendor" else "agent"
                    print(f"{label:9} [{event.get('lang')}] {event.get('text')}")
                    if event.get("subtitle") and event["subtitle"] != event.get("text"):
                        print(f"          ({event['subtitle']})")
                elif kind == "transcript":
                    print(f"{event.get('role', 'user'):9} {event.get('text')}")
                elif kind == "vendor":
                    print(f"vendor    {event.get('vendor_name')}: {event.get('line')}")
                elif kind == "offers":
                    best = event.get("best") or {}
                    print(f"offers    best={best.get('vendor_id')} price={best.get('unit_price')}")
                elif kind == "admin":
                    print(
                        f"admin     best={(event.get('best') or {}).get('vendor_name')} "
                        f"savings={event.get('savings')}"
                    )
                    done = True
                    return
                elif kind in ("notice", "error"):
                    print(f"{kind:9} {event.get('text') or event.get('message')}")
                elif kind == "phase":
                    print(f"phase     {event.get('phase')}")

        receiver = asyncio.create_task(receive())

        if args.wav:
            await stream_wav(socket, args.wav)
        if args.text:
            await asyncio.sleep(1.0)
            await socket.send(json.dumps({"type": "text", "text": args.text}))

        try:
            await asyncio.wait_for(receiver, timeout=args.timeout)
        except asyncio.TimeoutError:
            print(f"\nTimed out after {args.timeout}s with {seen} events.")
            return 1
        finally:
            receiver.cancel()

    elapsed = time.monotonic() - started
    print(f"\n{seen} events in {elapsed:.1f}s — admin summary received: {done}")
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Gnani Prisma (STT) and Timbre (TTS) clients.

Wire format verified against docs.gnani.ai and a live key on 9 Nov 2026:
  * STT  wss://api.vachana.ai/stt/v3/stream
         Session config is sent as WebSocket handshake headers
         (``language_code``, ``model``, ``x-sample-rate``, VAD tuning,
         ``topic``/``keyterms``); audio is raw PCM16 in 1,024-byte frames.
  * TTS  POST https://api.vachana.ai/api/v1/tts/inference
         ``audio_config.container = "raw"`` returns headerless 16-bit PCM at
         the requested sample rate, which is what the browser player expects.

Without keys everything degrades to browser speech.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import struct
from typing import Awaitable, Callable, Optional

import httpx

from ..config import VENDOR_VOICES, VOICES, Settings, settings as default_settings

log = logging.getLogger("negoai.gnani")

TTS_HTTP_URL = "https://api.vachana.ai/api/v1/tts/inference"

#: Prisma requires exactly 1,024 bytes (512 samples) per binary frame.
STT_FRAME_BYTES = 1024

#: Characters of TTS already paid for in this process. The guard is deliberately
#: simple: one loop, one counter, and a hard stop that falls back to text.
_GLOBAL_TTS_CHARS = 0


class TTSCreditGuard:
    """Per-session and global character caps before falling back to text-only."""

    def __init__(self, *, budget: int, session_cap: int) -> None:
        self.budget = max(0, int(budget))
        self.session_cap = max(0, int(session_cap))
        self.spent = 0
        self.exhausted = False

    def allow(self, characters: int) -> bool:
        global _GLOBAL_TTS_CHARS
        if self.exhausted or characters <= 0:
            return False
        if self.spent + characters > self.session_cap:
            self.exhausted = True
            return False
        if _GLOBAL_TTS_CHARS + characters > self.budget:
            self.exhausted = True
            return False
        self.spent += characters
        _GLOBAL_TTS_CHARS += characters
        return True


def pcm_from_wav(data: bytes) -> bytes:
    """Return raw PCM16 from a RIFF/WAV payload (or the input unchanged)."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        start = offset + 8
        if chunk_id == b"data":
            end = start + size
            if size == 0 or end > len(data):
                end = len(data)
            return data[start:end]
        offset = start + size + (size % 2)
    return data


class GnaniTTSService:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or default_settings
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict[tuple[str, str, str], bytes] = {}

    @property
    def enabled(self) -> bool:
        return self.config.has_gnani

    def voice_for(self, language: str) -> str:
        return VOICES.get(language) or VOICES.get("en-IN") or "Shivani"

    def distinct_voice(self, language: str, preferred: str) -> str:
        """Keep a vendor audibly different from NegoAI when a voice collides."""
        default = self.voice_for(language)
        if preferred and preferred != default:
            return preferred
        for candidate in VENDOR_VOICES.get(language) or list(VOICES.values()):
            if candidate != default:
                return candidate
        return preferred or default

    def build_payload(
        self, text: str, language: str = "en-IN", *, voice: Optional[str] = None
    ) -> dict:
        """The documented request body; kept public so tests can pin the contract."""
        return {
            "text": text,
            "voice": voice or self.voice_for(language),
            "model": self.config.gnani_tts_model,
            "language": language,
            "speed": self.config.gnani_tts_speed,
            "audio_config": {
                "sample_rate": self.config.gnani_sample_rate,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "raw",
            },
        }

    async def synthesize(
        self, text: str, language: str = "en-IN", *, voice: Optional[str] = None
    ) -> Optional[bytes]:
        """Return raw PCM16 at ``gnani_sample_rate`` (mono) or ``None``."""
        if not self.enabled or not text:
            return None
        payload = self.build_payload(text, language, voice=voice)
        key = (text, language, payload["voice"])
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        headers = {
            "X-API-Key-ID": self.config.gnani_key_id,
            "Content-Type": "application/json",
        }
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        try:
            response = await self._client.post(TTS_HTTP_URL, json=payload, headers=headers)
            response.raise_for_status()
            ctype = response.headers.get("content-type", "")
            if ctype.startswith("audio/") or ctype == "application/octet-stream":
                pcm = pcm_from_wav(response.content)
                self._remember(key, pcm)
                return pcm
            # Defensive: a deployment may wrap the audio in JSON.
            try:
                data = response.json()
            except json.JSONDecodeError:
                pcm = pcm_from_wav(response.content)
                self._remember(key, pcm)
                return pcm
            audio = data.get("audio") or data.get("audio_base64") or data.get("pcm")
            if isinstance(audio, str):
                try:
                    pcm = pcm_from_wav(base64.b64decode(audio))
                except Exception:
                    return None
                self._remember(key, pcm)
                return pcm
            url = data.get("audio_url")
            if isinstance(url, str):
                audio_response = await self._client.get(url)
                audio_response.raise_for_status()
                pcm = pcm_from_wav(audio_response.content)
                self._remember(key, pcm)
                return pcm
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else ""
            log.warning("Timbre TTS HTTP %s: %s", exc.response.status_code, detail)
            return None
        except Exception as exc:
            log.warning("Timbre TTS failed (%s); browser speech will fill in", exc)
            return None
        return None

    def _remember(self, key: tuple[str, str, str], audio: bytes) -> None:
        """Cache fixed lines (disclosure, greetings) to save latency and credits."""
        if not audio:
            return
        if len(self._cache) >= 128:
            self._cache.clear()
        self._cache[key] = audio

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class GnaniSTTStream:
    """Prisma realtime STT over one WebSocket.

    Prisma takes language and VAD settings at handshake time, so switching
    language means reconnecting (``VoiceSession._restart_stt``). Binary audio is
    re-chunked to the required 1,024-byte frames before it is sent.
    """

    def __init__(
        self,
        *,
        language: str,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
        config: Settings | None = None,
    ) -> None:
        self.config = config or default_settings
        self.language = language
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self._ws = None
        self._reader: Optional[asyncio.Task] = None
        self._closed = False
        self._error_reported = False
        self._buffer = bytearray()
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self.config.has_gnani

    @property
    def alive(self) -> bool:
        """False once Prisma closes the socket or the read loop dies."""
        return (
            self._ws is not None
            and not self._closed
            and self._reader is not None
            and not self._reader.done()
        )

    def headers(self) -> dict[str, str]:
        """Handshake config, exactly as docs.gnani.ai describes (public for tests)."""
        headers = {
            "x-api-key-id": self.config.gnani_key_id,
            "language_code": self.language,
            "x-sample-rate": str(self.config.gnani_sample_rate),
            "x-vad-threshold": f"{self.config.gnani_vad_threshold:g}",
            "x-min-silence-ms": str(self.config.gnani_min_silence_ms),
            "x-min-speech-ms": str(self.config.gnani_min_speech_ms),
        }
        if self.config.gnani_stt_model:
            headers["model"] = self.config.gnani_stt_model
        if self.config.gnani_stt_topic:
            headers["topic"] = self.config.gnani_stt_topic
        if self.config.gnani_stt_keyterms:
            # Non-ASCII domain words must be JSON-escaped in a header.
            headers["keyterms"] = json.dumps(
                self.config.gnani_stt_keyterms, ensure_ascii=True
            )
        return headers

    async def start(self) -> bool:
        if not self.enabled:
            return False
        try:
            import websockets

            self._ws = await websockets.connect(
                self.config.gnani_stt_url,
                additional_headers=self.headers(),
                max_size=4 * 1024 * 1024,
                open_timeout=15,
            )
            self._reader = asyncio.create_task(self._read_loop())
            return True
        except Exception as exc:
            log.warning("Prisma STT unavailable (%s); browser STT will be used", exc)
            await self._report_error(str(exc))
            return False

    async def _report_error(self, message: str) -> None:
        if self._error_reported:
            return
        self._error_reported = True
        await self.on_error(message)

    async def _mark_failed(self, message: str) -> None:
        if self._closed:
            return
        self._closed = True
        self._buffer.clear()
        log.warning("Prisma STT stream failed: %s", message)
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        await self._report_error(message)

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    continue
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                kind = data.get("type")
                if kind == "error":
                    text = str(data.get("message") or "Prisma STT error")
                    log.warning("Prisma STT error: %s", text)
                    await self._mark_failed(text)
                    return
                text = data.get("text") or data.get("transcript")
                if not isinstance(text, str) or not text.strip():
                    continue
                is_final = data.get("is_final")
                if is_final is False or kind == "partial":
                    await self.on_partial(text.strip())
                else:
                    # Prisma emits one final transcript per VAD segment.
                    await self.on_final(text.strip())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                await self._mark_failed(str(exc))
        else:
            if not self._closed:
                await self._mark_failed("Prisma STT connection closed")

    async def send_audio(self, pcm: bytes) -> bool:
        if self._ws is None or self._closed or not pcm:
            return False
        error = None
        async with self._lock:
            ws = self._ws
            if ws is None or self._closed:
                return False
            self._buffer.extend(pcm)
            frames: list[bytes] = []
            while len(self._buffer) >= STT_FRAME_BYTES:
                frames.append(bytes(self._buffer[:STT_FRAME_BYTES]))
                del self._buffer[:STT_FRAME_BYTES]
            try:
                for frame in frames:
                    await ws.send(frame)
            except Exception as exc:
                error = str(exc)
        if error is not None:
            await self._mark_failed(error)
            return False
        return True

    async def close(self) -> None:
        self._closed = True
        self._buffer.clear()
        if self._reader is not None:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

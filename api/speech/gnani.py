"""Gnani Prisma (STT) and Timbre (TTS) clients.

Endpoints follow docs.gnani.ai as verified in the blueprint:
  * STT  wss://api.vachana.ai/stt/v3/stream       (raw PCM, 16 kHz, 1024-byte frames)
  * TTS  https://api.vachana.ai/api/v1/tts/inference
  * auth header X-API-Key-ID

The TTS wire format is the one to re-check first on the challenge account;
``synthesize`` accepts plain PCM, base64 or an audio URL so a schema change does
not break the demo. Without keys everything degrades to browser speech.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Awaitable, Callable, Optional

import httpx

from ..config import VOICES, Settings, settings as default_settings

log = logging.getLogger("negoai.gnani")

TTS_HTTP_URL = "https://api.vachana.ai/api/v1/tts/inference"

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


class GnaniTTSService:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or default_settings
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict[tuple[str, str, str], bytes] = {}

    @property
    def enabled(self) -> bool:
        return self.config.has_gnani

    def voice_for(self, language: str) -> str:
        return VOICES.get(language) or VOICES.get("en-IN", "Deepak")

    def distinct_voice(self, language: str, preferred: str) -> str:
        """Keep the vendor audibly different from NegoAI when a name collides."""
        default = self.voice_for(language)
        if preferred and preferred != default:
            return preferred
        for candidate in VOICES.values():
            if candidate != default:
                return candidate
        return preferred or default

    async def synthesize(
        self, text: str, language: str = "en-IN", *, voice: Optional[str] = None
    ) -> Optional[bytes]:
        """Return raw PCM16 (16 kHz mono) or ``None`` when unavailable."""
        if not self.enabled or not text:
            return None
        voice = voice or self.voice_for(language)
        key = (text, language, voice)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        payload = {
            "text": text,
            "language": language,
            "voice": voice,
            "model": self.config.gnani_tts_model,
            "sample_rate": self.config.gnani_sample_rate,
            "encoding": "pcm_s16le",
        }
        headers = {
            "X-API-Key-ID": self.config.gnani_key_id,
            "Content-Type": "application/json",
        }
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        try:
            response = await self._client.post(TTS_HTTP_URL, json=payload, headers=headers)
            response.raise_for_status()
            ctype = response.headers.get("content-type", "")
            if ctype.startswith("audio/") or ctype == "application/octet-stream":
                self._remember(key, response.content)
                return response.content
            # Some deployments wrap audio in JSON.
            try:
                data = response.json()
            except json.JSONDecodeError:
                return response.content
            audio = data.get("audio") or data.get("audio_base64") or data.get("pcm")
            if isinstance(audio, str):
                try:
                    pcm = base64.b64decode(audio)
                except Exception:
                    return None
                self._remember(key, pcm)
                return pcm
            url = data.get("audio_url")
            if isinstance(url, str):
                audio_response = await self._client.get(url)
                audio_response.raise_for_status()
                self._remember(key, audio_response.content)
                return audio_response.content
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
    """Thin streaming wrapper around Prisma realtime STT.

    The exact event names are not confirmed in the public docs we could reach,
    so incoming frames are mapped defensively. Any failure raises through
    ``on_error`` and the UI falls back to browser recognition.
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
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self.config.has_gnani

    async def start(self) -> bool:
        if not self.enabled:
            return False
        try:
            import websockets

            self._ws = await websockets.connect(
                self.config.gnani_stt_url,
                additional_headers={"X-API-Key-ID": self.config.gnani_key_id},
                max_size=4 * 1024 * 1024,
            )
            await self._ws.send(
                json.dumps(
                    {
                        "type": "config",
                        "language": self.language,
                        "encoding": "pcm_s16le",
                        "sample_rate": self.config.gnani_sample_rate,
                        "channels": 1,
                    }
                )
            )
            self._reader = asyncio.create_task(self._read_loop())
            return True
        except Exception as exc:
            log.warning("Prisma STT unavailable (%s); browser STT will be used", exc)
            await self.on_error(str(exc))
            return False

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
                text = data.get("transcript") or data.get("text") or data.get("final")
                if not isinstance(text, str) or not text.strip():
                    continue
                is_final = bool(data.get("is_final") or data.get("final") or data.get("type") == "final")
                if is_final:
                    await self.on_final(text.strip())
                else:
                    await self.on_partial(text.strip())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                log.warning("Prisma STT read loop ended: %s", exc)

    async def send_audio(self, pcm: bytes) -> None:
        if self._ws is None or self._closed or not pcm:
            return
        async with self._lock:
            try:
                await self._ws.send(pcm)
            except Exception as exc:
                log.debug("STT send failed: %s", exc)

    async def close(self) -> None:
        self._closed = True
        if self._reader is not None:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

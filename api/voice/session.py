"""One brain, many channels.

Everything the browser sees flows through :class:`VoiceSession`: mic audio,
typed text and the guided demo all land in the same intake + negotiation
pipeline. The session emits UI events and (when keys exist) Timbre audio; the
browser never sees a key, a floor price or the committee ceiling.
"""

from __future__ import annotations

import asyncio
import base64
import difflib
import logging
import re
import time
import unicodedata
from collections import deque
from typing import Any, Awaitable, Callable, Optional

from .. import db
from ..agents.composer import ConversationContext, agent_line, vendor_line
from ..agents.guard import numbers_in
from ..agents.intake import IntakeState
from ..agents.llm import LLMClient
from ..agents.prompts import negotiator_system
from ..agents.summary import build_admin_summary
from ..config import Settings, settings as default_settings
from ..negotiation.engine import (
    ASK_QUOTE,
    COUNTER,
    ESCALATE_ACTION,
    MENTION_COMPETITOR,
    WALK_AWAY_ACTION,
    NegotiationEngine,
    Offer,
)
from ..negotiation.personas import PERSONAS, SimVendor
from ..speech.gnani import GnaniSTTStream, GnaniTTSService, TTSCreditGuard
from ..speech.numbers import normalise, spell_number
from .pcm import b64decode_pcm, b64encode_pcm, rms

log = logging.getLogger("negoai.session")

Send = Callable[[dict[str, Any]], Awaitable[None]]

COMMUNITY = {"id": db.COMMUNITY_ID, "name": "Green Residency", "households": 120}
#: Blueprint demo numbers: 120 households x 3 cans, aggregated after confirm.
AGGREGATE_QTY = 360
TARGET_PRICE = 18
MAX_PRICE = 20
MAX_ROUNDS = 3
PLAYBACK_TAIL_SECONDS = 0.3
AGENT_GATE_TAIL_SECONDS = 0.4

GREETING = {
    "kn-IN": (
        "ನಮಸ್ಕಾರ! ನಾನು ನೆಗೋಎಐ, ಒಬ್ಬ ಎಐ ಸಹಾಯಕ. ಈ ವಾರ ನಿಮಗೆ ಏನು ಬೇಕು — ನೀರಿನ ಕ್ಯಾನ್, "
        "ಹಾಲು ಅಥವಾ ತರಕಾರಿ?",
        "Hello! I am NegoAI, an AI assistant. What do you need this week — water cans, "
        "milk or vegetables?",
    ),
    "hi-IN": (
        "नमस्ते! मैं NegoAI हूँ, एक एआई सहायक। इस हफ्ते आपको क्या चाहिए — पानी के कैन, "
        "दूध या सब्ज़ी?",
        "Hello! I am NegoAI, an AI assistant. What do you need this week — water cans, "
        "milk or vegetables?",
    ),
    "en-IN": (
        "Hello! I am NegoAI, an AI assistant. What does your society need this week — "
        "water cans, milk or vegetables?",
        "Hello! I am NegoAI, an AI assistant. What does your society need this week — "
        "water cans, milk or vegetables?",
    ),
}

DEMO_SCRIPT = {
    "kn-IN": {
        "demand": ("ನನಗೆ ವಾರಕ್ಕೆ ಮೂರು ನೀರಿನ ಕ್ಯಾನ್ ಬೇಕು", "I need three water cans every week."),
        "confirm": ("ಹೌದು, ಸರಿ", "Yes, correct."),
        "day": ("ಶನಿವಾರ ಡೆಲಿವರಿ ಮಾಡಿ", "Deliver on Saturday."),
        "flat": ("ಬಿ-402", "B-402."),
    },
    "hi-IN": {
        "demand": ("मुझे हर हफ्ते तीन पानी के कैन चाहिए", "I need three water cans every week."),
        "confirm": ("हाँ, सही है", "Yes, correct."),
        "day": ("शनिवार को डिलीवरी कीजिए", "Deliver on Saturday."),
        "flat": ("बी-402", "B-402."),
    },
    "en-IN": {
        "demand": ("Three water cans every week", "I need three water cans every week."),
        "confirm": ("Yes, correct", "Yes, correct."),
        "day": ("Saturday delivery, please", "Deliver on Saturday."),
        "flat": ("B-402", "B-402."),
    },
}

APPROVE_WORDS = ("approve", "approved", "yes", "ಹೌದು", "हाँ", "स्वीकार")

LANGUAGE_NAMES = {"kn-IN": "Kannada", "hi-IN": "Hindi", "en-IN": "English"}
_SCRIPTS = {
    "kn-IN": re.compile(r"[\u0C80-\u0CFF]"),
    "hi-IN": re.compile(r"[\u0900-\u097F]"),
}


def language_mismatch(text: str, language: str) -> bool:
    """True when a transcript is in another script than the pinned session.

    A noisy room contains other talkers; Prisma returns their words even though
    the session language is fixed. Kannada and Hindi are disjoint scripts, so a
    clear mismatch is safe to reject before it reaches intake. Code-mixing with
    Latin words, numbers and the active script is still accepted.
    """
    has_kn = bool(_SCRIPTS["kn-IN"].search(text))
    has_hi = bool(_SCRIPTS["hi-IN"].search(text))
    if language == "kn-IN":
        return has_hi and not has_kn
    if language == "hi-IN":
        return has_kn and not has_hi
    if language == "en-IN":
        return has_kn or has_hi
    return False


class VoiceSession:
    def __init__(
        self,
        send: Send,
        *,
        mode: str = "live",
        language: str = "kn-IN",
        config: Settings | None = None,
    ) -> None:
        self.send = send
        self.config = config or default_settings
        self.mode = mode if mode in ("live", "guided") else "live"
        self.language = normalise(language)
        self.phase = "intake"
        self.intake = IntakeState(language=self.language)
        self.ctx = ConversationContext(
            community=COMMUNITY["name"],
            households=COMMUNITY["households"],
            product="water can",
            unit="can",
            qty=AGGREGATE_QTY,
        )
        self.engines: dict[str, NegotiationEngine] = {}
        self.sims: dict[str, SimVendor] = {}
        self.offers: dict[str, Offer] = {}
        self.negotiation_id: Optional[str] = None
        self.tasks: set[asyncio.Task] = set()
        self.llm = LLMClient(self.config)
        self.tts = GnaniTTSService(self.config)
        self.credits = TTSCreditGuard(
            budget=self.config.credit_budget,
            session_cap=self.config.session_tts_chars,
        )
        self.stt: Optional[GnaniSTTStream] = None
        self._stt_lock = asyncio.Lock()
        self._last_stt_retry = 0.0
        self.pace = max(0.01, self.config.demo_pace) if self.mode == "guided" else 1.0
        self._last_level = 0.0
        self._closed = False
        self._turns = 0
        self._speak_lock = asyncio.Lock()
        self._utterance_id = 0
        self._epoch = 0
        self._active_playback: tuple[int, int, asyncio.Event] | None = None
        self._synthesis_task: asyncio.Task | None = None
        self.agent_speaking = False
        self._interrupt_event = asyncio.Event()
        self._resident_ready = asyncio.Event()
        self._input_lock = asyncio.Lock()
        self._recent_agent_lines: deque[str] = deque(maxlen=3)
        self._last_negotiation_notice = 0.0
        # Playback controls (Prompt 10). The gate is set while running.
        self.paused = asyncio.Event()
        self.paused.set()
        self._credit_notice = False
        self._skip_requested = False
        self.negotiation_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ plumbing
    async def emit(self, payload: dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            await self.send(payload)
        except Exception as exc:  # socket gone mid-turn
            log.debug("emit failed: %s", exc)

    def _spawn(self, coro: Awaitable[Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)  # type: ignore[arg-type]
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def configure(self, *, mode: str, language: str) -> None:
        self._epoch += 1
        self.agent_speaking = False
        if self._synthesis_task is not None and not self._synthesis_task.done():
            self._synthesis_task.cancel()
        if self._active_playback is not None:
            self._active_playback[2].set()
        self._interrupt_event.clear()
        self._resident_ready.clear()
        await self._cancel_tasks()
        self.mode = mode if mode in ("live", "guided") else "live"
        self.language = normalise(language)
        self.pace = max(0.01, self.config.demo_pace) if self.mode == "guided" else 1.0
        self.phase = "intake"
        self.intake = IntakeState(language=self.language)
        self.engines.clear()
        self.sims.clear()
        self.offers.clear()
        self.negotiation_id = None
        self._turns = 0
        await self._restart_stt()
        await self.emit(self.ready_payload())

    def ready_payload(self) -> dict[str, Any]:
        return {
            "type": "ready",
            "mode": self.mode,
            "language": self.language,
            "session_id": self.negotiation_id or f"session-{int(time.time() * 1000)}",
            "epoch": self._epoch,
            "community": COMMUNITY,
            "capabilities": self.config.as_public(),
            "languages": ["kn-IN", "hi-IN", "en-IN"],
        }

    async def start(self) -> None:
        await self.emit(self.ready_payload())
        if self.config.has_gnani:
            await self._restart_stt()
        else:
            await self.emit(
                {
                    "type": "notice",
                    "level": "info",
                    "text": (
                        "No Gnani key on this box: scripted agent sentences and browser "
                        "voice. Drop GNANI_API_KEY into api/.env to switch to Prisma + Timbre."
                    ),
                }
            )
        if self.mode == "guided":
            self._spawn(self.run_demo())
        else:
            self._spawn(self._greet())

    async def close(self) -> None:
        self._closed = True
        await self._cancel_tasks()
        if self.stt:
            await self.stt.close()
        await self.tts.aclose()
        await self.llm.aclose()

    async def _cancel_tasks(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        self.tasks.clear()
        await asyncio.sleep(0)

    async def _restart_stt(self) -> None:
        """Prisma fixes language and VAD at handshake, so a switch means reconnect."""
        if not self.config.has_gnani:
            return
        if self.stt is not None:
            await self.stt.close()
            self.stt = None
        stream = GnaniSTTStream(
            language=self.language,
            on_partial=self._on_partial,
            on_final=self._on_final_transcript,
            on_error=self._on_stt_error,
            config=self.config,
        )
        if await stream.start():
            self.stt = stream
        else:
            await self.emit(
                {
                    "type": "notice",
                    "level": "warn",
                    "text": "Prisma STT did not connect; using the browser recogniser.",
                }
            )

    # --------------------------------------------------------------------- speech
    def _speech_seconds(self, text: str) -> float:
        words = max(1, len(re.findall(r"\S+", text)))
        return max(0.7, min(5.0, words * 0.34))

    async def speak(
        self,
        text: str,
        subtitle: str = "",
        *,
        lang: Optional[str] = None,
        voice: Optional[str] = None,
        role: str = "agent",
    ) -> None:
        if not text:
            return
        request_epoch = self._epoch
        async with self._speak_lock:
            if request_epoch != self._epoch:
                return
            while True:
                await self._wait_if_paused()
                if self.phase == "negotiation" and self._interrupt_event.is_set():
                    await self._resident_ready.wait()
                    self._resident_ready.clear()
                    self._interrupt_event.clear()

                self._utterance_id += 1
                utterance_id = self._utterance_id
                epoch = self._epoch
                lang = normalise(lang or self.language)
                self.agent_speaking = True
                self._recent_agent_lines.append(self._normalise_line(text))
                playback_done = asyncio.Event()
                self._active_playback = (epoch, utterance_id, playback_done)
                self._synthesis_task = None
                use_gnani = self.tts.enabled and self.credits.allow(len(text))
                await self.emit({"type": "state", "orb": "thinking"})
                await self.emit(
                    {
                        "type": "agent",
                        "role": role,
                        "text": text,
                        "subtitle": subtitle or text,
                        "lang": lang,
                        "tts": "gnani" if use_gnani else "browser",
                        "utterance_id": utterance_id,
                        "epoch": epoch,
                    }
                )
                await self.emit({"type": "state", "orb": "speaking"})

                seconds = self._speech_seconds(text)
                try:
                    if use_gnani:
                        self._synthesis_task = asyncio.create_task(
                            self.tts.synthesize(text, lang, voice=voice)
                        )
                        try:
                            audio = await asyncio.shield(self._synthesis_task)
                        except asyncio.CancelledError:
                            if asyncio.current_task() and asyncio.current_task().cancelling():
                                raise
                            audio = None
                        if audio and epoch == self._epoch:
                            seconds = len(audio) / max(1, 2 * self.config.gnani_sample_rate)
                            await self.emit(
                                {
                                    "type": "audio",
                                    "pcm": b64encode_pcm(audio),
                                    "sampleRate": self.config.gnani_sample_rate,
                                    "utterance_id": utterance_id,
                                    "epoch": epoch,
                                }
                            )
                    elif self.tts.enabled and self.credits.exhausted and not self._credit_notice:
                        self._credit_notice = True
                        await self.emit(
                            {
                                "type": "notice",
                                "level": "warn",
                                "text": (
                                    "Voice credit budget reached — continuing in text with English "
                                    "subtitles. Every number still comes from the engine."
                                ),
                            }
                        )

                    timeout = seconds * 1.5 + 1.0
                    try:
                        await asyncio.wait_for(playback_done.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        log.warning("playback acknowledgement timed out for utterance %s", utterance_id)

                    interrupted = epoch != self._epoch
                    if not interrupted:
                        await asyncio.sleep(PLAYBACK_TAIL_SECONDS)
                        await asyncio.sleep(AGENT_GATE_TAIL_SECONDS - PLAYBACK_TAIL_SECONDS)
                    self.agent_speaking = False
                    if not interrupted:
                        await self.emit(
                            {"type": "state", "orb": "listening" if self.mode == "live" else "idle"}
                        )
                        return
                    if self.phase != "negotiation":
                        return
                except asyncio.CancelledError:
                    raise
                finally:
                    if self._synthesis_task is not None and self._synthesis_task.done():
                        self._synthesis_task = None
                    if self._active_playback == (epoch, utterance_id, playback_done):
                        self._active_playback = None
                    self.agent_speaking = False

    @staticmethod
    def _normalise_line(text: str) -> str:
        decomposed = unicodedata.normalize("NFKC", text).casefold()
        return " ".join(re.sub(r"[^\w\s]", " ", decomposed).split())

    def _is_agent_echo(self, text: str) -> bool:
        candidate = self._normalise_line(text)
        if not candidate:
            return False
        return any(
            candidate == line or difflib.SequenceMatcher(None, candidate, line).ratio() > 0.8
            for line in self._recent_agent_lines
        )

    async def playback_done(self, utterance_id: int, epoch: int) -> None:
        active = self._active_playback
        if active and active[:2] == (epoch, utterance_id) and epoch == self._epoch:
            active[2].set()

    async def _greet(self) -> None:
        spoken, subtitle = GREETING.get(self.language, GREETING["en-IN"])
        await self.speak(spoken, subtitle)
        if self.mode == "live":
            await self.emit({"type": "state", "orb": "listening"})

    async def _wait_if_paused(self) -> None:
        while not self.paused.is_set():
            await asyncio.sleep(0.05)

    async def _pauseable_sleep(self, seconds: float) -> None:
        """Sleep in small steps so pause and stop feel immediate."""
        remaining = max(0.0, seconds)
        while remaining > 0:
            await self._wait_if_paused()
            step = min(0.1, remaining)
            await asyncio.sleep(step)
            remaining -= step

    async def _resident(self, text: str, subtitle: str = "") -> None:
        await self.emit(
            {
                "type": "transcript",
                "role": "resident",
                "text": text,
                "subtitle": subtitle,
                "lang": self.language,
            }
        )
        await self.emit({"type": "state", "orb": "thinking"})
        reply = self.intake.handle(text)
        if reply.kind == "confirm":
            await self.emit(
                {"type": "confirm", "text": reply.say, "items": [reply.slots]}
            )
        else:
            await self.emit({"type": "confirm_clear"})
        await self.emit({"type": "demand", "slots": reply.slots})
        await self.speak(reply.say, reply.subtitle, lang=reply.slots.get("language"))
        if reply.done:
            db.save_demand(
                resident_id=None,
                community_id=COMMUNITY["id"],
                product=self.intake.product or "water can",
                qty=self.intake.qty or 3,
                frequency=self.intake.frequency,
                delivery_day=self.intake.delivery_day,
                language=self.language,
            )
            await self.emit(
                {
                    "type": "transcript",
                    "role": "system",
                    "text": (
                        f"Aggregated demand: {AGGREGATE_QTY} water cans / week across "
                        f"{COMMUNITY['households']} households. Starting vendor calls."
                    ),
                    "subtitle": "",
                    "lang": "en-IN",
                }
            )
            await self.speak(
                self._aggregate_line(),
                f"Your {self.intake.qty or 3} cans are confirmed. With your neighbours the "
                f"verified demand is {spell_number(AGGREGATE_QTY, 'en-IN')} water cans a week. "
                "I will call three suppliers now.",
            )
            await self.emit(
                {
                    "type": "demand_saved",
                    "product": self.intake.product or "water can",
                    "qty": self.intake.qty or 3,
                    "frequency": self.intake.frequency,
                    "delivery_day": self.intake.delivery_day,
                    "language": self.language,
                }
            )
            # Spawned so stop/skip controls still reach the socket.
            self.negotiation_task = self._spawn(self.run_negotiation())

    def _aggregate_line(self) -> str:
        qty_words = spell_number(AGGREGATE_QTY, self.language)
        if self.language == "kn-IN":
            return (
                f"ನಿಮ್ಮ ಮೂರು ಕ್ಯಾನ್ ದಾಖಲಾಗಿದೆ. ನೆರೆಹೊರೆಯವರೊಂದಿಗೆ ಸೇರಿಸಿ ವಾರಕ್ಕೆ "
                f"{qty_words} ಕ್ಯಾನ್ ದೃಢವಾಗಿದೆ. ಈಗ ಮೂರು ಸರಬರಾಜುದಾರರಿಗೆ ಕರೆ ಮಾಡುತ್ತೇನೆ."
            )
        if self.language == "hi-IN":
            return (
                f"आपके तीन कैन दर्ज हो गए। पड़ोसियों के साथ मिलाकर हफ्ते में {qty_words} कैन "
                "पक्के हैं। अब मैं तीन सप्लायरों को कॉल करता हूँ।"
            )
        return (
            f"Your three cans are noted. With your neighbours, the verified demand is "
            f"{qty_words} cans a week. I will call three suppliers now."
        )

    # --------------------------------------------------------------------- inputs
    async def handle_text(self, text: str, subtitle: str = "") -> None:
        text = (text or "").strip()
        if not text:
            return
        if self.phase in ("negotiation",):
            now = time.monotonic()
            if now - self._last_negotiation_notice >= 5.0:
                self._last_negotiation_notice = now
                await self.emit(
                    {"type": "notice", "level": "info", "text": "The supplier call is in progress."}
                )
            if self._interrupt_event.is_set():
                self._resident_ready.set()
            return
        if self.phase in ("approval", "done"):
            if any(word in text.lower() for word in APPROVE_WORDS):
                await self.approve("approved")
            else:
                await self.speak(
                    "The offer is with the committee. Tap Approve or Reject on the admin screen.",
                    "The offer is with the committee. Tap Approve or Reject on the admin screen.",
                )
            return
        async with self._input_lock:
            if self._is_agent_echo(text):
                log.info("Dropped agent echo transcript")
                return
            await self._resident(text, subtitle)

    async def _ensure_stt(self) -> None:
        """Reconnect Prisma if it closed while the page sat idle.

        Without this the mic goes silently deaf after a pause: sends to a dead
        socket are swallowed and the resident sees no transcript.
        """
        if not self.config.has_gnani:
            return
        if self.stt is not None and self.stt.alive:
            return
        async with self._stt_lock:
            if self.stt is not None and self.stt.alive:
                return
            now = time.monotonic()
            if now - self._last_stt_retry < 3.0:
                return
            self._last_stt_retry = now
            log.info("Reconnecting Prisma STT for %s", self.language)
            await self._restart_stt()

    async def handle_audio(self, data: bytes) -> None:
        if self.agent_speaking:
            return
        level = rms(data)
        now = time.monotonic()
        if now - self._last_level > 0.05:
            self._last_level = now
            await self.emit({"type": "level", "value": round(level, 3)})
        await self._ensure_stt()
        if self.stt is not None:
            await self.stt.send_audio(data)

    async def _on_partial(self, text: str) -> None:
        await self.emit({"type": "partial", "text": text})

    async def _on_final_transcript(self, text: str) -> None:
        await self.emit({"type": "partial", "text": ""})
        if self.agent_speaking or self._is_agent_echo(text):
            log.info("Dropped final transcript while agent is speaking or for echo")
            return
        if language_mismatch(text, self.language):
            name = LANGUAGE_NAMES.get(self.language, self.language)
            await self.emit(
                {
                    "type": "notice",
                    "level": "warn",
                    "text": (
                        f"That sounded like another language. This session is set to "
                        f"{name} — use the language chip, or repeat in {name}."
                    ),
                }
            )
            return
        await self.handle_text(text)

    async def _on_stt_error(self, message: str) -> None:
        await self.emit(
            {
                "type": "notice",
                "level": "warn",
                "text": f"Prisma STT error ({message}); use the text box or browser mic.",
            }
        )

    async def set_language(self, language: str) -> None:
        language = normalise(language)
        changed = language != self.language
        self.language = language
        self.intake.language = self.language
        self.ctx = ConversationContext(
            community=COMMUNITY["name"],
            households=COMMUNITY["households"],
            product=self.intake.product or "water can",
            unit="can",
            qty=AGGREGATE_QTY,
        )
        if changed:
            await self._restart_stt()

    async def barge_in(self) -> None:
        self._epoch += 1
        self.agent_speaking = False
        if self.phase == "negotiation":
            self._interrupt_event.set()
        else:
            self._interrupt_event.clear()
            self._resident_ready.clear()
        if self._synthesis_task is not None and not self._synthesis_task.done():
            self._synthesis_task.cancel()
        if self._active_playback is not None:
            self._active_playback[2].set()
        await self.emit({"type": "interrupt", "epoch": self._epoch})
        await self.emit({"type": "state", "orb": "listening"})

    async def pause(self) -> None:
        self.paused.clear()
        await self.emit({"type": "control", "action": "paused"})
        await self.emit(
            {"type": "notice", "level": "info", "text": "Paused — playback and turns are on hold."}
        )

    async def resume(self) -> None:
        self.paused.set()
        await self.emit({"type": "control", "action": "resumed"})

    async def stop(self) -> None:
        """Stop the negotiation without deleting its append-only audit trail."""
        self.paused.set()
        self._epoch += 1
        self.agent_speaking = False
        if self._synthesis_task is not None and not self._synthesis_task.done():
            self._synthesis_task.cancel()
        if self._active_playback is not None:
            self._active_playback[2].set()
        current = asyncio.current_task()
        for task in list(self.tasks):
            if task is not current:
                task.cancel()
                self.tasks.discard(task)
        self._skip_requested = False
        if self.negotiation_task is not None and not self.negotiation_task.done():
            self.negotiation_task.cancel()
        self.negotiation_task = None
        self.phase = "stopped"
        await self.emit({"type": "control", "action": "stopped"})
        await self.emit(
            {
                "type": "notice",
                "level": "info",
                "text": "Negotiation stopped. Completed events stay in the audit log.",
            }
        )

    async def skip(self) -> None:
        self._skip_requested = True
        await self.emit({"type": "control", "action": "skipped"})
        await self.emit(
            {"type": "notice", "level": "info", "text": "Skipping to the next supplier."}
        )

    async def approve(self, decision: str, note: str = "") -> None:
        negotiation_id = self.negotiation_id or f"adhoc-{int(time.time())}"
        decision = "approved" if decision == "approved" else "rejected"
        db.save_approval(negotiation_id=negotiation_id, decision=decision, note=note)
        db.add_event(
            negotiation_id,
            actor="admin",
            type="approval",
            payload={"decision": decision, "note": note},
        )
        self.phase = "done"
        await self.emit({"type": "approval", "decision": decision, "note": note, "by": "committee"})
        if decision == "approved":
            await self.speak(
                "Approved. The order goes out for this week and the society share is recorded.",
                "Approved. The order goes out for this week and the society share is recorded.",
            )
        else:
            await self.speak(
                "Rejected. I will keep the quotes on file for the next round.",
                "Rejected. I will keep the quotes on file for the next round.",
            )

    # ---------------------------------------------------------------- negotiation
    async def run_negotiation(self) -> None:
        try:
            await self._negotiate()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("negotiation failed")
            await self.emit({"type": "error", "message": f"Negotiation failed: {exc}"})

    def _negotiation_payload(self, engine: NegotiationEngine) -> dict[str, Any]:
        payload = {"type": "negotiation", **engine.public_state()}
        if self.negotiation_id:
            payload["negotiation_id"] = self.negotiation_id
        return payload

    async def _negotiate(self) -> None:
        self.phase = "negotiation"
        self.ctx = ConversationContext(
            community=COMMUNITY["name"],
            households=COMMUNITY["households"],
            product="water can",
            unit="can",
            qty=AGGREGATE_QTY,
        )
        self.engines = {}
        self.sims = {}
        self.offers = {}

        for persona in PERSONAS:
            self.engines[persona.vendor_id] = NegotiationEngine(
                product="water can",
                unit="can",
                demand_qty=AGGREGATE_QTY,
                target_price=TARGET_PRICE,
                max_price=MAX_PRICE,
                max_rounds=MAX_ROUNDS,
                competitor_quote=None,
                vendor_id=persona.vendor_id,
                vendor_name=persona.name,
                community=COMMUNITY["name"],
                households=COMMUNITY["households"],
            )
            self.sims[persona.vendor_id] = SimVendor(persona, demand_qty=AGGREGATE_QTY)

        self.negotiation_id = db.create_negotiation(
            community_id=COMMUNITY["id"],
            product="water can",
            qty=AGGREGATE_QTY,
            language=self.language,
            state=ASK_QUOTE,
            max_rounds=MAX_ROUNDS,
        )

        await self.emit({"type": "phase", "phase": "negotiation"})
        await self.emit(self._negotiation_payload(next(iter(self.engines.values()))))

        for persona in PERSONAS:
            if self._skip_requested:
                self._skip_requested = False
                continue
            engine = self.engines[persona.vendor_id]
            await self.emit(self._negotiation_payload(engine))
            directive = engine.start()
            await self.agent_turn(engine, directive)
            await self.vendor_quote_turn(engine)

            guard = 0
            while True:
                await self._wait_if_paused()
                if self._skip_requested:
                    self._skip_requested = False
                    await self.emit(
                        {
                            "type": "notice",
                            "level": "info",
                            "text": f"Skipped {engine.vendor_name}; moving on.",
                        }
                    )
                    break
                guard += 1
                if guard > 10:
                    break
                directive = engine.next_directive()
                if directive is None:
                    break
                await self.agent_turn(engine, directive)
                if directive.action in (ESCALATE_ACTION, WALK_AWAY_ACTION):
                    break
                if directive.action == MENTION_COMPETITOR:
                    continue
                if directive.action == "ask_delivery":
                    await self.vendor_delivery_turn(engine)
                    continue
                await self.vendor_quote_turn(engine, directive.price)

            await self.emit(self._negotiation_payload(engine))

        await self._finish_negotiation()

    async def _finish_negotiation(self) -> None:
        engines_summary = []
        for vendor_id, engine in self.engines.items():
            summary = engine.summary_numbers()
            summary["vendor_name"] = engine.vendor_name
            engines_summary.append(summary)
            db.update_negotiation(
                self.negotiation_id or "",
                state=engine.state,
                round_no=engine.round,
                first_quote=engine.first_quote.unit_price if engine.first_quote else None,
                best_quote=engine.best_eligible.unit_price if engine.best_eligible else None,
            )

        admin = build_admin_summary(
            community=COMMUNITY["name"],
            households=COMMUNITY["households"],
            product=self.ctx.product,
            unit=self.ctx.unit,
            qty=AGGREGATE_QTY,
            engines=engines_summary,
            language=self.language,
        )
        self.phase = "approval"
        await self.emit({"type": "phase", "phase": "approval"})
        await self.emit({"type": "admin", **admin})
        if self.negotiation_id:
            db.add_event(
                self.negotiation_id,
                actor="engine",
                type="admin_summary",
                payload={
                    "best_vendor": (admin.get("best") or {}).get("vendor_name"),
                    "savings": admin.get("savings"),
                    "total_qty": admin.get("total_qty"),
                },
            )

    async def agent_turn(self, engine: NegotiationEngine, directive) -> None:
        self._turns += 1
        spoken, subtitle = agent_line(
            directive, self.ctx, self.language, vendor_name=engine.vendor_name
        )
        # The LLM may rephrase, but only with numbers the engine already owns.
        if self.llm.enabled:
            spoken, subtitle = await self._llm_phrase(engine, directive, spoken, subtitle)

        if self.negotiation_id:
            db.add_event(
                self.negotiation_id,
                actor="negoai",
                type=directive.action,
                payload={
                    "text": spoken,
                    "subtitle": subtitle,
                    "directive": directive.as_instruction(
                        product=self.ctx.product,
                        unit=self.ctx.unit,
                        community=COMMUNITY["name"],
                        households=COMMUNITY["households"],
                    ),
                    "price": directive.price,
                },
            )
        await self.speak(spoken, subtitle)

    async def _llm_phrase(self, engine, directive, fallback_spoken, fallback_subtitle):
        system = negotiator_system(
            community_name=COMMUNITY["name"],
            households=COMMUNITY["households"],
            vendor_name=engine.vendor_name,
            product=self.ctx.product,
            unit=self.ctx.unit,
            qty=AGGREGATE_QTY,
            verified_quotes=[
                quote.unit_price for quote in engine.history if quote.unit_price
            ],
            round_no=directive.round,
            max_rounds=directive.max_rounds,
            directive=directive.as_instruction(
                product=self.ctx.product,
                unit=self.ctx.unit,
                community=COMMUNITY["name"],
                households=COMMUNITY["households"],
            ),
        )
        payload = await self.llm.complete_json(
            system,
            f"Say the next line in {self.language}. Return JSON only.",
        )
        say = (payload or {}).get("say")
        if not isinstance(say, str) or not say.strip():
            return fallback_spoken, fallback_subtitle

        allowed = {float(AGGREGATE_QTY)}
        if directive.price is not None:
            allowed.add(float(directive.price))
        if directive.competitor is not None:
            allowed.add(float(directive.competitor))
        if directive.qty is not None:
            allowed.add(float(directive.qty))
        if self.intake.qty is not None:
            allowed.add(float(self.intake.qty))

        invented = numbers_in(say) - allowed
        if invented:
            log.info("Rejected LLM line with invented numbers: %s", invented)
            return fallback_spoken, fallback_subtitle
        return say.strip(), fallback_subtitle

    async def vendor_quote_turn(
        self, engine: NegotiationEngine, agent_price: Optional[float] = None
    ) -> None:
        persona_vendor = self.sims.get(engine.vendor_id)
        if persona_vendor is None:
            return
        # Verified competing quotes only: real recorded offers from other vendors.
        competing = [
            offer.unit_price
            for vendor_id, offer in self.offers.items()
            if vendor_id != engine.vendor_id
        ]
        if competing:
            engine.set_competitor(min(competing))

        offer = persona_vendor.quote(agent_price=agent_price)
        if offer.unit_price <= 0:
            directive = engine.record_refusal()
            await self.agent_turn(engine, directive)
            return

        engine.record_offer(offer)
        self.offers[engine.vendor_id] = offer
        eligible = offer.unit_price <= MAX_PRICE + 1e-9

        if self.negotiation_id:
            db.save_offer(
                self.negotiation_id,
                vendor_id=engine.vendor_id,
                product=engine.product,
                unit_price=offer.unit_price,
                delivery_charge=offer.delivery_charge,
                min_qty=offer.min_qty,
                valid_days=offer.valid_days,
                round_no=offer.round,
                eligible=eligible,
            )
            # The vendor quote is its own audit row, so Replay and the receipt
            # both show the price actually said, not just the agent's answer.
            db.add_event(
                self.negotiation_id,
                actor="vendor",
                type="offer",
                payload={
                    "vendor_id": engine.vendor_id,
                    "vendor_name": engine.vendor_name,
                    "unit_price": offer.unit_price,
                    "delivery_charge": offer.delivery_charge,
                    "min_qty": offer.min_qty,
                    "valid_days": offer.valid_days,
                    "round": offer.round,
                    "eligible": eligible,
                    "source": "simulated",
                },
            )
            db.update_negotiation(
                self.negotiation_id,
                state=engine.state,
                round_no=engine.round,
                best_quote=engine.best_eligible.unit_price if engine.best_eligible else None,
            )

        spoken, subtitle = vendor_line(
            {
                "kind": "quote",
                "unit_price": offer.unit_price,
                "delivery_charge": offer.delivery_charge,
                "min_qty": offer.min_qty,
            },
            persona_vendor.persona,
            self.ctx,
            self.language,
        )
        await self.emit({"type": "state", "orb": "thinking"})
        await self.emit(
            {
                "type": "vendor",
                "vendor_id": engine.vendor_id,
                "vendor_name": engine.vendor_name,
                "persona": persona_vendor.persona.personality,
                "line": spoken,
                "subtitle": subtitle,
                "lang": self.language,
                "round": offer.round,
                "eligible": eligible,
                "delivery_days": persona_vendor.persona.delivery_days,
                "quote": offer.to_dict(),
            }
        )
        await self.speak(
            spoken,
            subtitle,
            voice=self.tts.distinct_voice(self.language, persona_vendor.persona.voice),
            role="vendor",
        )
        await self.emit_offers()

    async def vendor_delivery_turn(self, engine: NegotiationEngine) -> None:
        sim = self.sims.get(engine.vendor_id)
        if sim is None:
            return
        terms = sim.delivery_terms()
        engine.record_delivery(
            free=terms["free_delivery"],
            charge=terms["delivery_charge"],
            min_qty=terms["min_qty"],
        )
        offer = self.offers.get(engine.vendor_id)
        if offer is not None:
            offer.delivery_charge = 0.0 if terms["free_delivery"] else terms["delivery_charge"]
            offer.min_qty = max(offer.min_qty or 0, terms["min_qty"])

        spoken, subtitle = vendor_line(
            {"kind": "delivery", **terms},
            sim.persona,
            self.ctx,
            self.language,
        )
        await self.emit(
            {
                "type": "vendor",
                "vendor_id": engine.vendor_id,
                "vendor_name": engine.vendor_name,
                "persona": sim.persona.personality,
                "line": spoken,
                "subtitle": subtitle,
                "lang": self.language,
                "round": engine.round,
                "eligible": bool(
                    offer and offer.unit_price <= MAX_PRICE + 1e-9
                ),
                "delivery_days": sim.persona.delivery_days,
                "quote": (offer or Offer(unit_price=sim.last_price or 0)).to_dict(),
            }
        )
        await self.speak(
            spoken,
            subtitle,
            voice=self.tts.distinct_voice(self.language, sim.persona.voice),
            role="vendor",
        )
        await self.emit_offers()

    async def emit_offers(self) -> None:
        offers = []
        for vendor_id, offer in self.offers.items():
            engine = self.engines.get(vendor_id)
            effective = round(
                offer.unit_price * AGGREGATE_QTY + (offer.delivery_charge or 0), 2
            )
            offers.append(
                {
                    **offer.to_dict(),
                    "persona": self.sims[vendor_id].persona.personality if vendor_id in self.sims else "",
                    "eligible": offer.unit_price <= MAX_PRICE + 1e-9,
                    "effective": effective,
                }
            )
        offers.sort(key=lambda item: (item["effective"], item["unit_price"]))
        first_quotes = [
            engine.first_quote.unit_price
            for engine in self.engines.values()
            if engine.first_quote
        ]
        await self.emit(
            {
                "type": "offers",
                "offers": offers,
                "best": offers[0] if offers else None,
                "first_quote": max(first_quotes) if first_quotes else None,
            }
        )

    # ------------------------------------------------------------------- demo
    async def run_demo(self) -> None:
        try:
            script = DEMO_SCRIPT.get(self.language, DEMO_SCRIPT["en-IN"])
            spoken, subtitle = GREETING.get(self.language, GREETING["en-IN"])
            await self.speak(spoken, subtitle)
            await asyncio.sleep(0.4 * self.pace)

            demand_text, demand_sub = script["demand"]
            await self._resident(demand_text, demand_sub)
            await asyncio.sleep(0.8 * self.pace)

            confirm_text, confirm_sub = script["confirm"]
            await self._resident(confirm_text, confirm_sub)
            await asyncio.sleep(0.5 * self.pace)

            day_text, day_sub = script["day"]
            await self._resident(day_text, day_sub)
            await asyncio.sleep(0.4 * self.pace)

            flat_text, flat_sub = script["flat"]
            await self._resident(flat_text, flat_sub)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("demo failed")
            await self.emit({"type": "error", "message": f"Demo failed: {exc}"})

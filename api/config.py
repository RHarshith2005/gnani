"""Runtime configuration. Keys never leave this process."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOICE_CATALOG = ROOT.parent / "config" / "voices.json"
log = logging.getLogger("negoai.config")

# Load api/.env for local runs and uvicorn. Tests set NEGOAI_NO_DOTENV=1 so a
# developer key on the box can never leak into the key-free test suite.
if not os.environ.get("NEGOAI_NO_DOTENV"):
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:  # python-dotenv absent: plain environment variables
        pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _default_database_path() -> str:
    """Vercel's filesystem is read-only except for /tmp, so keep the store there."""
    if os.environ.get("VERCEL"):
        return "/tmp/negoai.sqlite3"
    return str(ROOT / "negoai.sqlite3")


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = _env(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


#: Domain vocabulary sent as Prisma keyterms so product words are favoured.
DEFAULT_STT_KEYTERMS = [
    "NegoAI",
    "water can",
    "society",
    "delivery",
    "milk",
    "vegetables",
    "ಕ್ಯಾನ್",
    "ನೀರು",
    "पानी",
    "कैन",
    "दूध",
]


@dataclass
class Settings:
    """Everything the gateway needs, resolved once at import time."""

    # Gnani (Prisma STT / Timbre TTS) — server-only.
    gnani_api_key: str = field(default_factory=lambda: _env("GNANI_API_KEY"))
    gnani_key_id: str = field(default_factory=lambda: _env("GNANI_KEY_ID") or _env("GNANI_API_KEY"))
    gnani_stt_url: str = field(
        default_factory=lambda: _env("GNANI_STT_URL", "wss://api.vachana.ai/stt/v3/stream")
    )
    gnani_tts_url: str = field(
        default_factory=lambda: _env("GNANI_TTS_URL", "wss://api.vachana.ai/api/v1/tts")
    )
    gnani_tts_model: str = field(default_factory=lambda: _env("GNANI_TTS_MODEL", "timbre-v3.0"))
    gnani_tts_speed: float = field(default_factory=lambda: _env_float("GNANI_TTS_SPEED", 1.0))
    gnani_sample_rate: int = field(default_factory=lambda: int(_env_float("GNANI_SAMPLE_RATE", 16000)))
    gnani_stt_model: str = field(default_factory=lambda: _env("GNANI_STT_MODEL", "prisma-v3.0"))

    # Prisma VAD tuning (headers at handshake). These defaults favour complete
    # sentences from a laptop mic over the fastest possible transcript.
    gnani_vad_threshold: float = field(
        default_factory=lambda: _env_float("GNANI_VAD_THRESHOLD", 0.6)
    )
    gnani_min_silence_ms: int = field(
        default_factory=lambda: int(_env_float("GNANI_MIN_SILENCE_MS", 700))
    )
    gnani_min_speech_ms: int = field(
        default_factory=lambda: int(_env_float("GNANI_MIN_SPEECH_MS", 150))
    )
    gnani_stt_topic: str = field(
        default_factory=lambda: _env(
            "GNANI_STT_TOPIC",
            "apartment society bulk purchase of water cans, milk and vegetables",
        )
    )
    gnani_stt_keyterms: list[str] = field(
        default_factory=lambda: _env_list("GNANI_STT_KEYTERMS", DEFAULT_STT_KEYTERMS)
    )

    # Optional LLM. Any OpenAI-compatible endpoint works (OpenAI, Groq, Ollama,
    # vLLM); without a key the deterministic scripted composer speaks instead.
    llm_base_url: str = field(
        default_factory=lambda: _env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    )
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))
    llm_timeout: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT", 12.0))
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.2))

    # Supabase is the production store; SQLite is the zero-config local store.
    supabase_url: str = field(default_factory=lambda: _env("SUPABASE_URL"))
    # New-style secret key first, legacy service-role name as a fallback.
    supabase_service_key: str = field(
        default_factory=lambda: _env("SUPABASE_SECRET_KEY") or _env("SUPABASE_SERVICE_KEY")
    )
    supabase_publishable_key: str = field(
        default_factory=lambda: _env("SUPABASE_PUBLISHABLE_KEY")
    )
    supabase_db_url: str = field(default_factory=lambda: _env("SUPABASE_DB_URL"))
    database_path: str = field(
        default_factory=lambda: _env("NEGOAI_DB") or _default_database_path()
    )

    demo_pace: float = field(default_factory=lambda: _env_float("DEMO_PACE", 0.55))
    allow_origins: str = field(
        default_factory=lambda: _env("ALLOWED_ORIGINS") or _env("CORS_ORIGINS", "*")
    )

    # Voice credit guard (Prompt 10): characters of TTS, per session and globally.
    credit_budget: int = field(default_factory=lambda: int(_env_float("CREDIT_BUDGET", 60000)))
    session_tts_chars: int = field(
        default_factory=lambda: int(_env_float("SESSION_TTS_CHARS", 12000))
    )

    @property
    def has_gnani(self) -> bool:
        return bool(self.gnani_api_key or self.gnani_key_id)

    @property
    def has_llm(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def stt_mode(self) -> str:
        return "gnani" if self.has_gnani else "browser"

    @property
    def tts_mode(self) -> str:
        return "gnani" if self.has_gnani else "browser"

    def as_public(self) -> dict:
        """Capabilities only — never keys, never the target price."""
        return {
            "stt": self.stt_mode,
            "tts": self.tts_mode,
            "llm": "llm" if self.has_llm else "scripted",
            "stt_model": self.gnani_stt_model,
            "tts_model": self.gnani_tts_model,
        }


settings = Settings()

# Language -> Timbre v3.0 agent voice plus distinct vendor voices. Read from
# config/voices.json; GNANI_VOICE_<LANG> overrides the agent voice. Every v3.0
# voice speaks all three languages, so one identity holds across a language switch.
def _load_voice_catalog() -> tuple[dict[str, str], dict[str, list[str]]]:
    agents = {"kn-IN": "Shivani", "hi-IN": "Shivani", "en-IN": "Shivani"}
    vendors = {
        lang: ["Avinash", "Devansh", "Prakash"] for lang in agents
    }
    try:
        raw = json.loads(VOICE_CATALOG.read_text(encoding="utf-8"))
        voices = raw.get("voices") if isinstance(raw, dict) else None
        if isinstance(voices, dict):
            for lang, value in voices.items():
                if isinstance(value, dict):
                    agent = value.get("agent")
                    if isinstance(agent, str) and agent:
                        agents[str(lang)] = agent
                    names = value.get("vendors")
                    if isinstance(names, list) and names:
                        vendors[str(lang)] = [str(name) for name in names]
                else:
                    agents[str(lang)] = str(value)
    except FileNotFoundError:
        log.info("config/voices.json missing; using built-in voice names")
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("config/voices.json unreadable (%s); using built-in voice names", exc)
    agents = {
        lang: _env(f"GNANI_VOICE_{lang.split('-')[0].upper()}", default)
        for lang, default in agents.items()
    }
    return agents, vendors


VOICES, VENDOR_VOICES = _load_voice_catalog()

SUPPORTED_LANGUAGES = tuple(VOICES.keys())

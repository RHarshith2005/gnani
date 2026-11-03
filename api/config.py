"""Runtime configuration. Keys never leave this process."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
    gnani_tts_model: str = field(default_factory=lambda: _env("GNANI_TTS_MODEL", "timbre-v2.5"))
    gnani_sample_rate: int = field(default_factory=lambda: int(_env_float("GNANI_SAMPLE_RATE", 16000)))

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
    supabase_service_key: str = field(default_factory=lambda: _env("SUPABASE_SERVICE_KEY"))
    database_path: str = field(
        default_factory=lambda: _env("NEGOAI_DB", str(ROOT / "negoai.sqlite3"))
    )

    demo_pace: float = field(default_factory=lambda: _env_float("DEMO_PACE", 0.55))
    allow_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "*"))

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
            "tts_model": self.gnani_tts_model,
        }


settings = Settings()

# Language -> Timbre voice. Voices are configurable because availability per
# language must be confirmed against the challenge account.
VOICES = {
    lang: _env(f"GNANI_VOICE_{lang.split('-')[0].upper()}", default)
    for lang, default in {
        "kn-IN": "Nalini",
        "hi-IN": "Kaveri",
        "en-IN": "Deepak",
    }.items()
}

SUPPORTED_LANGUAGES = tuple(VOICES.keys())

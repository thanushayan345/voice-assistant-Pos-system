"""Environment-backed configuration loader and startup validator for Local Ollama AI."""

from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("tamil_voice_pos.config")

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE_PATH = BACKEND_DIR / ".env"

# Load backend/.env (and optional root .env) without overriding explicit OS env vars
load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

CURRENCY_SYMBOLS = {
    "LKR": "Rs.",
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

SUPPORTED_UNITS = [
    "Pieces",
    "Kilograms",
    "Grams",
    "Litres",
    "Bottles",
    "Packets",
    "Boxes",
    "Bags",
]

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Settings(BaseModel):
    """Validated application settings loaded from environment variables."""

    AI_PROVIDER: str = Field(default="ollama")
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_MODEL: str = Field(default="qwen2.5:3b", min_length=1)
    OLLAMA_TIMEOUT: int = Field(default=60, ge=5, le=300)

    CURRENCY: str = Field(default="LKR", min_length=2, max_length=10)
    LANGUAGE: str = Field(default="en-US", min_length=2, max_length=15)
    LOW_STOCK_DEFAULT: Decimal = Field(default=Decimal("5"))
    BIG_AMOUNT: Decimal = Field(default=Decimal("50000"))

    JWT_SECRET_KEY: str = Field(
        default="tamil-voice-pos-dev-secret-change-in-prod-2026",
        min_length=16,
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, ge=5)
    DATABASE_URL: str = Field(
        default=f"sqlite:///{(BACKEND_DIR / 'tamil_voice_pos.db').as_posix()}"
    )
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned != "ollama":
            raise ValueError(
                "Only 'ollama' is permitted for AI_PROVIDER. External cloud LLM APIs are disabled."
            )
        return cleaned

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def validate_ollama_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("OLLAMA_BASE_URL must be a valid HTTP URL (e.g., http://127.0.0.1:11434).")
        if parsed.hostname not in LOCAL_HOSTS:
            raise ValueError(
                "OLLAMA_BASE_URL must point to localhost / 127.0.0.1. Exposing or calling remote public endpoints is prohibited."
            )
        return cleaned

    @field_validator("OLLAMA_MODEL")
    @classmethod
    def validate_ollama_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("OLLAMA_MODEL cannot be empty.")
        return cleaned

    @field_validator("CURRENCY")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("CURRENCY cannot be empty.")
        return cleaned

    @field_validator("LANGUAGE")
    @classmethod
    def validate_language(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("LANGUAGE cannot be empty.")
        return cleaned

    @field_validator("LOW_STOCK_DEFAULT", mode="before")
    @classmethod
    def parse_low_stock(cls, value: object) -> Decimal:
        try:
            dec = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("LOW_STOCK_DEFAULT must be a valid number.") from exc
        if dec < Decimal("0"):
            raise ValueError("LOW_STOCK_DEFAULT must be >= 0.")
        return dec

    @field_validator("BIG_AMOUNT", mode="before")
    @classmethod
    def parse_big_amount(cls, value: object) -> Decimal:
        try:
            dec = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("BIG_AMOUNT must be a valid number.") from exc
        if dec <= Decimal("0"):
            raise ValueError("BIG_AMOUNT must be > 0.")
        return dec

    @property
    def currency_symbol(self) -> str:
        return CURRENCY_SYMBOLS.get(self.CURRENCY, self.CURRENCY)

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


def load_settings() -> Settings:
    """Load and validate settings from environment variables."""
    raw_db_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_db_url:
        raw_db_url = f"sqlite:///{(BACKEND_DIR / 'tamil_voice_pos.db').as_posix()}"
    elif raw_db_url.startswith("sqlite:///./"):
        rel_name = raw_db_url.replace("sqlite:///./", "", 1)
        raw_db_url = f"sqlite:///{(BACKEND_DIR / rel_name).as_posix()}"

    return Settings(
        AI_PROVIDER=os.getenv("AI_PROVIDER", "ollama"),
        OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        OLLAMA_TIMEOUT=int(os.getenv("OLLAMA_TIMEOUT", "60")),
        CURRENCY=os.getenv("CURRENCY", "LKR"),
        LANGUAGE=os.getenv("LANGUAGE", "en-US"),
        LOW_STOCK_DEFAULT=os.getenv("LOW_STOCK_DEFAULT", "5"),
        BIG_AMOUNT=os.getenv("BIG_AMOUNT", "50000"),
        JWT_SECRET_KEY=os.getenv(
            "JWT_SECRET_KEY",
            "tamil-voice-pos-dev-secret-change-in-prod-2026",
        ),
        JWT_EXPIRE_MINUTES=int(os.getenv("JWT_EXPIRE_MINUTES", "1440")),
        DATABASE_URL=raw_db_url,
        CORS_ORIGINS=os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ),
    )


settings = load_settings()


def _clean_env_val(val: object) -> str:
    raw = str(val or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1].strip()
    return raw


def refresh_runtime_env() -> None:
    """Re-read .env files from disk so local Ollama settings updates apply immediately."""
    for env_path in (BACKEND_DIR / ".env", PROJECT_ROOT / ".env"):
        if not env_path.exists():
            continue
        vals = dotenv_values(env_path)
        base_url = _clean_env_val(vals.get("OLLAMA_BASE_URL"))
        if base_url:
            settings.OLLAMA_BASE_URL = base_url.rstrip("/")
        model_val = _clean_env_val(vals.get("OLLAMA_MODEL"))
        if model_val:
            settings.OLLAMA_MODEL = model_val
        timeout_val = _clean_env_val(vals.get("OLLAMA_TIMEOUT"))
        if timeout_val.isdigit():
            settings.OLLAMA_TIMEOUT = int(timeout_val)
        lang_val = _clean_env_val(vals.get("LANGUAGE"))
        if lang_val:
            settings.LANGUAGE = lang_val
        break


def validate_startup_configuration() -> None:
    """Validate required configuration at backend startup and log status."""
    _ = Settings.model_validate(settings.model_dump())

    if not ENV_FILE_PATH.exists():
        logger.warning(
            "Environment file not found at %s. Using OS environment/default configuration.",
            ENV_FILE_PATH,
        )

    logger.info(
        "Local AI Configuration validated: Provider=%s, Endpoint=%s, Model=%s, Timeout=%ss, Currency=%s",
        settings.AI_PROVIDER,
        settings.OLLAMA_BASE_URL,
        settings.OLLAMA_MODEL,
        settings.OLLAMA_TIMEOUT,
        settings.CURRENCY,
    )

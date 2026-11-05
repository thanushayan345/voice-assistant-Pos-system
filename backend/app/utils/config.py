"""Environment-backed configuration loader and startup validator."""

from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List

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

PLACEHOLDER_KEYS = {
    "",
    "your_gemini_api_key",
    "your_gemini_api_key_here",
    "replace_me",
    "changeme",
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


class Settings(BaseModel):
    """Validated application settings loaded from environment variables."""

    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-3.8-flash", min_length=1)
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
    DATABASE_URL: str = Field(default=f"sqlite:///{(BACKEND_DIR / 'tamil_voice_pos.db').as_posix()}")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

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
    def ai_configured(self) -> bool:
        key = (self.GEMINI_API_KEY or "").strip()
        return key.lower() not in PLACEHOLDER_KEYS and len(key) >= 10

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
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
        GEMINI_MODEL=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
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
    """
    Re-read .env files directly from disk so newly saved GEMINI_API_KEY / GEMINI_MODEL / LANGUAGE
    take effect immediately without requiring a backend server restart.
    """
    candidate_files = [
        BACKEND_DIR / ".env",
        PROJECT_ROOT / ".env",
        BACKEND_DIR / ".env.example",
        PROJECT_ROOT / ".env.example",
    ]

    for env_path in candidate_files:
        if not env_path.exists():
            continue
        vals = dotenv_values(env_path)
        candidate_key = _clean_env_val(vals.get("GEMINI_API_KEY"))
        if candidate_key and candidate_key.lower() not in PLACEHOLDER_KEYS and len(candidate_key) >= 10:
            if env_path.name.endswith(".example"):
                logger.warning(
                    "Detected GEMINI_API_KEY inside %s — please move your key to backend/.env so it stays git-ignored!",
                    env_path.name,
                )
            settings.GEMINI_API_KEY = candidate_key
            model_val = _clean_env_val(vals.get("GEMINI_MODEL"))
            if model_val:
                settings.GEMINI_MODEL = model_val
            lang_val = _clean_env_val(vals.get("LANGUAGE"))
            if lang_val:
                settings.LANGUAGE = lang_val
            return

    # Also check OS environment if set
    os_key = _clean_env_val(os.getenv("GEMINI_API_KEY"))
    if os_key and os_key.lower() not in PLACEHOLDER_KEYS and len(os_key) >= 10:
        settings.GEMINI_API_KEY = os_key


def validate_startup_configuration() -> None:
    """Validate required configuration at backend startup and log status."""
    # Re-validate current settings instance
    _ = Settings.model_validate(settings.model_dump())

    if not ENV_FILE_PATH.exists():
        logger.warning(
            "Environment file not found at %s. Using OS environment/default configuration.",
            ENV_FILE_PATH,
        )

    if not settings.ai_configured:
        logger.warning(
            "GEMINI_API_KEY is missing or set to placeholder in backend/.env. "
            "Manual POS, Product Management, Inventory, and Reports are active; "
            "Voice AI requests will return a clear configuration error until GEMINI_API_KEY is set."
        )
    else:
        logger.info(
            "Configuration validated: Model=%s, Currency=%s, Language=%s, LowStock=%s, BigAmount=%s",
            settings.GEMINI_MODEL,
            settings.CURRENCY,
            settings.LANGUAGE,
            settings.LOW_STOCK_DEFAULT,
            settings.BIG_AMOUNT,
        )

"""Public application configuration endpoint (never exposes secrets)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from app.schemas.config import PublicConfigResponse, SupportedLanguageOption
from app.utils.config import SUPPORTED_UNITS, refresh_runtime_env, settings

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("", response_model=PublicConfigResponse)
def get_public_config():
    """Return non-sensitive runtime configuration for the React frontend."""
    refresh_runtime_env()

    supported = [
        SupportedLanguageOption(code="en-US", label="English (US)"),
        SupportedLanguageOption(code="en-GB", label="English (UK)"),
        SupportedLanguageOption(code="en-IN", label="English (South Asia)"),
    ]
    if settings.LANGUAGE and all(opt.code != settings.LANGUAGE for opt in supported):
        supported.insert(
            0,
            SupportedLanguageOption(
                code=settings.LANGUAGE,
                label=f"Configured ({settings.LANGUAGE})",
            ),
        )

    return PublicConfigResponse(
        app_name="Voice POS",
        currency=settings.CURRENCY,
        currency_symbol=settings.currency_symbol,
        language=settings.LANGUAGE,
        supported_languages=supported,
        low_stock_default=Decimal(str(settings.LOW_STOCK_DEFAULT)),
        big_amount=Decimal(str(settings.BIG_AMOUNT)),
        gemini_model=settings.GEMINI_MODEL,
        ai_configured=settings.ai_configured,
        supported_units=SUPPORTED_UNITS,
    )

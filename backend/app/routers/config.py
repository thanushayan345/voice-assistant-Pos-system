"""Public application configuration endpoint (Local Ollama AI + Hardware status)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from app.schemas.config import PublicConfigResponse, SupportedLanguageOption
from app.services.ollama_service import get_ollama_and_hardware_status
from app.utils.config import SUPPORTED_UNITS, refresh_runtime_env, settings

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("", response_model=PublicConfigResponse)
def get_public_config():
    """Return non-sensitive runtime configuration + local Ollama & GPU/RAM health."""
    refresh_runtime_env()
    ollama_connected, ollama_model_ready, hardware = get_ollama_and_hardware_status()

    supported = [
        SupportedLanguageOption(code="en-US", label="English (US)"),
        SupportedLanguageOption(code="en-IN", label="English (South Asia)"),
        SupportedLanguageOption(code="ta-LK", label="Tamil Voice Input (ta-LK)"),
        SupportedLanguageOption(code="ta-IN", label="Tamil Voice Input (ta-IN)"),
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
        ai_provider=settings.AI_PROVIDER,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        ollama_model=settings.OLLAMA_MODEL,
        ollama_timeout=settings.OLLAMA_TIMEOUT,
        ollama_connected=ollama_connected,
        ollama_model_ready=ollama_model_ready,
        ai_configured=bool(ollama_connected and ollama_model_ready),
        hardware=hardware,
        currency=settings.CURRENCY,
        currency_symbol=settings.currency_symbol,
        language=settings.LANGUAGE,
        supported_languages=supported,
        low_stock_default=Decimal(str(settings.LOW_STOCK_DEFAULT)),
        big_amount=Decimal(str(settings.BIG_AMOUNT)),
        supported_units=SUPPORTED_UNITS,
    )

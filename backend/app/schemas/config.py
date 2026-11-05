"""Public configuration response schema (never exposes API keys)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.schemas.common import MoneyDecimal, QtyDecimal


class SupportedLanguageOption(BaseModel):
    code: str
    label: str


class PublicConfigResponse(BaseModel):
    app_name: str
    currency: str
    currency_symbol: str
    language: str
    supported_languages: List[SupportedLanguageOption]
    low_stock_default: QtyDecimal
    big_amount: MoneyDecimal
    gemini_model: str
    ai_configured: bool
    supported_units: List[str]

"""Public configuration response schema for Local Ollama AI POS."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import MoneyDecimal, QtyDecimal


class SupportedLanguageOption(BaseModel):
    code: str
    label: str


class HardwareMetrics(BaseModel):
    gpu_name: Optional[str] = None
    vram_total_mb: Optional[int] = None
    vram_used_mb: Optional[int] = None
    ram_total_gb: Optional[float] = None
    ram_used_gb: Optional[float] = None
    ram_percent: Optional[float] = None
    loaded_model_vram_mb: Optional[float] = None
    acceleration: str = "CPU / Auto"


class PublicConfigResponse(BaseModel):
    app_name: str
    ai_provider: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout: int
    ollama_connected: bool
    ollama_model_ready: bool
    ai_configured: bool
    hardware: Optional[HardwareMetrics] = None
    currency: str
    currency_symbol: str
    language: str
    supported_languages: List[SupportedLanguageOption]
    low_stock_default: QtyDecimal
    big_amount: MoneyDecimal
    supported_units: List[str]

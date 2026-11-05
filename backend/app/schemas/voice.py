"""Voice AI command processing and confirmation Pydantic schemas (Local Ollama + Qwen 2.5 3B)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

SUPPORTED_INTENTS = (
    "CHECK_STOCK",
    "ADD_STOCK",
    "REDUCE_STOCK",
    "RECORD_SALE",
    "CHECK_PRICE",
    "SEARCH_PRODUCT",
    "CHECK_LOW_STOCK",
    "GET_TODAY_SALES",
    "GET_SALES_REPORT",
    "ADD_PRODUCT",
    "UNKNOWN",
)

IntentType = Literal[
    "CHECK_STOCK",
    "ADD_STOCK",
    "REDUCE_STOCK",
    "RECORD_SALE",
    "CHECK_PRICE",
    "SEARCH_PRODUCT",
    "CHECK_LOW_STOCK",
    "GET_TODAY_SALES",
    "GET_SALES_REPORT",
    "ADD_PRODUCT",
    "UNKNOWN",
]


class AIStructuredIntent(BaseModel):
    """Strict Pydantic schema enforced on local Ollama (qwen2.5:3b) structured JSON output."""

    intent: IntentType = "UNKNOWN"
    product_name: Optional[str] = None
    spoken_product_term: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    selling_price: Optional[float] = None
    purchase_price: Optional[float] = None
    category: Optional[str] = None
    report_period: Optional[str] = None
    is_ambiguous: bool = False
    ambiguous_candidates: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    response_language: Literal["ta", "en"] = "en"


class VoiceProcessRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=600)
    language: Optional[str] = Field(default=None, max_length=20)

    @field_validator("transcript")
    @classmethod
    def clean_transcript(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Voice command text cannot be empty.")
        return cleaned


class VoiceConfirmRequest(BaseModel):
    confirmation_token: str = Field(..., min_length=8, max_length=80)


class VoiceCancelRequest(BaseModel):
    confirmation_token: str = Field(..., min_length=8, max_length=80)


class VoiceCommandResponse(BaseModel):
    command_id: int
    intent: str
    transcript: str
    response_text: str
    response_language: str  # "ta" | "en"
    confidence: float = 0.0
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    status: str  # COMPLETED | PENDING_CONFIRMATION | CONFIRMED | CANCELLED | FAILED
    is_big_amount_warning: bool = False
    data: Optional[Dict[str, Any]] = None
    created_at: datetime


class VoiceHistoryItem(BaseModel):
    id: int
    transcript: str
    intent: str
    status: str
    confidence: Optional[float] = None
    response_text: Optional[str] = None
    created_at: datetime

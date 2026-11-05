"""Pydantic schemas and sanitization rules for Maintenance Mode & Feature Flags."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Patterns that must never appear in public maintenance messages
_SENSITIVE_PATTERNS = re.compile(
    r"(sqlite:///|[a-zA-Z]:\\|/Users/|/home/|JWT_SECRET|PASSWORD|SECRET_KEY|Traceback \(most recent|SELECT\s+.*\s+FROM)",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_public_text(text: str, fallback: str) -> str:
    """Strip HTML tags and redact any accidental sensitive path/SQL/secret details."""
    cleaned = _HTML_TAG_RE.sub("", (text or "")).strip()
    if not cleaned:
        return fallback
    if _SENSITIVE_PATTERNS.search(cleaned):
        return fallback
    return cleaned


class FeatureFlags(BaseModel):
    posBilling: bool = True
    voiceAssistant: bool = True
    productManagement: bool = True
    inventoryAdjustments: bool = True
    reportsAnalytics: bool = True


class SystemStatusResponse(BaseModel):
    maintenance: bool = False
    message: str = "Scheduled system maintenance is currently in progress."
    estimatedTime: str = "15 minutes"
    updatedAt: datetime
    blocking: bool = False
    features: FeatureFlags = Field(default_factory=FeatureFlags)


class SystemStatusUpdateRequest(BaseModel):
    maintenance: Optional[bool] = None
    message: Optional[str] = Field(default=None, max_length=500)
    estimatedTime: Optional[str] = Field(default=None, max_length=120)
    blocking: Optional[bool] = None
    features: Optional[FeatureFlags] = None

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_public_text(
            v,
            fallback="Scheduled system maintenance is currently in progress. Please try again shortly.",
        )

    @field_validator("estimatedTime")
    @classmethod
    def clean_estimated_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_public_text(v, fallback="Shortly")

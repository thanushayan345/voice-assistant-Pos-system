"""SQLAlchemy model for authoritative backend maintenance mode and feature flags."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SystemStatus(Base):
    __tablename__ = "system_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    maintenance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Scheduled system maintenance is currently in progress.",
    )
    estimated_time: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="15 minutes",
    )
    features_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default='{"posBilling":true,"voiceAssistant":true,"productManagement":true,"inventoryAdjustments":true,"reportsAnalytics":true}',
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )

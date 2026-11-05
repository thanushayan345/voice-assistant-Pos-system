"""VoiceCommand SQLAlchemy ORM model for AI voice audit log and pending confirmations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VoiceCommand(Base):
    __tablename__ = "voice_commands"
    __table_args__ = (
        CheckConstraint(
            "status IN ('COMPLETED', 'PENDING_CONFIRMATION', 'CONFIRMED', 'CANCELLED', 'FAILED', 'EXPIRED')",
            name="ck_voice_commands_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    confirmation_token = Column(String(64), unique=True, nullable=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript = Column(Text, nullable=False)
    language = Column(String(20), nullable=True)
    intent = Column(String(40), nullable=False, default="UNKNOWN", index=True)
    ai_raw_response = Column(Text, nullable=True)
    validated_payload = Column(Text, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    requires_confirmation = Column(Boolean, nullable=False, default=False)
    status = Column(String(30), nullable=False, default="COMPLETED", index=True)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="voice_commands")

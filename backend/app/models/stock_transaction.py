"""StockTransaction SQLAlchemy ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('INITIAL', 'ADD', 'REDUCE', 'SALE', 'ADJUSTMENT')",
            name="ck_stock_tx_type",
        ),
        CheckConstraint("quantity >= 0", name="ck_stock_tx_qty_non_neg"),
        CheckConstraint("previous_stock >= 0", name="ck_stock_tx_prev_non_neg"),
        CheckConstraint("new_stock >= 0", name="ck_stock_tx_new_non_neg"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reference_sale_id = Column(
        Integer,
        ForeignKey("sales.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type = Column(String(20), nullable=False, index=True)
    quantity = Column(Numeric(12, 3), nullable=False)
    previous_stock = Column(Numeric(12, 3), nullable=False)
    new_stock = Column(Numeric(12, 3), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    product = relationship("Product", back_populates="stock_transactions")
    user = relationship("User", back_populates="stock_transactions")
    sale = relationship("Sale", back_populates="stock_transactions")

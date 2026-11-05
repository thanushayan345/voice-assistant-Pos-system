"""Sale and SaleItem SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

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


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_sales_total_non_neg"),
        CheckConstraint("cash_received >= 0", name="ck_sales_cash_non_neg"),
        CheckConstraint("change_amount >= 0", name="ck_sales_change_non_neg"),
        CheckConstraint("source IN ('POS', 'VOICE')", name="ck_sales_source"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_number = Column(String(40), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    total_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cash_received = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    change_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    payment_method = Column(String(20), nullable=False, default="CASH")
    source = Column(String(20), nullable=False, default="POS")
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = relationship("User", back_populates="sales")
    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
    )
    stock_transactions = relationship("StockTransaction", back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sale_items_price_non_neg"),
        CheckConstraint("subtotal >= 0", name="ck_sale_items_subtotal_non_neg"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(
        Integer,
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_name = Column(String(120), nullable=False)
    unit = Column(String(30), nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")

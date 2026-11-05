"""Product SQLAlchemy ORM model."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("purchase_price >= 0", name="ck_products_purchase_price_non_neg"),
        CheckConstraint("selling_price >= 0", name="ck_products_selling_price_non_neg"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_neg"),
        CheckConstraint("low_stock_limit >= 0", name="ck_products_low_stock_non_neg"),
    )

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_name = Column(String(120), nullable=False, index=True)
    tamil_name = Column(String(160), nullable=True)
    category = Column(String(80), nullable=False, default="General", index=True)
    barcode = Column(String(64), unique=True, nullable=True, index=True)
    purchase_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    selling_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    stock_quantity = Column(Numeric(12, 3), nullable=False, default=Decimal("0.000"))
    unit = Column(String(30), nullable=False, default="Pieces")
    low_stock_limit = Column(Numeric(12, 3), nullable=False, default=Decimal("5.000"))
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    sale_items = relationship("SaleItem", back_populates="product")
    stock_transactions = relationship(
        "StockTransaction",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    @property
    def id(self) -> int:
        return self.product_id

    @property
    def is_low_stock(self) -> bool:
        return Decimal(str(self.stock_quantity)) <= Decimal(str(self.low_stock_limit))

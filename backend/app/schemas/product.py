"""Product CRUD Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import MoneyDecimal, QtyDecimal
from app.utils.config import settings
from app.utils.tamil_lexicon import normalize_unit_name


class ProductBase(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=120)
    tamil_name: Optional[str] = Field(default=None, max_length=160)
    category: str = Field(default="General", min_length=1, max_length=80)
    barcode: Optional[str] = Field(default=None, max_length=64)
    purchase_price: MoneyDecimal = Field(default=Decimal("0.00"))
    selling_price: MoneyDecimal
    stock_quantity: QtyDecimal = Field(default=Decimal("0.000"))
    unit: str = Field(default="Pieces", min_length=1, max_length=30)
    low_stock_limit: QtyDecimal = Field(
        default_factory=lambda: Decimal(str(settings.LOW_STOCK_DEFAULT))
    )

    @field_validator("product_name", "category")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned

    @field_validator("tamil_name", "barcode")
    @classmethod
    def clean_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Measurement unit is required.")
        return normalize_unit_name(cleaned, fallback=cleaned)

    @field_validator("purchase_price", "selling_price", "stock_quantity", "low_stock_limit")
    @classmethod
    def check_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Numeric values cannot be negative.")
        return v


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    tamil_name: Optional[str] = Field(default=None, max_length=160)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    barcode: Optional[str] = Field(default=None, max_length=64)
    purchase_price: Optional[MoneyDecimal] = None
    selling_price: Optional[MoneyDecimal] = None
    stock_quantity: Optional[QtyDecimal] = None
    unit: Optional[str] = Field(default=None, min_length=1, max_length=30)
    low_stock_limit: Optional[QtyDecimal] = None

    @field_validator("purchase_price", "selling_price", "stock_quantity", "low_stock_limit")
    @classmethod
    def check_optional_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < Decimal("0"):
            raise ValueError("Numeric values cannot be negative.")
        return v

    @field_validator("barcode", "tamil_name")
    @classmethod
    def clean_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    tamil_name: Optional[str] = None
    category: str
    barcode: Optional[str] = None
    purchase_price: MoneyDecimal
    selling_price: MoneyDecimal
    stock_quantity: QtyDecimal
    unit: str
    low_stock_limit: QtyDecimal
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class StockMovementSummary(BaseModel):
    id: int
    transaction_type: str
    quantity: QtyDecimal
    previous_stock: QtyDecimal
    new_stock: QtyDecimal
    reason: Optional[str] = None
    created_at: datetime


class ProductDetailResponse(ProductResponse):
    recent_transactions: List[StockMovementSummary] = Field(default_factory=list)

"""POS Sale creation and receipt Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import MoneyDecimal, QtyDecimal


class SaleItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: QtyDecimal

    @field_validator("quantity")
    @classmethod
    def check_positive_qty(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Sale item quantity must be greater than zero.")
        return v


class SaleCreateRequest(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1)
    cash_received: MoneyDecimal
    payment_method: str = Field(default="CASH", max_length=20)
    notes: Optional[str] = Field(default=None, max_length=255)
    confirm_big_amount: bool = Field(
        default=False,
        description="Must be True when total exceeds BIG_AMOUNT threshold.",
    )

    @field_validator("cash_received")
    @classmethod
    def check_non_neg_cash(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Cash received cannot be negative.")
        return v


class SaleItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit: str
    quantity: QtyDecimal
    unit_price: MoneyDecimal
    subtotal: MoneyDecimal


class SaleResponse(BaseModel):
    id: int
    invoice_number: str
    user_id: int
    cashier_name: str
    total_amount: MoneyDecimal
    cash_received: MoneyDecimal
    change_amount: MoneyDecimal
    payment_method: str
    source: str
    notes: Optional[str] = None
    created_at: datetime
    items: List[SaleItemResponse]

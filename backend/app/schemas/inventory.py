"""Inventory adjustment and stock transaction Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import MoneyDecimal, QtyDecimal
from app.schemas.product import ProductResponse


class StockAdjustRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    adjustment_type: str = Field(..., description="ADD, REDUCE, or SET")
    quantity: QtyDecimal
    reason: Optional[str] = Field(default=None, max_length=255)

    @field_validator("adjustment_type")
    @classmethod
    def validate_adjustment_type(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in ("ADD", "REDUCE", "SET"):
            raise ValueError("adjustment_type must be ADD, REDUCE, or SET.")
        return cleaned

    @field_validator("quantity")
    @classmethod
    def validate_qty(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Quantity cannot be negative.")
        return v


class StockTransactionResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    tamil_name: Optional[str] = None
    unit: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    reference_sale_id: Optional[int] = None
    transaction_type: str
    quantity: QtyDecimal
    previous_stock: QtyDecimal
    new_stock: QtyDecimal
    reason: Optional[str] = None
    created_at: datetime


class InventoryItemResponse(ProductResponse):
    stock_status: str  # IN_STOCK | LOW_STOCK | OUT_OF_STOCK
    stock_retail_value: MoneyDecimal
    stock_cost_value: MoneyDecimal


class InventoryOverviewResponse(BaseModel):
    total_products: int
    low_stock_count: int
    out_of_stock_count: int
    total_retail_value: MoneyDecimal
    total_cost_value: MoneyDecimal
    items: List[InventoryItemResponse]

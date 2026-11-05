"""Shared Decimal-safe Pydantic field types."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer


def _to_money_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        raise ValueError("Monetary value is required.")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid monetary amount.") from exc
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_qty_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        raise ValueError("Quantity value is required.")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid quantity value.") from exc
    return dec.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _serialize_decimal_number(value: Decimal) -> float:
    return float(value)


MoneyDecimal = Annotated[
    Decimal,
    BeforeValidator(_to_money_decimal),
    PlainSerializer(_serialize_decimal_number, return_type=float, when_used="json"),
]

QtyDecimal = Annotated[
    Decimal,
    BeforeValidator(_to_qty_decimal),
    PlainSerializer(_serialize_decimal_number, return_type=float, when_used="json"),
]

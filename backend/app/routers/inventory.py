"""Inventory management endpoints: overview, low-stock alerts, stock adjustments, and ledger."""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.stock_transaction import StockTransaction
from app.models.user import User
from app.schemas.inventory import (
    InventoryOverviewResponse,
    StockAdjustRequest,
    StockTransactionResponse,
)
from app.schemas.product import ProductResponse
from app.services.inventory_service import (
    adjust_stock,
    get_inventory_overview,
    get_low_stock_products,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("", response_model=InventoryOverviewResponse)
def read_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full inventory summary and per-product stock valuation."""
    return get_inventory_overview(db)


@router.get("/low-stock", response_model=List[ProductResponse])
def read_low_stock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active products currently at or below their low-stock threshold."""
    products = get_low_stock_products(db)
    return [ProductResponse.model_validate(p) for p in products]


@router.post("/adjust", response_model=ProductResponse)
def adjust_inventory_stock(
    payload: StockAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add, reduce, or set stock quantity for a product with full transaction logging."""
    updated = adjust_stock(
        db=db,
        product_id=payload.product_id,
        adjustment_type=payload.adjustment_type,
        quantity=payload.quantity,
        user_id=current_user.id,
        reason=payload.reason,
        commit=True,
    )
    return ProductResponse.model_validate(updated)


@router.get("/transactions", response_model=List[StockTransactionResponse])
def list_stock_transactions(
    product_id: Optional[int] = Query(default=None, gt=0),
    transaction_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return recent inventory stock ledger entries."""
    query = db.query(StockTransaction).options(
        joinedload(StockTransaction.product),
        joinedload(StockTransaction.user),
    )

    if product_id is not None:
        query = query.filter(StockTransaction.product_id == product_id)

    if transaction_type and transaction_type.strip() and transaction_type.strip().upper() != "ALL":
        query = query.filter(
            StockTransaction.transaction_type == transaction_type.strip().upper()
        )

    rows = (
        query.order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
        .limit(limit)
        .all()
    )

    return [
        StockTransactionResponse(
            id=tx.id,
            product_id=tx.product_id,
            product_name=tx.product.product_name if tx.product else f"Product #{tx.product_id}",
            tamil_name=tx.product.tamil_name if tx.product else None,
            unit=tx.product.unit if tx.product else "Units",
            user_id=tx.user_id,
            username=tx.user.username if tx.user else None,
            reference_sale_id=tx.reference_sale_id,
            transaction_type=tx.transaction_type,
            quantity=Decimal(str(tx.quantity)),
            previous_stock=Decimal(str(tx.previous_stock)),
            new_stock=Decimal(str(tx.new_stock)),
            reason=tx.reason,
            created_at=tx.created_at,
        )
        for tx in rows
    ]

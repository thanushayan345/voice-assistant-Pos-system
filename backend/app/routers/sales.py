"""POS Sales endpoints: create sale, list sales history, and fetch receipt by ID."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.sale import Sale, SaleItem
from app.models.user import User
from app.schemas.sale import SaleCreateRequest, SaleResponse
from app.services.sales_service import create_sale_transaction, serialize_sale
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/sales", tags=["POS & Sales"])


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete a POS sale, deduct inventory atomically, and return printable receipt data."""
    sale = create_sale_transaction(
        db=db,
        user=current_user,
        items=payload.items,
        cash_received=payload.cash_received,
        payment_method=payload.payment_method,
        source="POS",
        notes=payload.notes,
        confirm_big_amount=payload.confirm_big_amount,
    )
    return serialize_sale(sale)


@router.get("", response_model=List[SaleResponse])
def list_sales(
    search: Optional[str] = Query(default=None, description="Search by invoice number or item name"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve completed sales ordered newest first."""
    query = db.query(Sale).options(joinedload(Sale.items), joinedload(Sale.user))

    local_tz = datetime.now().astimezone().tzinfo
    if date_from:
        start_dt = datetime.combine(date_from, time.min, tzinfo=local_tz).astimezone(timezone.utc)
        query = query.filter(Sale.created_at >= start_dt)
    if date_to:
        end_dt = (
            datetime.combine(date_to, time.min, tzinfo=local_tz) + timedelta(days=1)
        ).astimezone(timezone.utc)
        query = query.filter(Sale.created_at < end_dt)

    if search and search.strip():
        like_str = f"%{search.strip()}%"
        matching_sale_ids = (
            db.query(SaleItem.sale_id)
            .filter(SaleItem.product_name.ilike(like_str))
            .subquery()
        )
        query = query.filter(
            or_(
                Sale.invoice_number.ilike(like_str),
                Sale.id.in_(matching_sale_ids),
            )
        )

    sales = query.order_by(Sale.created_at.desc(), Sale.id.desc()).limit(limit).all()
    return [serialize_sale(s) for s in sales]


@router.get("/{id}", response_model=SaleResponse)
def get_sale(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single completed sale and its line items for receipt viewing/printing."""
    sale = (
        db.query(Sale)
        .options(joinedload(Sale.items), joinedload(Sale.user))
        .filter(Sale.id == id)
        .first()
    )
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale #{id} not found.",
        )
    return serialize_sale(sale)

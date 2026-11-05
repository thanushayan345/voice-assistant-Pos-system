"""Product CRUD endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.models.sale import SaleItem
from app.models.stock_transaction import StockTransaction
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.product import (
    ProductCreate,
    ProductDetailResponse,
    ProductResponse,
    ProductUpdate,
    StockMovementSummary,
)
from app.services.inventory_service import (
    get_active_product_or_404,
    search_active_products,
)
from app.utils.security import get_current_user
from app.utils.tamil_lexicon import normalize_unit_name

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = Query(default=None, description="Search by English/Tamil name or barcode"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    low_stock_only: bool = Query(default=False, description="Only return low-stock items"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List and filter active catalog products."""
    products = search_active_products(
        db=db,
        search=search,
        category=category,
        low_stock_only=low_stock_only,
    )
    return [ProductResponse.model_validate(p) for p in products]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new product and record its initial stock transaction."""
    existing_name = (
        db.query(Product)
        .filter(
            Product.is_deleted.is_(False),
            Product.product_name.ilike(payload.product_name.strip()),
        )
        .first()
    )
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A product named '{payload.product_name}' already exists.",
        )

    if payload.barcode:
        existing_barcode = (
            db.query(Product).filter(Product.barcode == payload.barcode).first()
        )
        if existing_barcode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Barcode '{payload.barcode}' is already assigned to another product.",
            )

    product = Product(
        product_name=payload.product_name,
        tamil_name=payload.tamil_name,
        category=payload.category,
        barcode=payload.barcode,
        purchase_price=payload.purchase_price,
        selling_price=payload.selling_price,
        stock_quantity=payload.stock_quantity,
        unit=payload.unit,
        low_stock_limit=payload.low_stock_limit,
        is_deleted=False,
    )
    db.add(product)
    db.flush()

    if payload.stock_quantity > Decimal("0"):
        tx = StockTransaction(
            product_id=product.product_id,
            user_id=current_user.id,
            transaction_type="INITIAL",
            quantity=payload.stock_quantity,
            previous_stock=Decimal("0.000"),
            new_stock=payload.stock_quantity,
            reason="Initial stock on product creation",
        )
        db.add(tx)

    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@router.get("/{id}", response_model=ProductDetailResponse)
def get_product_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full product details and its 15 most recent stock transactions."""
    product = get_active_product_or_404(db, id)
    recent_txs = (
        db.query(StockTransaction)
        .filter(StockTransaction.product_id == product.product_id)
        .order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
        .limit(15)
        .all()
    )
    base = ProductResponse.model_validate(product)
    return ProductDetailResponse(
        **base.model_dump(),
        recent_transactions=[
            StockMovementSummary(
                id=tx.id,
                transaction_type=tx.transaction_type,
                quantity=Decimal(str(tx.quantity)),
                previous_stock=Decimal(str(tx.previous_stock)),
                new_stock=Decimal(str(tx.new_stock)),
                reason=tx.reason,
                created_at=tx.created_at,
            )
            for tx in recent_txs
        ],
    )


@router.put("/{id}", response_model=ProductResponse)
def update_product(
    id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update product attributes and log stock adjustment if stock_quantity changed."""
    product = get_active_product_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    if "product_name" in update_data and update_data["product_name"]:
        new_name = update_data["product_name"].strip()
        conflict = (
            db.query(Product)
            .filter(
                Product.is_deleted.is_(False),
                Product.product_id != product.product_id,
                Product.product_name.ilike(new_name),
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another product named '{new_name}' already exists.",
            )
        product.product_name = new_name

    if "barcode" in update_data:
        new_barcode = update_data["barcode"]
        if new_barcode:
            barcode_conflict = (
                db.query(Product)
                .filter(
                    Product.product_id != product.product_id,
                    Product.barcode == new_barcode,
                )
                .first()
            )
            if barcode_conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Barcode '{new_barcode}' is already in use.",
                )
        product.barcode = new_barcode

    if "tamil_name" in update_data:
        product.tamil_name = update_data["tamil_name"]
    if "category" in update_data and update_data["category"]:
        product.category = update_data["category"].strip()
    if "purchase_price" in update_data and update_data["purchase_price"] is not None:
        product.purchase_price = update_data["purchase_price"]
    if "selling_price" in update_data and update_data["selling_price"] is not None:
        product.selling_price = update_data["selling_price"]
    if "unit" in update_data and update_data["unit"]:
        raw_unit = update_data["unit"].strip()
        product.unit = normalize_unit_name(raw_unit, fallback=raw_unit)
    if "low_stock_limit" in update_data and update_data["low_stock_limit"] is not None:
        product.low_stock_limit = update_data["low_stock_limit"]

    if "stock_quantity" in update_data and update_data["stock_quantity"] is not None:
        prev_stock = Decimal(str(product.stock_quantity)).quantize(Decimal("0.001"))
        new_stock = Decimal(str(update_data["stock_quantity"])).quantize(Decimal("0.001"))
        if new_stock != prev_stock:
            product.stock_quantity = new_stock
            tx = StockTransaction(
                product_id=product.product_id,
                user_id=current_user.id,
                transaction_type="ADJUSTMENT",
                quantity=abs(new_stock - prev_stock),
                previous_stock=prev_stock,
                new_stock=new_stock,
                reason="Stock updated via product edit",
            )
            db.add(tx)

    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete("/{id}", response_model=MessageResponse)
def delete_product(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a product. If referenced by historical sale items, archive cleanly
    so past receipts remain valid while removing it from active POS/catalog.
    """
    product = get_active_product_or_404(db, id)
    name = product.product_name

    has_sales = (
        db.query(SaleItem).filter(SaleItem.product_id == product.product_id).first()
        is not None
    )
    if has_sales:
        product.is_deleted = True
        product.barcode = None
        db.commit()
    else:
        db.delete(product)
        db.commit()

    return MessageResponse(message=f"Product '{name}' deleted successfully.")

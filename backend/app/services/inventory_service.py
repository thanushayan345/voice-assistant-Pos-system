"""Inventory management and product resolution service."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.stock_transaction import StockTransaction
from app.schemas.inventory import InventoryItemResponse, InventoryOverviewResponse
from app.utils.tamil_lexicon import (
    expand_search_terms,
    format_decimal_clean,
    strip_tamil_suffix,
)


def get_active_product_or_404(db: Session, product_id: int) -> Product:
    """Fetch an active (non-deleted) product or raise HTTP 404."""
    product = (
        db.query(Product)
        .filter(Product.product_id == product_id, Product.is_deleted.is_(False))
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product


def search_active_products(
    db: Session,
    search: Optional[str] = None,
    category: Optional[str] = None,
    low_stock_only: bool = False,
) -> List[Product]:
    """Search active products supporting English names, Tamil names/synonyms, and barcodes."""
    query = db.query(Product).filter(Product.is_deleted.is_(False))

    if category and category.strip() and category.strip().lower() != "all":
        query = query.filter(Product.category.ilike(category.strip()))

    if search and search.strip():
        terms = expand_search_terms(search.strip())
        clauses = []
        for term in terms:
            like_pattern = f"%{term}%"
            clauses.append(Product.product_name.ilike(like_pattern))
            clauses.append(Product.tamil_name.ilike(like_pattern))
            clauses.append(Product.category.ilike(like_pattern))
            clauses.append(Product.barcode.ilike(like_pattern))
        if clauses:
            query = query.filter(or_(*clauses))

    products = query.order_by(Product.product_name.asc()).all()
    if low_stock_only:
        products = [p for p in products if p.is_low_stock]
    return products


def resolve_product_candidates(
    db: Session,
    product_name: Optional[str],
    spoken_term: Optional[str] = None,
) -> List[Product]:
    """
    Match AI-extracted product_name / spoken_product_term against real DB products.
    Prioritizes exact name matches before falling back to synonym/substring matches.
    """
    active_products = (
        db.query(Product)
        .filter(Product.is_deleted.is_(False))
        .order_by(Product.product_name.asc())
        .all()
    )
    if not active_products:
        return []

    raw_queries = [q.strip() for q in (product_name, spoken_term) if q and q.strip()]
    if not raw_queries:
        return []

    # 1. Exact case-insensitive match on product_name or tamil_name tokens
    exact_matches: List[Product] = []
    for query_str in raw_queries:
        q_low = query_str.lower()
        q_stem = strip_tamil_suffix(q_low)
        for prod in active_products:
            p_name = prod.product_name.strip().lower()
            t_tokens = [
                t.strip().lower()
                for t in (prod.tamil_name or "").replace("/", ",").split(",")
                if t.strip()
            ]
            if q_low == p_name or q_stem == p_name or q_low in t_tokens or q_stem in t_tokens:
                if prod not in exact_matches:
                    exact_matches.append(prod)
    if len(exact_matches) == 1:
        return exact_matches

    # 2. Synonym expansion match
    expanded_terms: set[str] = set()
    for query_str in raw_queries:
        expanded_terms.update(expand_search_terms(query_str))

    synonym_matches: List[Product] = []
    for prod in active_products:
        p_name = prod.product_name.strip().lower()
        t_raw = (prod.tamil_name or "").lower()
        t_tokens = [t.strip() for t in t_raw.replace("/", ",").split(",") if t.strip()]
        for term in expanded_terms:
            if (
                term == p_name
                or term in t_tokens
                or (len(term) >= 2 and (term in p_name.split() or term in t_raw))
            ):
                if prod not in synonym_matches:
                    synonym_matches.append(prod)
                break

    if synonym_matches:
        return synonym_matches

    # 3. Substring fallback
    substring_matches: List[Product] = []
    for prod in active_products:
        p_name = prod.product_name.strip().lower()
        t_raw = (prod.tamil_name or "").lower()
        for term in expanded_terms:
            if len(term) >= 2 and (term in p_name or term in t_raw):
                if prod not in substring_matches:
                    substring_matches.append(prod)
                break

    return substring_matches


def adjust_stock(
    db: Session,
    product_id: int,
    adjustment_type: str,
    quantity: Decimal,
    user_id: Optional[int],
    reason: Optional[str] = None,
    commit: bool = True,
) -> Product:
    """Atomically adjust product stock and write an auditable StockTransaction."""
    product = get_active_product_or_404(db, product_id)
    prev_stock = Decimal(str(product.stock_quantity)).quantize(Decimal("0.001"))
    qty = Decimal(str(quantity)).quantize(Decimal("0.001"))

    adj_type = adjustment_type.strip().upper()
    if adj_type == "ADD":
        if qty <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity to add must be greater than zero.",
            )
        new_stock = prev_stock + qty
        tx_type = "ADD"
        tx_qty = qty
    elif adj_type == "REDUCE":
        if qty <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity to reduce must be greater than zero.",
            )
        if prev_stock < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for {product.product_name}. "
                    f"Available: {format_decimal_clean(prev_stock)} {product.unit}, "
                    f"Requested reduction: {format_decimal_clean(qty)} {product.unit}."
                ),
            )
        new_stock = prev_stock - qty
        tx_type = "REDUCE"
        tx_qty = qty
    elif adj_type == "SET":
        if qty < Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stock level cannot be negative.",
            )
        new_stock = qty
        tx_type = "ADJUSTMENT"
        tx_qty = abs(new_stock - prev_stock)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported adjustment_type. Use ADD, REDUCE, or SET.",
        )

    product.stock_quantity = new_stock
    tx = StockTransaction(
        product_id=product.product_id,
        user_id=user_id,
        transaction_type=tx_type,
        quantity=tx_qty,
        previous_stock=prev_stock,
        new_stock=new_stock,
        reason=reason or f"Manual {adj_type.lower()} stock adjustment",
    )
    db.add(tx)

    if commit:
        db.commit()
        db.refresh(product)
    else:
        db.flush()

    return product


def get_low_stock_products(db: Session) -> List[Product]:
    """Return all active products whose stock_quantity <= low_stock_limit."""
    products = (
        db.query(Product)
        .filter(
            Product.is_deleted.is_(False),
            Product.stock_quantity <= Product.low_stock_limit,
        )
        .order_by(Product.stock_quantity.asc(), Product.product_name.asc())
        .all()
    )
    return products


def get_inventory_overview(db: Session) -> InventoryOverviewResponse:
    """Compute complete inventory valuation and health statuses using Decimal math."""
    products = (
        db.query(Product)
        .filter(Product.is_deleted.is_(False))
        .order_by(Product.product_name.asc())
        .all()
    )

    items: List[InventoryItemResponse] = []
    total_retail = Decimal("0.00")
    total_cost = Decimal("0.00")
    low_count = 0
    out_count = 0

    for p in products:
        qty = Decimal(str(p.stock_quantity))
        sell = Decimal(str(p.selling_price))
        buy = Decimal(str(p.purchase_price))
        limit = Decimal(str(p.low_stock_limit))

        retail_val = (qty * sell).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cost_val = (qty * buy).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_retail += retail_val
        total_cost += cost_val

        if qty <= Decimal("0"):
            stock_status = "OUT_OF_STOCK"
            out_count += 1
            low_count += 1
        elif qty <= limit:
            stock_status = "LOW_STOCK"
            low_count += 1
        else:
            stock_status = "IN_STOCK"

        items.append(
            InventoryItemResponse(
                product_id=p.product_id,
                product_name=p.product_name,
                tamil_name=p.tamil_name,
                category=p.category,
                barcode=p.barcode,
                purchase_price=sell if buy is None else buy,
                selling_price=sell,
                stock_quantity=qty,
                unit=p.unit,
                low_stock_limit=limit,
                is_low_stock=(qty <= limit),
                created_at=p.created_at,
                updated_at=p.updated_at,
                stock_status=stock_status,
                stock_retail_value=retail_val,
                stock_cost_value=cost_val,
            )
        )

    return InventoryOverviewResponse(
        total_products=len(products),
        low_stock_count=low_count,
        out_of_stock_count=out_count,
        total_retail_value=total_retail,
        total_cost_value=total_cost,
        items=items,
    )

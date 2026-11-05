"""POS billing, stock deduction, and sales calculation service."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.stock_transaction import StockTransaction
from app.models.user import User
from app.schemas.sale import SaleItemCreate, SaleItemResponse, SaleResponse
from app.utils.config import settings
from app.utils.tamil_lexicon import format_decimal_clean, format_money


def local_day_utc_bounds(target_date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Return UTC start and end timestamps corresponding to the local calendar day."""
    local_now = (target_date or datetime.now().astimezone()).astimezone()
    local_tz = local_now.tzinfo
    start_local = datetime.combine(local_now.date(), time.min, tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def generate_invoice_number(db: Session) -> str:
    """Generate a unique human-readable invoice number (INV-YYYYMMDD-XXXX)."""
    local_today = datetime.now().astimezone().strftime("%Y%m%d")
    prefix = f"INV-{local_today}-"
    latest = (
        db.query(Sale)
        .filter(Sale.invoice_number.like(f"{prefix}%"))
        .order_by(Sale.id.desc())
        .first()
    )
    next_seq = 1
    if latest and latest.invoice_number.startswith(prefix):
        tail = latest.invoice_number[len(prefix) :]
        if tail.isdigit():
            next_seq = int(tail) + 1
    return f"{prefix}{next_seq:04d}"


def serialize_sale(sale: Sale) -> SaleResponse:
    """Convert a Sale ORM instance into a validated SaleResponse."""
    cashier_name = sale.user.full_name if sale.user else f"User #{sale.user_id}"
    return SaleResponse(
        id=sale.id,
        invoice_number=sale.invoice_number,
        user_id=sale.user_id,
        cashier_name=cashier_name,
        total_amount=Decimal(str(sale.total_amount)),
        cash_received=Decimal(str(sale.cash_received)),
        change_amount=Decimal(str(sale.change_amount)),
        payment_method=sale.payment_method,
        source=sale.source,
        notes=sale.notes,
        created_at=sale.created_at,
        items=[
            SaleItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                unit=item.unit,
                quantity=Decimal(str(item.quantity)),
                unit_price=Decimal(str(item.unit_price)),
                subtotal=Decimal(str(item.subtotal)),
            )
            for item in sale.items
        ],
    )


def create_sale_transaction(
    db: Session,
    user: User,
    items: List[SaleItemCreate],
    cash_received: Decimal,
    payment_method: str = "CASH",
    source: str = "POS",
    notes: Optional[str] = None,
    confirm_big_amount: bool = False,
) -> Sale:
    """
    Validate stock, compute Decimal totals, enforce BIG_AMOUNT confirmation,
    deduct stock, and record Sale + SaleItems + StockTransactions atomically.
    """
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart cannot be empty.",
        )

    # Consolidate quantities if same product appears multiple times in request
    merged_quantities: OrderedDict[int, Decimal] = OrderedDict()
    for req_item in items:
        qty = Decimal(str(req_item.quantity)).quantize(Decimal("0.001"))
        if qty <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item quantity must be greater than zero.",
            )
        merged_quantities[req_item.product_id] = (
            merged_quantities.get(req_item.product_id, Decimal("0.000")) + qty
        )

    prepared_lines: List[Tuple[Product, Decimal, Decimal, Decimal]] = []
    total_amount = Decimal("0.00")

    for product_id, qty in merged_quantities.items():
        product = (
            db.query(Product)
            .filter(Product.product_id == product_id, Product.is_deleted.is_(False))
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product ID {product_id} does not exist or is unavailable.",
            )

        available_stock = Decimal(str(product.stock_quantity)).quantize(Decimal("0.001"))
        if available_stock < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for '{product.product_name}'. "
                    f"Available: {format_decimal_clean(available_stock)} {product.unit}, "
                    f"Requested: {format_decimal_clean(qty)} {product.unit}."
                ),
            )

        unit_price = Decimal(str(product.selling_price)).quantize(Decimal("0.01"))
        subtotal = (qty * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += subtotal
        prepared_lines.append((product, qty, unit_price, subtotal))

    big_threshold = Decimal(str(settings.BIG_AMOUNT)).quantize(Decimal("0.01"))
    if total_amount > big_threshold and not confirm_big_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "BIG_AMOUNT_CONFIRMATION_REQUIRED",
                "message": (
                    f"High-value transaction warning: Total bill "
                    f"{format_money(total_amount, settings.currency_symbol)} exceeds "
                    f"threshold {format_money(big_threshold, settings.currency_symbol)}. "
                    f"Please confirm to proceed."
                ),
                "total_amount": float(total_amount),
                "big_amount": float(big_threshold),
            },
        )

    cash_dec = Decimal(str(cash_received)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if cash_dec < total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient cash received ({format_money(cash_dec, settings.currency_symbol)}). "
                f"Total bill is {format_money(total_amount, settings.currency_symbol)}."
            ),
        )

    change_amount = (cash_dec - total_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    invoice_number = generate_invoice_number(db)

    try:
        sale = Sale(
            invoice_number=invoice_number,
            user_id=user.id,
            total_amount=total_amount,
            cash_received=cash_dec,
            change_amount=change_amount,
            payment_method=(payment_method or "CASH").strip().upper(),
            source=source,
            notes=notes,
        )
        db.add(sale)
        db.flush()

        for product, qty, unit_price, subtotal in prepared_lines:
            prev_stock = Decimal(str(product.stock_quantity)).quantize(Decimal("0.001"))
            new_stock = (prev_stock - qty).quantize(Decimal("0.001"))
            product.stock_quantity = new_stock

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.product_id,
                product_name=product.product_name,
                unit=product.unit,
                quantity=qty,
                unit_price=unit_price,
                subtotal=subtotal,
            )
            db.add(sale_item)

            stock_tx = StockTransaction(
                product_id=product.product_id,
                user_id=user.id,
                reference_sale_id=sale.id,
                transaction_type="SALE",
                quantity=qty,
                previous_stock=prev_stock,
                new_stock=new_stock,
                reason=f"Sale {invoice_number} ({source})",
            )
            db.add(stock_tx)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while recording sale: {exc}",
        ) from exc

    return (
        db.query(Sale)
        .options(joinedload(Sale.items), joinedload(Sale.user))
        .filter(Sale.id == sale.id)
        .first()
    )


def get_today_sales_metrics(db: Session) -> Tuple[Decimal, int]:
    """Return (today_total_sales, today_transactions_count) for the local calendar day."""
    start_utc, end_utc = local_day_utc_bounds()
    sales = (
        db.query(Sale)
        .filter(Sale.created_at >= start_utc, Sale.created_at < end_utc)
        .all()
    )
    total = sum(
        (Decimal(str(s.total_amount)) for s in sales),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    return total, len(sales)

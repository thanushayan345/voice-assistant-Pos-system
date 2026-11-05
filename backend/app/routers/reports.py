"""Reporting endpoints: dynamic dashboard KPIs, daily sales analytics, and inventory valuation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.product import Product
from app.models.sale import Sale
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.report import (
    CategoryStockBreakdown,
    DailySalesPoint,
    DailySalesReportResponse,
    DashboardReportResponse,
    InventoryReportResponse,
    TopSellingProductItem,
)
from app.services.inventory_service import get_inventory_overview, get_low_stock_products
from app.services.sales_service import get_today_sales_metrics, serialize_sale
from app.utils.config import settings
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/reports", tags=["Reports & Dashboard"])


def _to_local_date_str(dt: datetime) -> str:
    local_tz = datetime.now().astimezone().tzinfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz).strftime("%Y-%m-%d")


@router.get("/dashboard", response_model=DashboardReportResponse)
def get_dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return live dashboard statistics, low-stock alerts, and recent sales."""
    today_sales, today_tx_count = get_today_sales_metrics(db)
    inv_overview = get_inventory_overview(db)
    low_stock_products = get_low_stock_products(db)

    recent_sales_rows = (
        db.query(Sale)
        .options(joinedload(Sale.items), joinedload(Sale.user))
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(8)
        .all()
    )

    return DashboardReportResponse(
        currency=settings.CURRENCY,
        currency_symbol=settings.currency_symbol,
        today_total_sales=today_sales,
        today_transactions_count=today_tx_count,
        total_products=inv_overview.total_products,
        total_stock_value=inv_overview.total_retail_value,
        total_stock_cost_value=inv_overview.total_cost_value,
        low_stock_count=inv_overview.low_stock_count,
        recent_sales=[serialize_sale(s) for s in recent_sales_rows],
        low_stock_products=[ProductResponse.model_validate(p) for p in low_stock_products],
    )


@router.get("/daily-sales", response_model=DailySalesReportResponse)
def get_daily_sales_report(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return day-by-day sales totals, source breakdown, profit estimate, and top-selling items."""
    local_now = datetime.now().astimezone()
    local_tz = local_now.tzinfo
    start_local_date = local_now.date() - timedelta(days=days - 1)
    start_utc = datetime.combine(start_local_date, time.min, tzinfo=local_tz).astimezone(
        timezone.utc
    )

    sales = (
        db.query(Sale)
        .options(joinedload(Sale.items))
        .filter(Sale.created_at >= start_utc)
        .order_by(Sale.created_at.asc())
        .all()
    )

    # Map product purchase prices for gross profit estimation
    product_cost_map: Dict[int, Decimal] = {
        p.product_id: Decimal(str(p.purchase_price))
        for p in db.query(Product).all()
    }

    day_buckets: Dict[str, Dict[str, object]] = {}
    for offset in range(days):
        d_str = (start_local_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        day_buckets[d_str] = {
            "sales_count": 0,
            "total_amount": Decimal("0.00"),
            "pos_sales_count": 0,
            "voice_sales_count": 0,
        }

    period_total = Decimal("0.00")
    estimated_profit = Decimal("0.00")
    product_agg: Dict[int, Dict[str, object]] = {}

    for sale in sales:
        sale_total = Decimal(str(sale.total_amount)).quantize(Decimal("0.01"))
        period_total += sale_total
        d_key = _to_local_date_str(sale.created_at)
        if d_key in day_buckets:
            bucket = day_buckets[d_key]
            bucket["sales_count"] = int(bucket["sales_count"]) + 1
            bucket["total_amount"] = Decimal(str(bucket["total_amount"])) + sale_total
            if sale.source == "VOICE":
                bucket["voice_sales_count"] = int(bucket["voice_sales_count"]) + 1
            else:
                bucket["pos_sales_count"] = int(bucket["pos_sales_count"]) + 1

        for item in sale.items:
            qty = Decimal(str(item.quantity))
            sub = Decimal(str(item.subtotal))
            buy_cost = product_cost_map.get(item.product_id, Decimal("0.00"))
            item_profit = (sub - (qty * buy_cost)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            estimated_profit += item_profit

            if item.product_id not in product_agg:
                product_agg[item.product_id] = {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "unit": item.unit,
                    "qty": Decimal("0.000"),
                    "rev": Decimal("0.00"),
                }
            product_agg[item.product_id]["qty"] = (
                Decimal(str(product_agg[item.product_id]["qty"])) + qty
            )
            product_agg[item.product_id]["rev"] = (
                Decimal(str(product_agg[item.product_id]["rev"])) + sub
            )

    tx_count = len(sales)
    avg_sale = (
        (period_total / Decimal(tx_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if tx_count > 0
        else Decimal("0.00")
    )

    daily_breakdown: List[DailySalesPoint] = [
        DailySalesPoint(
            date=d_str,
            sales_count=int(vals["sales_count"]),
            total_amount=Decimal(str(vals["total_amount"])),
            pos_sales_count=int(vals["pos_sales_count"]),
            voice_sales_count=int(vals["voice_sales_count"]),
        )
        for d_str, vals in day_buckets.items()
    ]

    sorted_top = sorted(
        product_agg.values(),
        key=lambda x: Decimal(str(x["rev"])),
        reverse=True,
    )[:10]

    top_products = [
        TopSellingProductItem(
            product_id=int(p["product_id"]),
            product_name=str(p["product_name"]),
            unit=str(p["unit"]),
            total_quantity_sold=Decimal(str(p["qty"])),
            total_revenue=Decimal(str(p["rev"])),
        )
        for p in sorted_top
    ]

    return DailySalesReportResponse(
        currency=settings.CURRENCY,
        currency_symbol=settings.currency_symbol,
        days=days,
        period_total_sales=period_total,
        period_transactions_count=tx_count,
        average_sale_value=avg_sale,
        estimated_gross_profit=estimated_profit,
        daily_breakdown=daily_breakdown,
        top_products=top_products,
    )


@router.get("/inventory", response_model=InventoryReportResponse)
def get_inventory_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return category-level stock valuation, margin potential, and low-stock breakdown."""
    overview = get_inventory_overview(db)
    low_items = get_low_stock_products(db)

    cat_map: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "product_count": 0,
            "low_stock_count": 0,
            "retail_value": Decimal("0.00"),
            "cost_value": Decimal("0.00"),
        }
    )

    for item in overview.items:
        entry = cat_map[item.category]
        entry["product_count"] = int(entry["product_count"]) + 1
        if item.is_low_stock:
            entry["low_stock_count"] = int(entry["low_stock_count"]) + 1
        entry["retail_value"] = Decimal(str(entry["retail_value"])) + Decimal(
            str(item.stock_retail_value)
        )
        entry["cost_value"] = Decimal(str(entry["cost_value"])) + Decimal(
            str(item.stock_cost_value)
        )

    categories = [
        CategoryStockBreakdown(
            category=cat_name,
            product_count=int(vals["product_count"]),
            low_stock_count=int(vals["low_stock_count"]),
            retail_value=Decimal(str(vals["retail_value"])),
            cost_value=Decimal(str(vals["cost_value"])),
        )
        for cat_name, vals in sorted(cat_map.items(), key=lambda kv: kv[0])
    ]

    margin = (
        Decimal(str(overview.total_retail_value))
        - Decimal(str(overview.total_cost_value))
    ).quantize(Decimal("0.01"))

    return InventoryReportResponse(
        currency=settings.CURRENCY,
        currency_symbol=settings.currency_symbol,
        total_products=overview.total_products,
        low_stock_count=overview.low_stock_count,
        out_of_stock_count=overview.out_of_stock_count,
        total_retail_value=overview.total_retail_value,
        total_cost_value=overview.total_cost_value,
        estimated_potential_margin=margin,
        categories=categories,
        low_stock_items=[ProductResponse.model_validate(p) for p in low_items],
    )

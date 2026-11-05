"""Dashboard, daily sales, and inventory report Pydantic schemas."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.schemas.common import MoneyDecimal, QtyDecimal
from app.schemas.product import ProductResponse
from app.schemas.sale import SaleResponse


class DashboardReportResponse(BaseModel):
    currency: str
    currency_symbol: str
    today_total_sales: MoneyDecimal
    today_transactions_count: int
    total_products: int
    total_stock_value: MoneyDecimal
    total_stock_cost_value: MoneyDecimal
    low_stock_count: int
    recent_sales: List[SaleResponse]
    low_stock_products: List[ProductResponse]


class DailySalesPoint(BaseModel):
    date: str
    sales_count: int
    total_amount: MoneyDecimal
    pos_sales_count: int
    voice_sales_count: int


class TopSellingProductItem(BaseModel):
    product_id: int
    product_name: str
    unit: str
    total_quantity_sold: QtyDecimal
    total_revenue: MoneyDecimal


class DailySalesReportResponse(BaseModel):
    currency: str
    currency_symbol: str
    days: int
    period_total_sales: MoneyDecimal
    period_transactions_count: int
    average_sale_value: MoneyDecimal
    estimated_gross_profit: MoneyDecimal
    daily_breakdown: List[DailySalesPoint]
    top_products: List[TopSellingProductItem]


class CategoryStockBreakdown(BaseModel):
    category: str
    product_count: int
    low_stock_count: int
    retail_value: MoneyDecimal
    cost_value: MoneyDecimal


class InventoryReportResponse(BaseModel):
    currency: str
    currency_symbol: str
    total_products: int
    low_stock_count: int
    out_of_stock_count: int
    total_retail_value: MoneyDecimal
    total_cost_value: MoneyDecimal
    estimated_potential_margin: MoneyDecimal
    categories: List[CategoryStockBreakdown]
    low_stock_items: List[ProductResponse]

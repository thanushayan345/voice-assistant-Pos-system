"""Database initialization and hackathon sample seed data."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401 - register models on Base.metadata
from app.models.product import Product
from app.models.stock_transaction import StockTransaction
from app.models.user import User
from app.utils.config import settings
from app.utils.security import hash_password

logger = logging.getLogger("tamil_voice_pos.seed")


SAMPLE_PRODUCTS = [
    {
        "product_name": "Rice",
        "tamil_name": "அரிசி",
        "category": "Grains & Staples",
        "barcode": "890100100001",
        "purchase_price": Decimal("210.00"),
        "selling_price": Decimal("250.00"),
        "stock_quantity": Decimal("50.000"),
        "unit": "Kilograms",
    },
    {
        "product_name": "Sugar",
        "tamil_name": "சர்க்கரை / சீனி",
        "category": "Groceries",
        "barcode": "890100100002",
        "purchase_price": Decimal("240.00"),
        "selling_price": Decimal("280.00"),
        "stock_quantity": Decimal("30.000"),
        "unit": "Kilograms",
    },
    {
        "product_name": "Milk",
        "tamil_name": "பால்",
        "category": "Dairy & Beverages",
        "barcode": "890100100003",
        "purchase_price": Decimal("165.00"),
        "selling_price": Decimal("200.00"),
        "stock_quantity": Decimal("15.000"),
        "unit": "Litres",
    },
    {
        "product_name": "Soap",
        "tamil_name": "சோப்பு",
        "category": "Personal Care",
        "barcode": "890100100004",
        "purchase_price": Decimal("115.00"),
        "selling_price": Decimal("150.00"),
        "stock_quantity": Decimal("8.000"),
        "unit": "Pieces",
    },
    {
        "product_name": "Tea",
        "tamil_name": "தேயிலை",
        "category": "Beverages",
        "barcode": "890100100005",
        "purchase_price": Decimal("980.00"),
        "selling_price": Decimal("1200.00"),
        "stock_quantity": Decimal("4.000"),
        "unit": "Kilograms",
    },
]


def seed_initial_data(db: Session) -> None:
    """Seed default demo owner user and hackathon sample products when empty."""
    owner = db.query(User).filter(User.username == "admin").first()
    if not owner:
        owner = User(
            username="admin",
            full_name="Shop Owner (Demo)",
            email="owner@tamilvoicepos.lk",
            hashed_password=hash_password("admin123"),
            role="owner",
            is_active=True,
        )
        db.add(owner)
        db.flush()
        logger.info("Seeded default demo account: username='admin'")

    existing_count = db.query(Product).count()
    if existing_count == 0:
        default_limit = Decimal(str(settings.LOW_STOCK_DEFAULT))
        for item in SAMPLE_PRODUCTS:
            product = Product(
                product_name=item["product_name"],
                tamil_name=item["tamil_name"],
                category=item["category"],
                barcode=item["barcode"],
                purchase_price=item["purchase_price"],
                selling_price=item["selling_price"],
                stock_quantity=item["stock_quantity"],
                unit=item["unit"],
                low_stock_limit=default_limit,
                is_deleted=False,
            )
            db.add(product)
            db.flush()

            tx = StockTransaction(
                product_id=product.product_id,
                user_id=owner.id if owner else None,
                transaction_type="INITIAL",
                quantity=item["stock_quantity"],
                previous_stock=Decimal("0.000"),
                new_stock=item["stock_quantity"],
                reason="Initial hackathon demo inventory seed",
            )
            db.add(tx)

        logger.info("Seeded %d hackathon sample products.", len(SAMPLE_PRODUCTS))

    db.commit()


def init_db() -> None:
    """Create tables and run initial idempotent seed."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    except Exception:
        db.rollback()
        logger.exception("Error seeding initial data")
        raise
    finally:
        db.close()

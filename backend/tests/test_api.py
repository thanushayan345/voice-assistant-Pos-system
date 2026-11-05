"""End-to-end automated API tests for Tamil Voice POS backend."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Point tests at an isolated temporary SQLite file before importing app
_TEMP_DB_FD, _TEMP_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TEMP_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEMP_DB_PATH.replace(chr(92), '/')}"

from app.main import app  # noqa: E402
from app.schemas.voice import GeminiStructuredIntent  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    try:
        os.remove(_TEMP_DB_PATH)
    except OSError:
        pass


def _auth_headers(client: TestClient, username: str = "admin", password: str = "admin123") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_public_config_hides_api_key(client: TestClient):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "LKR"
    assert body["currency_symbol"] == "Rs."
    assert body["low_stock_default"] == 5
    assert body["big_amount"] == 50000
    assert "GEMINI_API_KEY" not in body
    assert "gemini_api_key" not in body


def test_auth_flow_and_sample_seed(client: TestClient):
    headers = _auth_headers(client)
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"

    prod_resp = client.get("/api/products", headers=headers)
    assert prod_resp.status_code == 200
    products = prod_resp.json()
    assert len(products) == 5
    by_name = {p["product_name"]: p for p in products}
    assert by_name["Rice"]["selling_price"] == 250
    assert by_name["Rice"]["stock_quantity"] == 50
    assert by_name["Sugar"]["selling_price"] == 280
    assert by_name["Milk"]["selling_price"] == 200
    assert by_name["Soap"]["selling_price"] == 150
    assert by_name["Tea"]["selling_price"] == 1200
    assert by_name["Tea"]["stock_quantity"] == 4
    assert by_name["Tea"]["is_low_stock"] is True


def test_hackathon_voice_scenarios_with_confirmation(client: TestClient):
    headers = _auth_headers(client)

    # Scenario 1: Owner checks rice stock using Tamil voice
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="CHECK_STOCK",
                product_name="Rice",
                spoken_product_term="அரிசி",
                confidence=0.98,
                response_language="ta",
            ),
            '{"intent":"CHECK_STOCK"}',
        )
        r1 = client.post(
            "/api/voice/process",
            json={"transcript": "கடையில் எவ்வளவு அரிசி இருக்கு?", "language": "ta-LK"},
            headers=headers,
        )
        assert r1.status_code == 200
        b1 = r1.json()
        assert b1["intent"] == "CHECK_STOCK"
        assert b1["requires_confirmation"] is False
        assert "50" in b1["response_text"]

    # Scenario 2: Owner adds 20 bags of rice -> Pending -> Confirm -> Stock becomes 70
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="ADD_STOCK",
                product_name="Rice",
                spoken_product_term="அரிசி",
                quantity=20,
                unit="bags",
                confidence=0.96,
                response_language="ta",
            ),
            '{"intent":"ADD_STOCK"}',
        )
        r2 = client.post(
            "/api/voice/process",
            json={"transcript": "அரிசி 20 மூட்டை சேர்க்கவும்", "language": "ta-LK"},
            headers=headers,
        )
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["requires_confirmation"] is True
        token = b2["confirmation_token"]
        assert token

        # Verify DB NOT modified before confirmation
        rice_before = [
            p for p in client.get("/api/products?search=Rice", headers=headers).json()
            if p["product_name"] == "Rice"
        ][0]
        assert rice_before["stock_quantity"] == 50

        # Confirm operation
        c2 = client.post(
            "/api/voice/confirm",
            json={"confirmation_token": token},
            headers=headers,
        )
        assert c2.status_code == 200
        assert c2.json()["status"] == "CONFIRMED"
        assert c2.json()["data"]["product"]["stock_quantity"] == 70

    # Scenario 3: Owner sells 2 kg of sugar -> Pending -> Confirm -> Sugar becomes 28, sale Rs. 560
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="RECORD_SALE",
                product_name="Sugar",
                spoken_product_term="சர்க்கரை",
                quantity=2,
                unit="kg",
                confidence=0.97,
                response_language="ta",
            ),
            '{"intent":"RECORD_SALE"}',
        )
        r3 = client.post(
            "/api/voice/process",
            json={"transcript": "இரண்டு கிலோ சர்க்கரை விற்றேன்", "language": "ta-LK"},
            headers=headers,
        )
        assert r3.status_code == 200
        sale_token = r3.json()["confirmation_token"]
        c3 = client.post(
            "/api/voice/confirm",
            json={"confirmation_token": sale_token},
            headers=headers,
        )
        assert c3.status_code == 200
        assert c3.json()["data"]["sale"]["total_amount"] == 560
        assert c3.json()["data"]["product"]["stock_quantity"] == 28

    # Scenario 4: Owner checks today's total sales
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="GET_TODAY_SALES",
                confidence=0.99,
                response_language="ta",
            ),
            '{"intent":"GET_TODAY_SALES"}',
        )
        r4 = client.post(
            "/api/voice/process",
            json={"transcript": "இன்றைய விற்பனை எவ்வளவு?", "language": "ta-LK"},
            headers=headers,
        )
        assert r4.status_code == 200
        assert r4.json()["data"]["today_total_sales"] == 560

    # Scenario 5: Owner asks which products are running low -> Tea (4 kg)
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="CHECK_LOW_STOCK",
                confidence=0.99,
                response_language="ta",
            ),
            '{"intent":"CHECK_LOW_STOCK"}',
        )
        r5 = client.post(
            "/api/voice/process",
            json={"transcript": "கடையில் எந்த பொருட்கள் குறைவாக இருக்கு?", "language": "ta-LK"},
            headers=headers,
        )
        assert r5.status_code == 200
        assert r5.json()["data"]["low_stock_count"] >= 1
        low_names = [p["product_name"] for p in r5.json()["data"]["products"]]
        assert "Tea" in low_names


def test_product_crud_and_pos_billing_and_big_amount(client: TestClient):
    headers = _auth_headers(client)

    # Scenario 6: Owner adds a new product using the application
    new_prod_resp = client.post(
        "/api/products",
        json={
            "product_name": "Coconut Oil",
            "tamil_name": "தேங்காய் எண்ணெய்",
            "category": "Groceries",
            "purchase_price": 750,
            "selling_price": 900,
            "stock_quantity": 100,
            "unit": "Bottles",
            "low_stock_limit": 5,
        },
        headers=headers,
    )
    assert new_prod_resp.status_code == 201
    oil_id = new_prod_resp.json()["product_id"]

    # Scenario 7: Owner generates a bill using POS (2 Bottles of Coconut Oil = Rs. 1,800, Cash Rs. 2,000 -> Change Rs. 200)
    sale_resp = client.post(
        "/api/sales",
        json={
            "items": [{"product_id": oil_id, "quantity": 2}],
            "cash_received": 2000,
            "payment_method": "CASH",
        },
        headers=headers,
    )
    assert sale_resp.status_code == 201
    sale_body = sale_resp.json()
    assert sale_body["total_amount"] == 1800
    assert sale_body["change_amount"] == 200

    # Test BIG_AMOUNT (> 50,000) requires confirm_big_amount=True
    big_sale_unconfirmed = client.post(
        "/api/sales",
        json={
            "items": [{"product_id": oil_id, "quantity": 60}],  # 60 * 900 = Rs. 54,000
            "cash_received": 55000,
            "confirm_big_amount": False,
        },
        headers=headers,
    )
    assert big_sale_unconfirmed.status_code == 409
    assert big_sale_unconfirmed.json()["detail"]["code"] == "BIG_AMOUNT_CONFIRMATION_REQUIRED"

    big_sale_confirmed = client.post(
        "/api/sales",
        json={
            "items": [{"product_id": oil_id, "quantity": 60}],
            "cash_received": 55000,
            "confirm_big_amount": True,
        },
        headers=headers,
    )
    assert big_sale_confirmed.status_code == 201
    assert big_sale_confirmed.json()["total_amount"] == 54000
    assert big_sale_confirmed.json()["change_amount"] == 1000

    # Test insufficient stock blocked
    insufficient_resp = client.post(
        "/api/sales",
        json={
            "items": [{"product_id": oil_id, "quantity": 500}],
            "cash_received": 500000,
            "confirm_big_amount": True,
        },
        headers=headers,
    )
    assert insufficient_resp.status_code == 400

    # Dashboard dynamic check
    dash = client.get("/api/reports/dashboard", headers=headers)
    assert dash.status_code == 200
    assert Decimal(str(dash.json()["today_total_sales"])) == Decimal("56360.00")

    # Daily sales & inventory reports check
    daily = client.get("/api/reports/daily-sales?days=7", headers=headers)
    assert daily.status_code == 200
    assert Decimal(str(daily.json()["period_total_sales"])) == Decimal("56360.00")
    assert len(daily.json()["top_products"]) >= 2

    inv_rep = client.get("/api/reports/inventory", headers=headers)
    assert inv_rep.status_code == 200
    assert inv_rep.json()["total_products"] == 6


def test_security_cancellation_and_edge_cases(client: TestClient):
    headers_admin = _auth_headers(client)

    # Register second staff user
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "username": "staff1",
            "full_name": "Kumaran Staff",
            "password": "password123",
            "role": "staff",
        },
    )
    assert reg_resp.status_code == 201
    staff_token = reg_resp.json()["access_token"]
    headers_staff = {"Authorization": f"Bearer {staff_token}"}

    # Admin creates pending voice stock reduction
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="REDUCE_STOCK",
                product_name="Soap",
                spoken_product_term="சோப்பு",
                quantity=2,
                unit="Pieces",
                confidence=0.95,
                response_language="ta",
            ),
            '{"intent":"REDUCE_STOCK"}',
        )
        pending_resp = client.post(
            "/api/voice/process",
            json={"transcript": "சோப்பு 2 துண்டு குறைக்கவும்", "language": "ta-LK"},
            headers=headers_admin,
        )
        assert pending_resp.status_code == 200
        tok = pending_resp.json()["confirmation_token"]

    # Staff user MUST NOT be allowed to confirm Admin's pending operation
    cross_confirm = client.post(
        "/api/voice/confirm",
        json={"confirmation_token": tok},
        headers=headers_staff,
    )
    assert cross_confirm.status_code == 404

    # Admin cancels operation -> stock remains 8
    cancel_resp = client.post(
        "/api/voice/cancel",
        json={"confirmation_token": tok},
        headers=headers_admin,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    soap = [
        p for p in client.get("/api/products?search=Soap", headers=headers_admin).json()
        if p["product_name"] == "Soap"
    ][0]
    assert soap["stock_quantity"] == 8

    # Missing quantity must NEVER assume a quantity
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            GeminiStructuredIntent(
                intent="ADD_STOCK",
                product_name="Milk",
                spoken_product_term="பால்",
                quantity=None,
                confidence=0.9,
                response_language="ta",
            ),
            '{"intent":"ADD_STOCK"}',
        )
        missing_qty_resp = client.post(
            "/api/voice/process",
            json={"transcript": "பால் சேர்க்கவும்", "language": "ta-LK"},
            headers=headers_admin,
        )
        assert missing_qty_resp.status_code == 200
        assert missing_qty_resp.json()["requires_confirmation"] is False

    # Unconfigured Gemini API key returns clear 503 error while manual inventory still works
    from app.utils.config import settings as app_settings

    with (
        patch("app.services.gemini_service.refresh_runtime_env"),
        patch.object(app_settings, "GEMINI_API_KEY", ""),
    ):
        unconf = client.post(
            "/api/voice/process",
            json={"transcript": "How much milk is available?", "language": "en-US"},
            headers=headers_admin,
        )
        assert unconf.status_code == 503
        assert unconf.json()["detail"]["code"] == "GEMINI_API_KEY_MISSING"

    # Manual inventory adjust & logout revocation check
    adj = client.post(
        "/api/inventory/adjust",
        json={
            "product_id": soap["product_id"],
            "adjustment_type": "ADD",
            "quantity": 4,
            "reason": "Restocked soap",
        },
        headers=headers_staff,
    )
    assert adj.status_code == 200
    assert adj.json()["stock_quantity"] == 12

    logout_resp = client.post("/api/auth/logout", headers=headers_staff)
    assert logout_resp.status_code == 200
    after_logout = client.get("/api/auth/me", headers=headers_staff)
    assert after_logout.status_code == 401


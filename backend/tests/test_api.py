"""End-to-end automated API tests for Local Ollama (qwen2.5:3b) Voice POS backend."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

_TEMP_DB_FD, _TEMP_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TEMP_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEMP_DB_PATH.replace(chr(92), '/')}"

from app.main import app  # noqa: E402
from app.schemas.voice import AIStructuredIntent  # noqa: E402


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


def test_public_config_uses_local_ollama(client: TestClient):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_provider"] == "ollama"
    assert body["ollama_model"] == "qwen2.5:3b"
    assert body["ollama_base_url"] == "http://127.0.0.1:11434"
    assert body["currency"] == "LKR"
    assert body["currency_symbol"] == "Rs."


def test_voice_scenarios_with_confirmation_and_ollama_offline_graceful(client: TestClient):
    headers = _auth_headers(client)

    # Check Rice stock
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            AIStructuredIntent(
                intent="CHECK_STOCK",
                product_name="Rice",
                spoken_product_term="அரிசி",
                confidence=0.98,
            ),
            '{"intent":"CHECK_STOCK"}',
        )
        r1 = client.post(
            "/api/voice/process",
            json={"transcript": "கடையில் எவ்வளவு அரிசி இருக்கு?", "language": "ta-LK"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["intent"] == "CHECK_STOCK"
        assert "50" in r1.json()["response_text"]

    # Add 20 bags of Rice -> Pending -> Confirm
    with patch("app.routers.voice.interpret_voice_command") as mock_ai:
        mock_ai.return_value = (
            AIStructuredIntent(
                intent="ADD_STOCK",
                product_name="Rice",
                quantity=20,
                unit="Bags",
                confidence=0.96,
            ),
            '{"intent":"ADD_STOCK"}',
        )
        r2 = client.post(
            "/api/voice/process",
            json={"transcript": "Add 20 bags of rice", "language": "en-US"},
            headers=headers,
        )
        assert r2.status_code == 200
        token = r2.json()["confirmation_token"]
        assert r2.json()["requires_confirmation"] is True

        c2 = client.post(
            "/api/voice/confirm",
            json={"confirmation_token": token},
            headers=headers,
        )
        assert c2.status_code == 200
        assert c2.json()["data"]["product"]["stock_quantity"] == 70

    # Ollama connection failure returns graceful 503 while manual POS continues working
    with patch(
        "app.services.ollama_service.ollama.Client.chat",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        offline_resp = client.post(
            "/api/voice/process",
            json={"transcript": "How much milk is available?", "language": "en-US"},
            headers=headers,
        )
        assert offline_resp.status_code == 503
        assert offline_resp.json()["detail"]["code"] == "OLLAMA_UNAVAILABLE"

    # Manual POS still works when Ollama is offline
    products_list = client.get("/api/products", headers=headers).json()
    rice_id = [p["product_id"] for p in products_list if p["product_name"] == "Rice"][0]
    sale_resp = client.post(
        "/api/sales",
        json={
            "items": [{"product_id": rice_id, "quantity": 2}],
            "cash_received": 500,
            "payment_method": "CASH",
        },
        headers=headers,
    )
    assert sale_resp.status_code == 201
    assert Decimal(str(sale_resp.json()["total_amount"])) == Decimal("500.00")


def test_system_maintenance_mode_and_feature_flags_503(client: TestClient):
    admin_headers = _auth_headers(client)

    # Register a staff user and confirm 403 Forbidden on PUT /api/system/status
    reg = client.post(
        "/api/auth/register",
        json={
            "username": "staff_cashier",
            "password": "password123",
            "full_name": "Staff Cashier",
            "role": "staff",
        },
    )
    assert reg.status_code in (200, 201)
    staff_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    denied = client.put(
        "/api/system/status",
        json={"maintenance": True},
        headers=staff_headers,
    )
    assert denied.status_code == 403

    # Admin enables blocking maintenance with sanitized message
    enabled = client.put(
        "/api/system/status",
        json={
            "maintenance": True,
            "blocking": True,
            "message": "Scheduled upgrade <script>alert(1)</script> sqlite:///pos.db",
            "estimatedTime": "20 minutes",
        },
        headers=admin_headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["maintenance"] is True
    assert "<script>" not in enabled.json()["message"]
    assert "sqlite:///" not in enabled.json()["message"]

    # Protected API returns HTTP 503 Service Unavailable for staff while /api/system/status stays 200
    blocked_resp = client.get("/api/products", headers=staff_headers)
    assert blocked_resp.status_code == 503
    assert blocked_resp.json()["detail"]["code"] == "MAINTENANCE_MODE"
    assert client.get("/api/system/status").status_code == 200

    # Restore normal mode, disable voiceAssistant feature flag -> /api/voice/history returns 503
    flag_resp = client.put(
        "/api/system/status",
        json={
            "maintenance": False,
            "blocking": False,
            "features": {
                "posBilling": True,
                "voiceAssistant": False,
                "productManagement": True,
                "inventoryAdjustments": True,
                "reportsAnalytics": True,
            },
        },
        headers=admin_headers,
    )
    assert flag_resp.status_code == 200
    voice_disabled = client.get("/api/voice/history", headers=staff_headers)
    assert voice_disabled.status_code == 503
    assert voice_disabled.json()["detail"]["code"] == "FEATURE_DISABLED"

    # Re-enable all features
    reset_resp = client.put(
        "/api/system/status",
        json={
            "maintenance": False,
            "blocking": False,
            "features": {
                "posBilling": True,
                "voiceAssistant": True,
                "productManagement": True,
                "inventoryAdjustments": True,
                "reportsAnalytics": True,
            },
        },
        headers=admin_headers,
    )
    assert reset_resp.status_code == 200

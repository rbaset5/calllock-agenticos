"""Integration tests for voice tool router."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    return TestClient(app)


def _sign_body(body: bytes, secret: str = "test-api-key") -> str:
    """Generate a Retell SDK-compatible signature header."""
    timestamp_ms = int(time.time() * 1000)
    message = body + str(timestamp_ms).encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v={timestamp_ms},d={digest}"


class TestLookupCallerEndpoint:
    def test_valid_request_returns_result(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "lookup_caller",
            "args": {"phone_number": "+15125550101"},
            "call": {
                "call_id": "ret-001",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        with patch("voice.router.lookup_caller", return_value={"found": False, "jobs": [], "calls": [], "bookings": []}):
            response = client.post(
                "/webhook/retell/lookup_caller",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "found" in data

    def test_missing_phone_returns_not_found(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "lookup_caller",
            "args": {},
            "call": {
                "call_id": "ret-002",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/lookup_caller",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json()["found"] is False

    def test_invalid_hmac_returns_401(self, client: TestClient) -> None:
        body = json.dumps({
            "call_id": "ret-003",
            "args": {"phone_number": "+15125550101"},
            "metadata": {"tenant_id": "tenant-test"},
        }).encode()

        response = client.post(
            "/webhook/retell/lookup_caller",
            content=body,
            headers={
                "x-retell-signature": "bad-signature",
                "content-type": "application/json",
            },
        )

        assert response.status_code == 401


class TestCreateCallbackEndpoint:
    def test_returns_success(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "create_callback_request",
            "args": {
                "caller_phone": "+15125550101",
                "reason": "AC not cooling",
                "callback_minutes": 30,
            },
            "call": {
                "call_id": "ret-010",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/create_callback",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestSalesLeadAlertEndpoint:
    def test_returns_success(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "send_sales_lead_alert",
            "args": {
                "equipment": "Central AC",
                "customer_name": "John Smith",
                "customer_phone": "+15125550101",
                "address": "123 Oak St",
            },
            "call": {
                "call_id": "ret-020",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/send_sales_lead_alert",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

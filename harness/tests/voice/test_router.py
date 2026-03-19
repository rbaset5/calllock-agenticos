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


def _sign_body(body: bytes, api_key: str = "test-api-key") -> str:
    """Generate Retell-format combined signature header."""
    ts_ms = int(time.time() * 1000)
    message = body + str(ts_ms).encode()
    digest = hmac.new(api_key.encode(), message, hashlib.sha256).hexdigest()
    return f"v={ts_ms},d={digest}"


class TestLookupCallerEndpoint:
    def test_valid_request_returns_result(self, client: TestClient) -> None:
        body = json.dumps({
            "call_id": "ret-001",
            "tool_name": "lookup_caller",
            "args": {"phone_number": "+15125550101"},
            "metadata": {"tenant_id": "tenant-test"},
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
            "call_id": "ret-002",
            "tool_name": "lookup_caller",
            "args": {},
            "metadata": {"tenant_id": "tenant-test"},
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
                "x-retell-signature": "v=123,d=bad-digest",
                "content-type": "application/json",
            },
        )

        assert response.status_code == 401

    def test_nested_retell_format(self, client: TestClient) -> None:
        """Retell's current format: { name, args, call: { call_id, metadata } }."""
        body = json.dumps({
            "name": "lookup_caller",
            "args": {"phone_number": "+15125550101"},
            "call": {
                "call_id": "ret-004",
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
        assert "found" in response.json()


class TestCreateCallbackEndpoint:
    def test_returns_success(self, client: TestClient) -> None:
        body = json.dumps({
            "call_id": "ret-010",
            "tool_name": "create_callback",
            "args": {
                "caller_phone": "+15125550101",
                "reason": "AC not cooling",
                "callback_minutes": 30,
            },
            "metadata": {"tenant_id": "tenant-test"},
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
            "call_id": "ret-020",
            "tool_name": "send_sales_lead_alert",
            "args": {
                "equipment": "Central AC",
                "customer_name": "John Smith",
                "customer_phone": "+15125550101",
                "address": "123 Oak St",
            },
            "metadata": {"tenant_id": "tenant-test"},
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

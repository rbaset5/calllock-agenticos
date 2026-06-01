"""Integration tests for voice tool router."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_missing_retell_api_key_returns_401(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("RETELL_API_KEY", raising=False)
        body = json.dumps({
            "call_id": "ret-004",
            "args": {"phone_number": "+15125550101"},
            "metadata": {"tenant_id": "tenant-test"},
        }).encode()

        response = client.post(
            "/webhook/retell/lookup_caller",
            content=body,
            headers={
                "x-retell-signature": "v=1,d=sig",
                "content-type": "application/json",
            },
        )

        assert response.status_code == 401


class TestInboundEndpoint:
    @pytest.mark.parametrize("to_number", ["+13126463816", "+13126463826"])
    def test_maps_live_retell_number_to_tenant(self, client: TestClient, to_number: str) -> None:
        body = json.dumps({
            "agent_id": "agent-test",
            "to_number": to_number,
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/inbound",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "metadata": {"tenant_id": "e51d9ae7-9cde-4dca-a49c-4744c39240bc"}
        }


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


class TestBookServiceEndpoint:
    def test_returns_booking_result(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "book_service",
            "args": {
                "customer_name": "Jane Doe",
                "customer_phone": "+15125550101",
                "service_address": "123 Oak St, Austin TX 78701",
                "zip_code": "78701",
                "preferred_time": "2026-06-02T15:00:00-04:00",
                "issue_description": "AC not cooling",
                "urgency_tier": "urgent",
            },
            "call": {
                "call_id": "ret-030",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        with patch("voice.router.book_service", new_callable=AsyncMock, return_value={
            "success": True,
            "booking_confirmed": True,
            "booking_id": "cal-001",
        }) as mock_book_service:
            response = client.post(
                "/webhook/retell/book_service",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["booking_confirmed"] is True
        assert data["booking_id"] == "cal-001"
        assert mock_book_service.await_args.kwargs["zip_code"] == "78701"


class TestFallbackAndServiceAreaEndpoints:
    def test_route_call_fallback_returns_policy_decision(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "route_call_fallback",
            "args": {
                "urgency_tier": "emergency",
                "route": "legitimate",
                "business_open": False,
                "caller_requested_human": False,
                "booking_failed": False,
                "confidence": 0.95,
                "live_transfer_enabled": True,
                "callback_tasks_enabled": True,
                "voicemail_enabled": True,
                "default_transfer_number": "+15125550001",
                "emergency_transfer_number": "+15125559111",
                "voicemail_number": "+15125559999",
            },
            "call": {
                "call_id": "ret-040",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/route_call_fallback",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "transfer"
        assert data["target_number"] == "+15125559111"
        assert data["backup_action"] == "callback_task"

    def test_route_call_fallback_parses_string_booleans(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "route_call_fallback",
            "args": {
                "urgency_tier": "emergency",
                "route": "legitimate",
                "live_transfer_enabled": "false",
                "callback_tasks_enabled": "true",
                "voicemail_enabled": "false",
                "emergency_transfer_number": "+15125559111",
            },
            "call": {
                "call_id": "ret-040b",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        response = client.post(
            "/webhook/retell/route_call_fallback",
            content=body,
            headers={
                "x-retell-signature": sig,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "callback_task"
        assert data["target_number"] is None

    def test_validate_service_area_uses_tenant_voice_config(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "validate_service_area",
            "args": {"service_address": "123 Oak St, Austin TX 78701"},
            "call": {
                "call_id": "ret-041",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        with patch("voice.router._resolve_config") as mock_resolve:
            mock_resolve.return_value.service_area_zips = ["78701", "78702"]
            response = client.post(
                "/webhook/retell/validate_service_area",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"in_service_area": True, "zip_code": "78701"}

    def test_validate_service_area_accepts_direct_zip_code(self, client: TestClient) -> None:
        body = json.dumps({
            "name": "validate_service_area",
            "args": {"zip_code": "78702"},
            "call": {
                "call_id": "ret-042",
                "metadata": {"tenant_id": "tenant-test"},
            },
        }).encode()
        sig = _sign_body(body)

        with patch("voice.router._resolve_config") as mock_resolve:
            mock_resolve.return_value.service_area_zips = ["78701", "78702"]
            response = client.post(
                "/webhook/retell/validate_service_area",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"in_service_area": True, "zip_code": "78702"}

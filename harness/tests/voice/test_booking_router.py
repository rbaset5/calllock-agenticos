"""Tests for the booking management REST API router."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    return TestClient(app)


def _api_key_header(key: str = "test-api-key") -> dict[str, str]:
    return {"X-API-Key": key}


def _mock_api_key_records(key: str = "test-api-key", tenant_id: str = "tenant-ace-001") -> list[dict]:
    return [
        {
            "api_key_hash": hashlib.sha256(key.encode()).hexdigest(),
            "tenant_id": tenant_id,
            "revoked_at": None,
        }
    ]


class TestBookingLookup:
    def test_valid_lookup(self, client: TestClient) -> None:
        with (
            patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()),
            patch("voice.booking_router._resolve_calcom", return_value=MagicMock()),
            patch("voice.booking_router.lookup_by_phone", new_callable=AsyncMock, return_value=[
                {"uid": "cal-001", "startTime": "2026-03-20T10:00:00Z", "status": "accepted"}
            ]),
        ):
            response = client.get(
                "/api/bookings/lookup?phone=%2B15125550101",
                headers=_api_key_header(),
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["bookings"]) == 1

    def test_missing_phone_returns_422(self, client: TestClient) -> None:
        with patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()):
            response = client.get(
                "/api/bookings/lookup",
                headers=_api_key_header(),
            )

        assert response.status_code == 422

    def test_invalid_api_key_returns_401(self, client: TestClient) -> None:
        with patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()):
            response = client.get(
                "/api/bookings/lookup?phone=%2B15125550101",
                headers={"X-API-Key": "wrong-key"},
            )

        assert response.status_code == 401

    def test_missing_api_key_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/bookings/lookup?phone=%2B15125550101")
        assert response.status_code == 401


class TestBookingCancel:
    def test_valid_cancel(self, client: TestClient) -> None:
        with (
            patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()),
            patch("voice.booking_router._resolve_calcom", return_value=MagicMock()),
            patch("voice.booking_router.cancel_booking", new_callable=AsyncMock, return_value=True),
        ):
            response = client.post(
                "/api/bookings/cancel",
                json={"booking_uid": "cal-uid-001", "reason": "Customer requested"},
                headers=_api_key_header(),
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_missing_fields_returns_422(self, client: TestClient) -> None:
        with patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()):
            response = client.post(
                "/api/bookings/cancel",
                json={},
                headers=_api_key_header(),
            )

        assert response.status_code == 422


class TestBookingReschedule:
    def test_valid_reschedule(self, client: TestClient) -> None:
        with (
            patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()),
            patch("voice.booking_router._resolve_calcom", return_value=MagicMock()),
            patch("voice.booking_router.reschedule_booking", new_callable=AsyncMock, return_value=True),
        ):
            response = client.post(
                "/api/bookings/reschedule",
                json={
                    "booking_uid": "cal-uid-001",
                    "new_time": "2026-03-25T14:00:00Z",
                },
                headers=_api_key_header(),
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_calcom_503(self, client: TestClient) -> None:
        from voice.services.calcom import CalcomError

        with (
            patch("voice.booking_router._get_api_keys", return_value=_mock_api_key_records()),
            patch("voice.booking_router._resolve_calcom", return_value=MagicMock()),
            patch("voice.booking_router.reschedule_booking", new_callable=AsyncMock, side_effect=CalcomError("timeout")),
        ):
            response = client.post(
                "/api/bookings/reschedule",
                json={
                    "booking_uid": "cal-uid-001",
                    "new_time": "2026-03-25T14:00:00Z",
                },
                headers=_api_key_header(),
            )

        assert response.status_code == 503

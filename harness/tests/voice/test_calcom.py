"""Tests for Cal.com API service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voice.models import CalcomConfig
from voice.services.calcom import (
    CalcomError,
    cancel_booking,
    create_booking,
    lookup_by_phone,
    reschedule_booking,
)


@pytest.fixture
def calcom_config() -> CalcomConfig:
    return CalcomConfig(
        calcom_api_key="cal_live_test_key",
        calcom_event_type_id=12345,
        calcom_username="acecooling",
        calcom_timezone="America/Chicago",
    )


def _mock_response(status: int, data: object = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data or {}
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.text = str(data)
    return resp


class TestLookupByPhone:
    @pytest.mark.asyncio
    async def test_returns_bookings(self, calcom_config: CalcomConfig) -> None:
        bookings = {
            "status": "success",
            "data": [
                {
                    "uid": "cal-uid-001",
                    "title": "AC Service",
                    "startTime": "2026-03-20T10:00:00Z",
                    "endTime": "2026-03-20T11:00:00Z",
                    "status": "accepted",
                    "attendees": [{"phoneNumber": "+15125550101"}],
                },
            ],
        }

        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_response(200, bookings))
            mock_httpx.AsyncClient.return_value = mock_client

            result = await lookup_by_phone("+15125550101", calcom_config)

        assert len(result) == 1
        assert result[0]["uid"] == "cal-uid-001"

    @pytest.mark.asyncio
    async def test_no_bookings_returns_empty(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_response(200, {"status": "success", "data": []}))
            mock_httpx.AsyncClient.return_value = mock_client

            result = await lookup_by_phone("+15125550101", calcom_config)

        assert result == []

    @pytest.mark.asyncio
    async def test_calcom_error_raises(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_mock_response(500))
            mock_httpx.AsyncClient.return_value = mock_client

            with pytest.raises(CalcomError):
                await lookup_by_phone("+15125550101", calcom_config)


class TestCancelBooking:
    @pytest.mark.asyncio
    async def test_successful_cancel(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(200, {"status": "success"}))
            mock_httpx.AsyncClient.return_value = mock_client

            result = await cancel_booking("cal-uid-001", "Customer requested", calcom_config)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_error_raises(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(404))
            mock_httpx.AsyncClient.return_value = mock_client

            with pytest.raises(CalcomError):
                await cancel_booking("cal-uid-bad", "test", calcom_config)


class TestCreateBooking:
    @pytest.mark.asyncio
    async def test_successful_create_booking(self, calcom_config: CalcomConfig) -> None:
        booking_response = {
            "status": "success",
            "data": {
                "uid": "cal-uid-created",
                "startTime": "2026-03-25T14:00:00Z",
            },
        }

        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(200, booking_response))
            mock_httpx.AsyncClient.return_value = mock_client

            result = await create_booking(
                customer_name="Jane Customer",
                customer_phone="+15125550101",
                service_address="123 Main St, Austin, TX 78701",
                preferred_time="2026-03-25T14:00:00Z",
                issue_description="AC not cooling",
                urgency_tier="soon",
                config=calcom_config,
            )

        assert result["uid"] == "cal-uid-created"
        mock_client.post.assert_awaited_once()
        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["eventTypeId"] == 12345
        assert kwargs["json"]["attendee"]["phoneNumber"] == "+15125550101"
        assert kwargs["json"]["metadata"]["source"] == "calllock_voice"

    @pytest.mark.asyncio
    async def test_create_booking_error_raises(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(500))
            mock_httpx.AsyncClient.return_value = mock_client

            with pytest.raises(CalcomError):
                await create_booking(
                    customer_name="Jane Customer",
                    customer_phone="+15125550101",
                    service_address="123 Main St, Austin, TX 78701",
                    preferred_time="2026-03-25T14:00:00Z",
                    issue_description="AC not cooling",
                    urgency_tier="soon",
                    config=calcom_config,
                )


class TestRescheduleBooking:
    @pytest.mark.asyncio
    async def test_successful_reschedule(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(200, {"status": "success"}))
            mock_httpx.AsyncClient.return_value = mock_client

            result = await reschedule_booking(
                "cal-uid-001",
                "2026-03-25T14:00:00Z",
                calcom_config,
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_reschedule_error_raises(self, calcom_config: CalcomConfig) -> None:
        with patch("voice.services.calcom.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=_mock_response(500))
            mock_httpx.AsyncClient.return_value = mock_client

            with pytest.raises(CalcomError):
                await reschedule_booking("cal-uid-001", "2026-03-25T14:00:00Z", calcom_config)

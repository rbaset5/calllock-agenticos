"""Tests for the harness-owned Retell book_service tool."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from voice.fallback_router import FallbackPolicy
from voice.models import CalcomConfig, VoiceConfig
from voice.tools.book_service import book_service


@pytest.mark.asyncio
async def test_book_service_creates_booking_after_service_area_passes(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_create_booking(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "uid": "cal-001",
            "start": "2026-06-02T15:00:00-04:00",
        }

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="",
        preferred_time="2026-06-02T15:00:00-04:00",
        issue_description="AC not cooling",
        urgency_tier="urgent",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is True
    assert result["booking_id"] == "cal-001"
    assert result["appointment_time"] == "2026-06-02T15:00:00-04:00"
    assert calls[0]["customer_email"] == "jane@example.com"
    assert calls[0]["service_address"] == "123 Oak St, Austin TX 78701"


@pytest.mark.asyncio
async def test_book_service_uses_zip_code_when_address_lacks_zip(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_create_booking(**_: object) -> dict[str, object]:
        return {
            "uid": "cal-002",
            "start": "2026-06-02T16:00:00-04:00",
        }

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX",
        zip_code="78701",
        preferred_time="2026-06-02T16:00:00-04:00",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is True
    assert result["booking_id"] == "cal-002"


@pytest.mark.asyncio
async def test_book_service_resolves_soonest_available_inside_default_business_hours(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    booking_calls: list[dict[str, object]] = []

    async def fake_list_available_slots(**_: object) -> list[dict[str, object]]:
        return [
            {"start": "2026-06-02T08:30:00.000-05:00"},
            {"start": "2026-06-02T17:00:00.000-05:00"},
            {"start": "2026-06-03T09:00:00.000-05:00"},
        ]

    async def fake_create_booking(**kwargs: object) -> dict[str, object]:
        booking_calls.append(kwargs)
        return {
            "uid": "cal-soonest",
            "start": kwargs["preferred_time"],
        }

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="78701",
        preferred_time="soonest available",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
        list_available_slots_fn=fake_list_available_slots,
        now_fn=lambda: datetime(2026, 6, 2, 10, 0, tzinfo=ZoneInfo("America/Chicago")),
    )

    assert result["booking_confirmed"] is True
    assert result["booking_id"] == "cal-soonest"
    assert booking_calls[0]["preferred_time"] == "2026-06-03T09:00:00.000-05:00"


@pytest.mark.asyncio
async def test_book_service_resolves_tomorrow_morning_to_first_matching_slot(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    slot_calls: list[dict[str, object]] = []
    booking_calls: list[dict[str, object]] = []

    async def fake_list_available_slots(**kwargs: object) -> list[dict[str, object]]:
        slot_calls.append(kwargs)
        return [
            {"start": "2026-06-03T08:30:00.000-05:00"},
            {"start": "2026-06-03T09:30:00.000-05:00"},
            {"start": "2026-06-03T13:00:00.000-05:00"},
        ]

    async def fake_create_booking(**kwargs: object) -> dict[str, object]:
        booking_calls.append(kwargs)
        return {
            "uid": "cal-tomorrow",
            "start": kwargs["preferred_time"],
        }

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="78701",
        preferred_time="tomorrow morning",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
        list_available_slots_fn=fake_list_available_slots,
        now_fn=lambda: datetime(2026, 6, 2, 10, 0, tzinfo=ZoneInfo("America/Chicago")),
    )

    assert result["booking_confirmed"] is True
    assert result["appointment_time"] == "2026-06-03T09:30:00.000-05:00"
    assert booking_calls[0]["preferred_time"] == "2026-06-03T09:30:00.000-05:00"
    assert slot_calls[0]["time_zone"] == "America/Chicago"


@pytest.mark.asyncio
async def test_book_service_returns_available_slots_when_preference_has_no_match(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_list_available_slots(**_: object) -> list[dict[str, object]]:
        return [
            {"start": "2026-06-03T09:00:00.000-05:00"},
            {"start": "2026-06-03T15:30:00.000-05:00"},
        ]

    async def fake_create_booking(**_: object) -> dict[str, object]:
        raise AssertionError("Cal.com booking should wait for the caller to choose an offered slot")

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="78701",
        preferred_time="tomorrow evening",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
        list_available_slots_fn=fake_list_available_slots,
        now_fn=lambda: datetime(2026, 6, 2, 10, 0, tzinfo=ZoneInfo("America/Chicago")),
    )

    assert result["booking_confirmed"] is False
    assert result["reason"] == "no_matching_slot"
    assert result["available_slots"] == [
        "2026-06-03T09:00:00.000-05:00",
        "2026-06-03T15:30:00.000-05:00",
    ]


@pytest.mark.asyncio
async def test_book_service_requires_email_before_calcom(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_create_booking(**_: object) -> dict[str, object]:
        raise AssertionError("Cal.com should not be called without customer email")

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="78701",
        preferred_time="tomorrow afternoon",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is False
    assert result["reason"] == "customer_email_missing"
    assert result["fallback_action"] == "callback_task"


@pytest.mark.asyncio
async def test_book_service_blocks_out_of_area_before_calcom(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_create_booking(**_: object) -> dict[str, object]:
        raise AssertionError("Cal.com should not be called for out-of-area callers")

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="999 Pine St, Dallas TX 75201",
        zip_code="75201",
        preferred_time="soonest available",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is False
    assert result["reason"] == "service_area_blocked"
    assert result["fallback_action"] == "callback_task"


@pytest.mark.asyncio
async def test_book_service_routes_to_voicemail_when_callback_disabled(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_create_booking(**_: object) -> dict[str, object]:
        raise RuntimeError("Cal.com is down")

    result = await book_service(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="",
        preferred_time="soonest available",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        fallback_policy=FallbackPolicy(
            callback_tasks_enabled=False,
            voicemail_enabled=True,
            voicemail_number="+15125559999",
        ),
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is False
    assert result["reason"] == "booking_failed"
    assert result["fallback_action"] == "voicemail"
    assert result["fallback_target"] == "+15125559999"

"""Tests for the harness-owned Retell book_service tool."""

from __future__ import annotations

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
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX 78701",
        zip_code="",
        preferred_time="tomorrow afternoon",
        issue_description="AC not cooling",
        urgency_tier="urgent",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is True
    assert result["booking_id"] == "cal-001"
    assert result["appointment_time"] == "2026-06-02T15:00:00-04:00"
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
        customer_phone="+15125550101",
        service_address="123 Oak St, Austin TX",
        zip_code="78701",
        preferred_time="tomorrow afternoon",
        issue_description="AC not cooling",
        urgency_tier="routine",
        voice_config=mock_voice_config,
        calcom_config=mock_calcom_config,
        create_booking_fn=fake_create_booking,
    )

    assert result["booking_confirmed"] is True
    assert result["booking_id"] == "cal-002"


@pytest.mark.asyncio
async def test_book_service_blocks_out_of_area_before_calcom(
    mock_voice_config: VoiceConfig,
    mock_calcom_config: CalcomConfig,
) -> None:
    async def fake_create_booking(**_: object) -> dict[str, object]:
        raise AssertionError("Cal.com should not be called for out-of-area callers")

    result = await book_service(
        customer_name="Jane Doe",
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

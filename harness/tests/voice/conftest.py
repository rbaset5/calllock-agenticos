"""Shared fixtures for voice module tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice.models import CalcomConfig, VoiceConfig


@pytest.fixture
def mock_voice_config() -> VoiceConfig:
    return VoiceConfig(
        twilio_account_sid="AC_test_sid",
        twilio_auth_token="test_auth_token",
        twilio_from_number="+15125551234",
        twilio_owner_phone="+15125555678",
        service_area_zips=["78701", "78702", "78703"],
        business_name="ACE Cooling & Heating",
        business_phone="+15125559999",
    )


@pytest.fixture
def mock_calcom_config() -> CalcomConfig:
    return CalcomConfig(
        calcom_api_key="cal_live_test",
        calcom_event_type_id=12345,
        calcom_username="acecooling",
        calcom_timezone="America/Chicago",
    )


@pytest.fixture
def mock_retell_payload() -> dict[str, object]:
    """A realistic Retell call-ended webhook payload."""

    return {
        "call_id": "ret-call-001",
        "transcript": (
            "Agent: Thank you for calling ACE Cooling and Heating. "
            "User: Hi, my name is John Smith. My AC isn't cooling. "
            "I live at 123 Oak Street, Austin, TX 78701. "
            "It stopped working this morning."
        ),
        "transcript_object": [],
        "call_summary": "Customer reports AC not cooling at home.",
        "custom_metadata": {"tenant_id": "tenant-ace-001"},
        "from_number": "+15125550101",
        "to_number": "+15125559999",
        "direction": "inbound",
        "duration_ms": 120000,
        "recording_url": "https://retell.ai/recordings/ret-call-001.mp3",
        "disconnection_reason": "agent_hangup",
        "retell_llm_dynamic_variables": {
            "customer_name": "John Smith",
            "service_address": "123 Oak Street, Austin, TX 78701",
            "urgency_tier": "urgent",
            "booking_confirmed": "false",
        },
        "tool_call_results": [],
    }


@pytest.fixture
def mock_retell_tool_call_request() -> dict[str, object]:
    """A realistic Retell tool call webhook payload."""

    return {
        "call_id": "ret-call-001",
        "tool_name": "lookup_caller",
        "args": {"phone_number": "+15125550101"},
        "metadata": {"tenant_id": "tenant-ace-001"},
    }


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client with sync get/set methods."""

    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.setex = MagicMock()
    return redis

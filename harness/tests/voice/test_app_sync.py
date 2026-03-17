"""Tests for CallLock App webhook sync service."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voice.models import VoiceConfig
from voice.services.app_sync import (
    sign_webhook_payload,
    transform_to_app_payload,
    send_to_app,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def voice_config() -> VoiceConfig:
    return VoiceConfig(
        twilio_account_sid="AC_test_sid",
        twilio_auth_token="test_auth_token",
        twilio_from_number="+15125551234",
        twilio_owner_phone="+15125555678",
        app_webhook_url="https://app.calllock.co/api/webhook/jobs",
        app_webhook_secret="test_webhook_secret",
        service_area_zips=["78701"],
        business_name="ACE Cooling & Heating",
        business_phone="+15125559999",
    )


@pytest.fixture
def extraction_result() -> dict[str, Any]:
    return {
        "customer_name": "John Smith",
        "customer_phone": "+15125550101",
        "service_address": "123 Oak Street, Austin, TX 78701",
        "problem_description": "AC not cooling",
        "safety_emergency": False,
        "urgency_level": "Routine",
        "urgency_tier": "routine",
        "dashboard_urgency": "medium",
        "hvac_issue_type": None,
        "tag_categories": {},
        "tags": [],
        "quality_score": 45.0,
        "scorecard_warnings": [],
        "caller_type": "unknown",
        "primary_intent": "unknown",
        "revenue_tier": "standard_repair",
        "revenue_estimate": {
            "tier": "standard_repair",
            "tierLabel": "$$",
            "tierDescription": "Standard Repair",
            "estimatedRange": "$200-$800",
            "signals": [],
            "confidence": "low",
            "potentialReplacement": False,
        },
        "route": "legitimate",
        "end_call_reason": "agent_hangup",
        "extracted_fields": {},
        "failed_steps": [],
        "extraction_status": "complete",
    }


@pytest.fixture
def raw_payload() -> dict[str, Any]:
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
        "retell_llm_dynamic_variables": {},
        "tool_call_results": [],
    }


class TestTransformToAppPayload:
    def test_golden_fixture_match(
        self,
        extraction_result: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        """Transform output must match the golden fixture field-for-field."""
        golden_path = FIXTURES_DIR / "golden_dashboard_payload.json"
        golden = json.loads(golden_path.read_text())

        result = transform_to_app_payload(
            extraction=extraction_result,
            raw_payload=raw_payload,
            call_id="call-test-001",
            user_email="operator@acecooling.com",
        )

        for key, expected_value in golden.items():
            actual = result.get(key)
            assert actual == expected_value, (
                f"Field '{key}': expected {expected_value!r}, got {actual!r}"
            )

    def test_required_fields_present(
        self,
        extraction_result: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        result = transform_to_app_payload(
            extraction=extraction_result,
            raw_payload=raw_payload,
            call_id="call-test-002",
            user_email="test@test.com",
        )

        assert result["customer_name"] == "John Smith"
        assert result["customer_phone"] == "+15125550101"
        assert result["customer_address"] == "123 Oak Street, Austin, TX 78701"
        assert result["service_type"] == "hvac"
        assert result["urgency"] == "medium"
        assert result["user_email"] == "test@test.com"

    def test_booking_status_confirmed(
        self,
        extraction_result: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        extraction_result["end_call_reason"] = "booking_confirmed"

        result = transform_to_app_payload(
            extraction=extraction_result,
            raw_payload=raw_payload,
            call_id="call-test-003",
            user_email="test@test.com",
            booking_id="cal-uid-123",
        )

        assert result["booking_status"] == "confirmed"

    def test_booking_status_not_requested(
        self,
        extraction_result: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        result = transform_to_app_payload(
            extraction=extraction_result,
            raw_payload=raw_payload,
            call_id="call-test-004",
            user_email="test@test.com",
        )

        assert result["booking_status"] == "not_requested"

    def test_unknown_caller_fallback(
        self,
        extraction_result: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> None:
        extraction_result["customer_name"] = None

        result = transform_to_app_payload(
            extraction=extraction_result,
            raw_payload=raw_payload,
            call_id="call-test-005",
            user_email="test@test.com",
        )

        assert result["customer_name"] == "Unknown Caller"


class TestSignWebhookPayload:
    def test_produces_valid_hmac(self) -> None:
        payload = {"customer_name": "Test"}
        secret = "my-secret"

        signature = sign_webhook_payload(payload, secret)

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert signature == expected


class TestSendToApp:
    @pytest.mark.asyncio
    async def test_successful_post_returns_true(self, voice_config: VoiceConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "job_id": "job-1"}

        with patch("voice.services.app_sync.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await send_to_app(
                payload={"customer_name": "Test"},
                config=voice_config,
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_5xx_raises_for_retry(self, voice_config: VoiceConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"
        mock_response.raise_for_status.side_effect = Exception("502 Bad Gateway")

        with patch("voice.services.app_sync.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient.return_value = mock_client

            with pytest.raises(Exception):
                await send_to_app(
                    payload={"customer_name": "Test"},
                    config=voice_config,
                )

from __future__ import annotations

import logging

import pytest

from voice.models import (
    CalcomConfig,
    CallEndedEvent,
    CallerType,
    DashboardPayload,
    EndCallReason,
    PrimaryIntent,
    RetellCallEndedPayload,
    RetellToolCallRequest,
    RevenueTier,
    UrgencyTier,
    VoiceConfig,
)


class TestVoiceConfig:
    def test_valid_config(self) -> None:
        config = VoiceConfig(
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_from_number="+15125551234",
            twilio_owner_phone="+15125555678",
            service_area_zips=["78701", "78702"],
            business_name="ACE Cooling",
            business_phone="+15125559999",
        )
        assert config.business_name == "ACE Cooling"

    def test_empty_zips_allowed(self) -> None:
        config = VoiceConfig(
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_from_number="+15125551234",
            twilio_owner_phone="+15125555678",
            service_area_zips=[],
            business_name="ACE Cooling",
            business_phone="+15125559999",
        )
        assert config.service_area_zips == []

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(Exception):
            VoiceConfig(twilio_account_sid="AC123")


class TestCalcomConfig:
    def test_valid_config(self) -> None:
        config = CalcomConfig(
            calcom_api_key="cal_live_xxx",
            calcom_event_type_id=12345,
            calcom_username="acecooling",
            calcom_timezone="America/Chicago",
        )
        assert config.calcom_timezone == "America/Chicago"


class TestCallEndedEvent:
    def test_minimal_valid_event(self) -> None:
        event = CallEndedEvent(
            tenant_id="t-123",
            call_id="c-456",
            call_source="retell",
            phone_number="+15125551234",
            transcript="Hello",
            urgency_tier=UrgencyTier.ROUTINE,
            caller_type=CallerType.RESIDENTIAL,
            primary_intent=PrimaryIntent.SERVICE,
            revenue_tier=RevenueTier.STANDARD_REPAIR,
            tags=[],
            quality_score=0.0,
            scorecard_warnings=[],
            route="legitimate",
            extraction_status="complete",
            retell_call_id="ret-789",
            call_duration_seconds=60,
            end_call_reason=EndCallReason.AGENT_HANGUP,
        )
        assert event.call_source == "retell"

    def test_partial_extraction_allowed(self) -> None:
        event = CallEndedEvent(
            tenant_id="t-123",
            call_id="c-456",
            call_source="retell",
            phone_number="+15125551234",
            transcript="",
            urgency_tier=UrgencyTier.ROUTINE,
            caller_type=CallerType.UNKNOWN,
            primary_intent=PrimaryIntent.UNKNOWN,
            revenue_tier=RevenueTier.UNKNOWN,
            tags=[],
            quality_score=0.0,
            scorecard_warnings=["zero-tags", "callback-gap"],
            route="legitimate",
            extraction_status="partial",
            retell_call_id="ret-789",
            call_duration_seconds=5,
            end_call_reason=EndCallReason.CUSTOMER_HANGUP,
        )
        assert event.extraction_status == "partial"


class TestUrgencyTier:
    def test_all_values(self) -> None:
        assert UrgencyTier.EMERGENCY == "emergency"
        assert UrgencyTier.URGENT == "urgent"
        assert UrgencyTier.ROUTINE == "routine"
        assert UrgencyTier.ESTIMATE == "estimate"


class TestLooseWebhookModels:
    def test_retell_tool_call_request_logs_unexpected_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            request = RetellToolCallRequest.model_validate(
                {
                    "call_id": "ret-call-001",
                    "tool_name": "lookup_caller",
                    "args": {"phone_number": "+15125550101"},
                    "metadata": {"tenant_id": "tenant-ace-001"},
                    "surprise_field": "unexpected",
                }
            )

        assert request.call_id == "ret-call-001"
        assert "surprise_field" in caplog.text

    def test_retell_call_ended_payload_accepts_alias_and_extra_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            payload = RetellCallEndedPayload.model_validate(
                {
                    "call_id": "ret-call-001",
                    "transcript": "Customer needs help",
                    "custom_metadata": {"tenant_id": "tenant-ace-001"},
                    "retell_llm_dynamic_variables": {"customer_name": "John Smith"},
                    "tool_call_results": [],
                    "unknown_flag": True,
                }
            )

        assert payload.dynamic_variables == {"customer_name": "John Smith"}
        assert "unknown_flag" in caplog.text


class TestDashboardPayload:
    def test_valid_dashboard_payload(self) -> None:
        payload = DashboardPayload(
            customer_name="John Smith",
            customer_phone="+15125550101",
            customer_address="123 Oak Street, Austin, TX 78701",
            service_type="hvac",
            urgency="high",
            user_email="ops@calllock.co",
            call_id="call-123",
            revenue_tier=RevenueTier.STANDARD_REPAIR,
            revenue_confidence="medium",
            tags={"SERVICE_TYPE": ["REPAIR_AC"], "URGENCY": ["NO_COOL"]},
            transcript_object=[
                {"role": "agent", "content": "How can I help?"},
                {"role": "user", "content": "My AC stopped cooling."},
            ],
            booking_status="not_requested",
        )
        assert payload.service_type == "hvac"
        assert payload.tags["SERVICE_TYPE"] == ["REPAIR_AC"]

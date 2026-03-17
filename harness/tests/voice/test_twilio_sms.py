"""Tests for Twilio SMS service with template-based messages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from twilio.base.exceptions import TwilioRestException

from voice.models import VoiceConfig
from voice.services.twilio_sms import (
    SendResult,
    mask_phone,
    sanitize_reason,
    send_callback_sms,
    send_emergency_sms,
    send_sales_lead_sms,
)


@pytest.fixture
def voice_config() -> VoiceConfig:
    return VoiceConfig(
        twilio_account_sid="AC_test_sid",
        twilio_auth_token="test_auth_token",
        twilio_from_number="+15125551234",
        twilio_owner_phone="+15125555678",
        service_area_zips=["78701"],
        business_name="ACE Cooling & Heating",
        business_phone="+15125559999",
    )


@pytest.fixture
def mock_twilio_client() -> MagicMock:
    client = MagicMock()
    message = MagicMock()
    message.sid = "SM_test_message_sid"
    client.messages.create.return_value = message
    return client


class TestMaskPhone:
    def test_full_phone(self) -> None:
        assert mask_phone("+15125551234") == "***-***-1234"

    def test_short_phone(self) -> None:
        assert mask_phone("123") == "****"

    def test_none(self) -> None:
        assert mask_phone(None) == "unknown"

    def test_empty(self) -> None:
        assert mask_phone("") == "unknown"


class TestSanitizeReason:
    def test_truncates_to_200(self) -> None:
        long_reason = "x" * 300
        result = sanitize_reason(long_reason)
        assert len(result) == 200

    def test_strips_non_printable(self) -> None:
        result = sanitize_reason("hello\x00world\x01test")
        assert result == "helloworldtest"

    def test_normal_text_unchanged(self) -> None:
        result = sanitize_reason("AC not cooling")
        assert result == "AC not cooling"

    def test_none_returns_empty(self) -> None:
        result = sanitize_reason(None)
        assert result == ""


class TestSendCallbackSMS:
    def test_successful_send(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        result = send_callback_sms(
            config=voice_config,
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            twilio_client=mock_twilio_client,
        )

        assert result is not None
        assert result.success is True
        assert result.message_sid == "SM_test_message_sid"

        mock_twilio_client.messages.create.assert_called_once()
        call_kwargs = mock_twilio_client.messages.create.call_args.kwargs
        assert call_kwargs["to"] == "+15125555678"
        assert call_kwargs["from_"] == "+15125551234"
        body = call_kwargs["body"]
        assert "ACE Cooling & Heating" in body
        assert "+15125550101" in body
        assert "AC not cooling" in body
        assert "30 min" in body

    def test_template_format(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        result = send_callback_sms(
            config=voice_config,
            caller_phone="+15125550101",
            reason="Water heater leaking",
            callback_minutes=15,
            twilio_client=mock_twilio_client,
        )

        body = mock_twilio_client.messages.create.call_args.kwargs["body"]
        lines = body.split("\n")
        assert lines[0] == "ACE Cooling & Heating callback request"
        assert lines[1] == "Caller: +15125550101"
        assert lines[2] == "Reason: Water heater leaking"
        assert lines[3] == "Callback within 15 min"

    def test_twilio_error_returns_none(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        mock_twilio_client.messages.create.side_effect = TwilioRestException(
            status=500, uri="/Messages", msg="Internal Error"
        )

        result = send_callback_sms(
            config=voice_config,
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            twilio_client=mock_twilio_client,
        )

        assert result is None

    def test_reason_sanitized(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        long_reason = "x" * 300
        send_callback_sms(
            config=voice_config,
            caller_phone="+15125550101",
            reason=long_reason,
            callback_minutes=30,
            twilio_client=mock_twilio_client,
        )

        body = mock_twilio_client.messages.create.call_args.kwargs["body"]
        reason_line = [line for line in body.split("\n") if line.startswith("Reason:")][0]
        reason_value = reason_line.split("Reason: ", 1)[1]
        assert len(reason_value) <= 200


class TestSendSalesLeadSMS:
    def test_successful_send(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        result = send_sales_lead_sms(
            config=voice_config,
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St, Austin TX",
            twilio_client=mock_twilio_client,
        )

        assert result is not None
        assert result.success is True
        assert result.message_sid == "SM_test_message_sid"

        call_kwargs = mock_twilio_client.messages.create.call_args.kwargs
        body = call_kwargs["body"]
        assert "SALES LEAD: Central AC" in body
        assert "Customer: John Smith" in body
        assert "Phone: +15125550101" in body
        assert "Address: 123 Oak St, Austin TX" in body

    def test_template_format(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        send_sales_lead_sms(
            config=voice_config,
            equipment="AC Replacement",
            customer_name="Jane Doe",
            customer_phone="+15125550202",
            address="456 Elm St, Austin TX 78702",
            twilio_client=mock_twilio_client,
        )

        body = mock_twilio_client.messages.create.call_args.kwargs["body"]
        lines = body.split("\n")
        assert lines[0] == "SALES LEAD: AC Replacement"
        assert lines[1] == "Customer: Jane Doe"
        assert lines[2] == "Phone: +15125550202"
        assert lines[3] == "Address: 456 Elm St, Austin TX 78702"

    def test_twilio_error_returns_none(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        mock_twilio_client.messages.create.side_effect = TwilioRestException(
            status=400, uri="/Messages", msg="Invalid number"
        )

        result = send_sales_lead_sms(
            config=voice_config,
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St",
            twilio_client=mock_twilio_client,
        )

        assert result is None


class TestSendEmergencySMS:
    def test_successful_send(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        result = send_emergency_sms(
            config=voice_config,
            description="Gas leak reported",
            caller_phone="+15125550101",
            address="789 Pine Ave, Austin TX",
            twilio_client=mock_twilio_client,
        )

        assert result is not None
        assert result.success is True

        body = mock_twilio_client.messages.create.call_args.kwargs["body"]
        assert "URGENT: Gas leak reported" in body
        assert "Caller: +15125550101" in body
        assert "Address: 789 Pine Ave, Austin TX" in body

    def test_template_format(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        send_emergency_sms(
            config=voice_config,
            description="CO detector alarm",
            caller_phone="+15125550303",
            address="321 Maple Dr, Austin TX",
            twilio_client=mock_twilio_client,
        )

        body = mock_twilio_client.messages.create.call_args.kwargs["body"]
        lines = body.split("\n")
        assert lines[0] == "URGENT: CO detector alarm"
        assert lines[1] == "Caller: +15125550303"
        assert lines[2] == "Address: 321 Maple Dr, Austin TX"

    def test_twilio_error_returns_none(self, voice_config: VoiceConfig, mock_twilio_client: MagicMock) -> None:
        mock_twilio_client.messages.create.side_effect = TwilioRestException(
            status=500, uri="/Messages", msg="Server error"
        )

        result = send_emergency_sms(
            config=voice_config,
            description="Fire hazard",
            caller_phone="+15125550101",
            address="100 Main St",
            twilio_client=mock_twilio_client,
        )

        assert result is None

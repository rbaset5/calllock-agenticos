"""Tests for send_sales_lead_alert tool handler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from voice.models import VoiceConfig
from voice.services.twilio_sms import SendResult
from voice.tools.sales_lead_alert import send_sales_lead_alert

_GRACEFUL_ERROR = "We're experiencing technical difficulties. Please call back or leave a message."


@pytest.fixture
def voice_config() -> VoiceConfig:
    return VoiceConfig(
        twilio_account_sid="AC_test_sid",
        twilio_auth_token="test_auth_token",
        twilio_from_number="+15125551234",
        twilio_owner_phone="+15125555678",
        app_webhook_url="https://app.calllock.co/api/webhook",
        app_webhook_secret="test_webhook_secret",
        service_area_zips=["78701"],
        business_name="ACE Cooling & Heating",
        business_phone="+15125559999",
    )


@pytest.fixture
def mock_sms_fn() -> MagicMock:
    fn = MagicMock()
    fn.return_value = SendResult(success=True, message_sid="SM_test")
    return fn


class TestSalesLeadAlertSuccess:
    def test_successful_send(self, voice_config: VoiceConfig, mock_sms_fn: MagicMock) -> None:
        result = send_sales_lead_alert(
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St, Austin TX",
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True
        mock_sms_fn.assert_called_once_with(
            config=voice_config,
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St, Austin TX",
        )

    def test_returns_confirmation_message(self, voice_config: VoiceConfig, mock_sms_fn: MagicMock) -> None:
        result = send_sales_lead_alert(
            equipment="Heat Pump",
            customer_name="Jane Doe",
            customer_phone="+15125550202",
            address="456 Elm St",
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True
        assert "message" in result


class TestSalesLeadAlertTwilioFailure:
    def test_twilio_failure_still_returns_success(
        self, voice_config: VoiceConfig, mock_sms_fn: MagicMock
    ) -> None:
        """Returns success to Retell even on Twilio failure."""
        mock_sms_fn.return_value = None

        result = send_sales_lead_alert(
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St",
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True

    def test_twilio_exception_still_returns_success(
        self, voice_config: VoiceConfig, mock_sms_fn: MagicMock
    ) -> None:
        mock_sms_fn.side_effect = RuntimeError("Twilio SDK crashed")

        result = send_sales_lead_alert(
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St",
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True


class TestSalesLeadAlertVoiceConfigMissing:
    def test_missing_config_returns_graceful_error(self) -> None:
        result = send_sales_lead_alert(
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St",
            voice_config=None,
        )

        assert result["success"] is False
        assert result["message"] == _GRACEFUL_ERROR

    def test_config_error_prevents_sms_call(self, mock_sms_fn: MagicMock) -> None:
        result = send_sales_lead_alert(
            equipment="Central AC",
            customer_name="John Smith",
            customer_phone="+15125550101",
            address="123 Oak St",
            voice_config=None,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is False
        mock_sms_fn.assert_not_called()

"""Tests for create_callback tool handler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from twilio.base.exceptions import TwilioRestException

from voice.config import VoiceConfigError
from voice.models import VoiceConfig
from voice.services.twilio_sms import SendResult
from voice.tools.create_callback import create_callback

_GRACEFUL_ERROR = "We're experiencing technical difficulties. Please call back or leave a message."


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
def mock_sms_fn() -> MagicMock:
    fn = MagicMock()
    fn.return_value = SendResult(success=True, message_sid="SM_test")
    return fn


class TestCreateCallbackSuccess:
    def test_successful_callback(self, voice_config: VoiceConfig, mock_sms_fn: MagicMock) -> None:
        result = create_callback(
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True
        mock_sms_fn.assert_called_once_with(
            config=voice_config,
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
        )

    def test_returns_confirmation_message(self, voice_config: VoiceConfig, mock_sms_fn: MagicMock) -> None:
        result = create_callback(
            caller_phone="+15125550101",
            reason="Water heater leaking",
            callback_minutes=15,
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True
        assert "message" in result


class TestCreateCallbackTwilioFailure:
    def test_twilio_failure_still_returns_success(
        self, voice_config: VoiceConfig, mock_sms_fn: MagicMock
    ) -> None:
        """Returns success to Retell even on Twilio failure (caller hears normal ending)."""
        mock_sms_fn.return_value = None  # Twilio failed

        result = create_callback(
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True

    def test_twilio_exception_still_returns_success(
        self, voice_config: VoiceConfig, mock_sms_fn: MagicMock
    ) -> None:
        """Even if SMS fn throws unexpectedly, return success to Retell."""
        mock_sms_fn.side_effect = RuntimeError("Unexpected Twilio error")

        result = create_callback(
            caller_phone="+15125550101",
            reason="AC broken",
            callback_minutes=30,
            voice_config=voice_config,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is True


class TestCreateCallbackVoiceConfigMissing:
    def test_missing_config_returns_graceful_error(self) -> None:
        """VoiceConfig missing -> return graceful error message to Retell."""
        result = create_callback(
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            voice_config=None,
        )

        assert result["success"] is False
        assert result["message"] == _GRACEFUL_ERROR

    def test_config_error_returns_graceful_error(self, mock_sms_fn: MagicMock) -> None:
        """Simulate VoiceConfigError by passing None config."""
        result = create_callback(
            caller_phone="+15125550101",
            reason="AC not cooling",
            callback_minutes=30,
            voice_config=None,
            send_sms_fn=mock_sms_fn,
        )

        assert result["success"] is False
        assert _GRACEFUL_ERROR in result["message"]
        mock_sms_fn.assert_not_called()

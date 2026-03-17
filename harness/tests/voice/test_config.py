from __future__ import annotations

import json
import logging
import os
from unittest.mock import MagicMock

import pytest

from voice.crypto import encrypt_config
from voice.config import VoiceConfigError, resolve_calcom_config, resolve_voice_config
from voice.models import CalcomConfig, VoiceConfig


def _voice_config_dict() -> dict[str, object]:
    return {
        "twilio_account_sid": "AC123",
        "twilio_auth_token": "token",
        "twilio_from_number": "+15125551234",
        "twilio_owner_phone": "+15125555678",
        "service_area_zips": ["78701"],
        "business_name": "ACE",
        "business_phone": "+15125559999",
    }


def _calcom_config_dict() -> dict[str, object]:
    return {
        "calcom_api_key": "cal_live_test",
        "calcom_event_type_id": 12345,
        "calcom_username": "acecooling",
        "calcom_timezone": "America/Chicago",
    }


class TestResolveVoiceConfig:
    def test_cache_hit(self) -> None:
        cached = json.dumps(_voice_config_dict())
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=cached)

        config = resolve_voice_config("tenant-1", redis_client=mock_redis)

        assert isinstance(config, VoiceConfig)
        assert config.business_name == "ACE"

    def test_cache_miss_fetches_db(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        mock_redis.setex = MagicMock()

        config = resolve_voice_config(
            "tenant-1",
            redis_client=mock_redis,
            db_fetch=lambda _tenant_id: _voice_config_dict(),
        )

        assert config.business_name == "ACE"
        mock_redis.setex.assert_called_once()

    def test_empty_config_raises(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)

        with pytest.raises(VoiceConfigError, match="tenant-1"):
            resolve_voice_config("tenant-1", redis_client=mock_redis, db_fetch=lambda _tenant_id: {})

    def test_redis_error_logs_warning_and_falls_back(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("redis unavailable")

        with caplog.at_level(logging.WARNING):
            config = resolve_voice_config(
                "tenant-1",
                redis_client=mock_redis,
                db_fetch=lambda _tenant_id: _voice_config_dict(),
            )

        assert config.business_name == "ACE"
        assert "voice.config_cache.error" in caplog.text

    def test_db_fetch_decrypts_encrypted_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        encrypted = encrypt_config(_voice_config_dict())

        config = resolve_voice_config("tenant-1", redis_client=None, db_fetch=lambda _tenant_id: encrypted)

        assert config.twilio_account_sid == "AC123"


class TestResolveCalcomConfig:
    def test_calcom_cache_miss_fetches_db(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        mock_redis.setex = MagicMock()

        config = resolve_calcom_config(
            "tenant-1",
            redis_client=mock_redis,
            db_fetch=lambda _tenant_id: _calcom_config_dict(),
        )

        assert isinstance(config, CalcomConfig)
        assert config.calcom_username == "acecooling"
        mock_redis.setex.assert_called_once()

    def test_calcom_cache_hit(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=json.dumps(_calcom_config_dict()))

        config = resolve_calcom_config("tenant-1", redis_client=mock_redis)

        assert config.calcom_timezone == "America/Chicago"

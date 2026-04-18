from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from voice.auth import HMACVerificationError, InvalidAPIKeyError, verify_api_key, verify_retell_hmac


class TestRetellHMAC:
    def test_valid_signature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        body = b'{"call_id": "123"}'
        timestamp_ms = int(time.time() * 1000)
        message = body + str(timestamp_ms).encode()
        digest = hmac.new(b"test-api-key", message, hashlib.sha256).hexdigest()
        signature = f"v={timestamp_ms},d={digest}"

        verify_retell_hmac(body, signature)

    def test_invalid_signature_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")

        with pytest.raises(HMACVerificationError):
            verify_retell_hmac(b"body", "bad-signature")

    def test_expired_timestamp_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        old_ts = int(time.time() * 1000) - 600_000
        body = b"body"
        message = body + str(old_ts).encode()
        digest = hmac.new(b"test-api-key", message, hashlib.sha256).hexdigest()
        signature = f"v={old_ts},d={digest}"

        with pytest.raises(HMACVerificationError, match="expired"):
            verify_retell_hmac(body, signature)

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RETELL_API_KEY", raising=False)
        monkeypatch.delenv("RETELL_WEBHOOK_SECRET", raising=False)

        with pytest.raises(RuntimeError):
            verify_retell_hmac(b"body", "v=1,d=sig")

    def test_legacy_signature_still_supported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RETELL_API_KEY", raising=False)
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "legacy-secret")
        body = b'{"call_id":"legacy"}'
        timestamp = str(int(time.time()))
        message = timestamp.encode() + b"." + body
        signature = hmac.new(b"legacy-secret", message, hashlib.sha256).hexdigest()

        verify_retell_hmac(body, signature, timestamp)


class TestAPIKeyAuth:
    def test_valid_key(self) -> None:
        plaintext_key = "test-api-key-12345"
        stored_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()

        result = verify_api_key(
            provided_key=plaintext_key,
            stored_records=[{"api_key_hash": stored_hash, "tenant_id": "t-1", "revoked_at": None}],
        )

        assert result == "t-1"

    def test_revoked_key_rejected(self) -> None:
        plaintext_key = "test-api-key-12345"
        stored_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()

        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(
                provided_key=plaintext_key,
                stored_records=[{"api_key_hash": stored_hash, "tenant_id": "t-1", "revoked_at": "2026-01-01"}],
            )

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(provided_key="unknown", stored_records=[])

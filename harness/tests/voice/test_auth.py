from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from voice.auth import HMACVerificationError, InvalidAPIKeyError, verify_api_key, verify_retell_hmac


class TestRetellHMAC:
    def test_valid_signature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
        body = b'{"call_id": "123"}'
        timestamp = str(int(time.time()))
        message = timestamp.encode() + b"." + body
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        verify_retell_hmac(body, signature, timestamp)

    def test_invalid_signature_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")

        with pytest.raises(HMACVerificationError):
            verify_retell_hmac(b"body", "bad-sig", str(int(time.time())))

    def test_expired_timestamp_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
        old_ts = str(int(time.time()) - 600)
        body = b"body"
        message = old_ts.encode() + b"." + body
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        with pytest.raises(HMACVerificationError, match="expired"):
            verify_retell_hmac(body, signature, old_ts)

    def test_missing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RETELL_WEBHOOK_SECRET", raising=False)

        with pytest.raises(RuntimeError):
            verify_retell_hmac(b"body", "sig", str(int(time.time())))


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

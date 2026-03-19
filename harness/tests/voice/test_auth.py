from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from voice.auth import HMACVerificationError, InvalidAPIKeyError, verify_api_key, verify_retell_hmac


def _make_retell_signature(body: bytes, api_key: str, ts_ms: int | None = None) -> str:
    """Build a Retell-format signature header: v=<ts_ms>,d=<digest>."""
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    message = body + str(ts_ms).encode()
    digest = hmac.new(api_key.encode(), message, hashlib.sha256).hexdigest()
    return f"v={ts_ms},d={digest}"


class TestRetellHMAC:
    def test_valid_combined_signature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        body = b'{"call_id": "123"}'
        sig_header = _make_retell_signature(body, "test-api-key")

        verify_retell_hmac(body, sig_header)

    def test_valid_with_separate_timestamp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        body = b'{"call_id": "123"}'
        ts_ms = int(time.time() * 1000)
        message = body + str(ts_ms).encode()
        digest = hmac.new(b"test-api-key", message, hashlib.sha256).hexdigest()

        verify_retell_hmac(body, digest, str(ts_ms))

    def test_invalid_signature_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        ts_ms = int(time.time() * 1000)

        with pytest.raises(HMACVerificationError):
            verify_retell_hmac(b"body", f"v={ts_ms},d=bad-digest")

    def test_expired_timestamp_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
        old_ts_ms = int(time.time() * 1000) - 600_000  # 10 min old
        body = b"body"
        sig_header = _make_retell_signature(body, "test-api-key", old_ts_ms)

        with pytest.raises(HMACVerificationError, match="expired"):
            verify_retell_hmac(body, sig_header)

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RETELL_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="RETELL_API_KEY"):
            verify_retell_hmac(b"body", "v=123,d=abc")

    def test_malformed_header_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RETELL_API_KEY", "test-api-key")

        with pytest.raises(HMACVerificationError, match="Malformed"):
            verify_retell_hmac(b"body", "garbage-header")


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

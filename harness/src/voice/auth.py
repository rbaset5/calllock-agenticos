"""Authentication helpers for voice webhooks and booking API access."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Iterable, Mapping
from typing import Any


_TIMESTAMP_TOLERANCE_SECONDS = 300


class HMACVerificationError(Exception):
    """Retell webhook signature verification failed."""


class InvalidAPIKeyError(Exception):
    """Booking API key is invalid, revoked, or unknown."""


def verify_retell_hmac(body: bytes, signature: str, timestamp: str) -> None:
    """Verify a Retell webhook HMAC-SHA256 signature."""

    secret = os.environ.get("RETELL_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("RETELL_WEBHOOK_SECRET environment variable is not set")

    try:
        parsed_timestamp = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise HMACVerificationError("Invalid timestamp format") from exc

    age_seconds = abs(time.time() - parsed_timestamp)
    if age_seconds > _TIMESTAMP_TOLERANCE_SECONDS:
        raise HMACVerificationError(
            f"Timestamp expired: {age_seconds:.0f}s old (max {_TIMESTAMP_TOLERANCE_SECONDS}s)"
        )

    message = timestamp.encode() + b"." + body
    expected_signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise HMACVerificationError("HMAC signature mismatch")


def verify_api_key(provided_key: str, stored_records: Iterable[Mapping[str, Any]]) -> str:
    """Verify a plaintext API key against stored SHA-256 hashes."""

    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    for record in stored_records:
        if hmac.compare_digest(str(record["api_key_hash"]), provided_hash):
            if record.get("revoked_at") is not None:
                raise InvalidAPIKeyError("API key has been revoked")
            return str(record["tenant_id"])

    raise InvalidAPIKeyError("Unknown API key")


__all__ = [
    "HMACVerificationError",
    "InvalidAPIKeyError",
    "verify_api_key",
    "verify_retell_hmac",
]

"""Authentication helpers for voice webhooks and booking API access."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections.abc import Iterable, Mapping
from typing import Any


_TIMESTAMP_TOLERANCE_MS = 5 * 60 * 1000
_LEGACY_TIMESTAMP_TOLERANCE_SECONDS = 300
_RETELL_SIGNATURE_PATTERN = re.compile(r"v=(\d+),d=(.+)")


class HMACVerificationError(Exception):
    """Retell webhook signature verification failed."""


class InvalidAPIKeyError(Exception):
    """Booking API key is invalid, revoked, or unknown."""


def verify_retell_hmac(body: bytes, signature: str, timestamp: str | None = None) -> None:
    """Verify a Retell webhook signature.

    Primary path matches Retell's current SDK/webhook contract:
    `x-retell-signature: v=<timestamp_ms>,d=<sha256(body + timestamp_ms)>`,
    verified with `RETELL_API_KEY`.

    A legacy timestamp-based fallback remains for older local fixtures that still
    sign requests with `RETELL_WEBHOOK_SECRET` and a separate `x-retell-timestamp`
    header.
    """

    match = _RETELL_SIGNATURE_PATTERN.fullmatch(signature.strip())
    if match:
        secret = os.environ.get("RETELL_API_KEY")
        if not secret:
            raise RuntimeError("RETELL_API_KEY environment variable is not set")

        signed_timestamp_ms = int(match.group(1))
        signed_digest = match.group(2)
        age_ms = abs(int(time.time() * 1000) - signed_timestamp_ms)
        if age_ms > _TIMESTAMP_TOLERANCE_MS:
            raise HMACVerificationError(
                f"Timestamp expired: {age_ms}ms old (max {_TIMESTAMP_TOLERANCE_MS}ms)"
            )

        message = body + str(signed_timestamp_ms).encode()
        expected_digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_digest, signed_digest):
            raise HMACVerificationError("HMAC signature mismatch")
        return

    secret = os.environ.get("RETELL_WEBHOOK_SECRET")
    if not timestamp:
        if os.environ.get("RETELL_API_KEY"):
            raise HMACVerificationError("Invalid signature format")
        if not secret:
            raise RuntimeError("RETELL_API_KEY or RETELL_WEBHOOK_SECRET environment variable is not set")
        raise HMACVerificationError("Missing legacy timestamp header")

    if not secret:
        raise RuntimeError("RETELL_WEBHOOK_SECRET environment variable is not set for legacy webhook verification")

    try:
        parsed_timestamp = int(timestamp or "")
    except (TypeError, ValueError) as exc:
        raise HMACVerificationError("Invalid timestamp format") from exc

    age_seconds = abs(time.time() - parsed_timestamp)
    if age_seconds > _LEGACY_TIMESTAMP_TOLERANCE_SECONDS:
        raise HMACVerificationError(
            f"Timestamp expired: {age_seconds:.0f}s old (max {_LEGACY_TIMESTAMP_TOLERANCE_SECONDS}s)"
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

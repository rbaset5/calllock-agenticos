"""Authentication helpers for voice webhooks and booking API access."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Iterable, Mapping
from typing import Any


_TIMESTAMP_TOLERANCE_MS = 300_000  # 5 minutes in milliseconds


class HMACVerificationError(Exception):
    """Retell webhook signature verification failed."""


class InvalidAPIKeyError(Exception):
    """Booking API key is invalid, revoked, or unknown."""


def _parse_retell_signature_header(header: str) -> tuple[str, str]:
    """Parse Retell's combined signature header.

    Format: ``v=<timestamp_ms>,d=<hex_digest>``
    Returns (timestamp_ms_str, hex_digest).
    """
    parts: dict[str, str] = {}
    for segment in header.split(","):
        if "=" in segment:
            key, _, value = segment.partition("=")
            parts[key.strip()] = value.strip()

    ts = parts.get("v", "")
    digest = parts.get("d", "")
    if not ts or not digest:
        raise HMACVerificationError(
            f"Malformed x-retell-signature header: expected v=<ts>,d=<digest>, got '{header}'"
        )
    return ts, digest


def verify_retell_hmac(body: bytes, signature: str, timestamp: str | None = None) -> None:
    """Verify a Retell webhook HMAC-SHA256 signature.

    Retell sends a single ``x-retell-signature`` header with format
    ``v=<timestamp_ms>,d=<hex_digest>``.  The HMAC is computed as
    ``HMAC-SHA256(body + timestamp_ms_bytes, RETELL_API_KEY)``.

    For backwards compatibility, if *timestamp* is provided as a separate
    value (legacy callers), the function still works — but modern callers
    should pass the full ``x-retell-signature`` header as *signature* and
    leave *timestamp* as ``None``.
    """
    secret = os.environ.get("RETELL_API_KEY")
    if not secret:
        raise RuntimeError("RETELL_API_KEY environment variable is not set")

    # If timestamp was not provided separately, parse from combined header
    if not timestamp:
        timestamp, signature = _parse_retell_signature_header(signature)

    try:
        parsed_ts = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise HMACVerificationError("Invalid timestamp format") from exc

    now_ms = int(time.time() * 1000)
    age_ms = abs(now_ms - parsed_ts)
    if age_ms > _TIMESTAMP_TOLERANCE_MS:
        raise HMACVerificationError(
            f"Timestamp expired: {age_ms / 1000:.0f}s old (max {_TIMESTAMP_TOLERANCE_MS // 1000}s)"
        )

    # Retell SDK: HMAC-SHA256(body + timestamp_bytes, api_key)
    message = body + str(parsed_ts).encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
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

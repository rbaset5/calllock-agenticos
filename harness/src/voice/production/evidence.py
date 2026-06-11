"""Evidence capture helpers for Retell voice calls."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from db import repository


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(payload: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 hash for JSON-like payloads."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def record_event(
    *,
    tenant_id: str | None,
    call_id: str,
    retell_call_id: str,
    event_type: str,
    payload: Mapping[str, Any],
    source: str = "retell",
) -> dict[str, Any]:
    """Persist a normalized voice call event."""
    event = {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "retell_call_id": retell_call_id,
        "event_type": event_type,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "payload": dict(payload),
        "payload_hash": hash_payload(payload),
    }
    return repository.record_voice_call_event(event)


def record_tool_call(
    *,
    tenant_id: str | None,
    call_id: str,
    retell_call_id: str | None,
    tool_name: str,
    request_payload: Mapping[str, Any],
    response_payload: Mapping[str, Any] | None,
    status: str,
    latency_ms: int | None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Persist a normalized Retell tool call record."""
    record = {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "retell_call_id": retell_call_id,
        "tool_name": tool_name,
        "request_payload": dict(request_payload),
        "response_payload": dict(response_payload) if response_payload is not None else None,
        "status": status,
        "latency_ms": latency_ms,
        "error_type": error_type,
        "error_message": error_message,
    }
    return repository.record_voice_tool_call(record)


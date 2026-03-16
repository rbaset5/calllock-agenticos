from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[4]


def sms_outbox_root() -> Path:
    configured = os.getenv("CALLLOCK_SMS_OUTBOX_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "sms-outbox"


def _normalize_recipients(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    recipients: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in recipients:
            recipients.append(item.strip())
    return recipients


def _write_outbox(category: str, record: dict[str, Any]) -> Path:
    root = sms_outbox_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{category}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    return path


def deliver_sms(
    *,
    category: str,
    recipients: Any,
    message: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_recipients = _normalize_recipients(recipients)
    if not resolved_recipients:
        return {"channel": "sms", "delivered": False, "reason": "missing_sms_recipient"}

    outbox_record = {
        "recipients": resolved_recipients,
        "message": message,
        "payload": payload,
    }

    webhook_url = os.getenv("SMS_WEBHOOK_URL")
    if not webhook_url:
        path = _write_outbox(category, outbox_record)
        return {
            "channel": "sms",
            "delivered": True,
            "backend": "outbox",
            "destination": str(path),
            "recipients": resolved_recipients,
        }

    if httpx is None:
        path = _write_outbox(category, {**outbox_record, "webhook_error": "httpx_unavailable"})
        return {
            "channel": "sms",
            "delivered": False,
            "backend": "webhook_error_outbox",
            "destination": str(path),
            "recipients": resolved_recipients,
            "reason": "httpx_unavailable",
        }

    request_payload = {
        "recipients": resolved_recipients,
        "message": message,
        "payload": payload,
    }
    auth_token = os.getenv("SMS_WEBHOOK_BEARER_TOKEN")
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
    try:
        response = httpx.post(webhook_url, json=request_payload, headers=headers, timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch or outbox fallback
        path = _write_outbox(category, {**outbox_record, "webhook_error": str(exc)})
        return {
            "channel": "sms",
            "delivered": False,
            "backend": "webhook_error_outbox",
            "destination": str(path),
            "recipients": resolved_recipients,
            "reason": str(exc),
        }

    return {
        "channel": "sms",
        "delivered": True,
        "backend": "webhook",
        "destination": webhook_url,
        "recipients": resolved_recipients,
    }

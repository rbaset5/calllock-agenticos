from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]


def email_outbox_root() -> Path:
    configured = os.getenv("CALLLOCK_EMAIL_OUTBOX_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "email-outbox"


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
    root = email_outbox_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{category}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    return path


def deliver_email(
    *,
    category: str,
    recipients: Any,
    subject: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_recipients = _normalize_recipients(recipients)
    if not resolved_recipients:
        return {"channel": "email", "delivered": False, "reason": "missing_email_recipient"}

    outbox_record = {
        "recipients": resolved_recipients,
        "subject": subject,
        "payload": payload,
    }

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        path = _write_outbox(category, outbox_record)
        return {
            "channel": "email",
            "delivered": True,
            "backend": "outbox",
            "destination": str(path),
            "recipients": resolved_recipients,
        }

    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "calllock@example.test")
    message["To"] = ", ".join(resolved_recipients)
    message["Subject"] = subject
    message.set_content(json.dumps(payload, indent=2, sort_keys=True))

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as client:
            if smtp_use_tls:
                client.starttls()
            if smtp_username and smtp_password:
                client.login(smtp_username, smtp_password)
            client.send_message(message)
    except Exception as exc:  # pragma: no cover - exercised through tests via outbox path
        path = _write_outbox(category, {**outbox_record, "smtp_error": str(exc)})
        return {
            "channel": "email",
            "delivered": False,
            "backend": "smtp_error_outbox",
            "destination": str(path),
            "recipients": resolved_recipients,
            "reason": str(exc),
        }

    return {
        "channel": "email",
        "delivered": True,
        "backend": "smtp",
        "destination": f"smtp://{smtp_host}:{smtp_port}",
        "recipients": resolved_recipients,
    }

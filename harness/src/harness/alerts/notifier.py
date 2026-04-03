from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover
    class _HttpxShim:
        post = None

    httpx = _HttpxShim()  # type: ignore[assignment]

from harness.notifications.email_delivery import deliver_email
from harness.notifications.pager_delivery import deliver_pager
from harness.notifications.sms_delivery import deliver_sms

REPO_ROOT = Path(__file__).resolve().parents[3]


def _alert_root() -> Path:
    base = os.getenv("CALLLOCK_ALERT_ROOT")
    if base:
        return Path(base)
    return REPO_ROOT / ".context" / "alerts"


def _resolve_channels(tenant_config: dict[str, Any]) -> list[str]:
    channels = tenant_config.get("alert_channels", ["dashboard"])
    if not isinstance(channels, list):
        return ["dashboard"]
    resolved = []
    for channel in channels:
        if isinstance(channel, str) and channel not in resolved:
            resolved.append(channel)
    return resolved or ["dashboard"]


def _dashboard_payload(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": alert["id"],
        "tenant_id": alert.get("tenant_id"),
        "alert_type": alert["alert_type"],
        "severity": alert["severity"],
        "message": alert["message"],
        "metrics": alert.get("metrics", {}),
        "created_at": alert.get("created_at"),
    }


def _deliver_dashboard(alert: dict[str, Any]) -> dict[str, Any]:
    root = _alert_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "dashboard.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_dashboard_payload(alert), sort_keys=True))
        handle.write("\n")
    return {"channel": "dashboard", "delivered": True, "destination": str(path)}


def _deliver_webhook(alert: dict[str, Any], tenant_config: dict[str, Any]) -> dict[str, Any]:
    webhook_url = tenant_config.get("alert_webhook_url") or os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return {"channel": "webhook", "delivered": False, "reason": "missing_webhook_url"}
    if not callable(getattr(httpx, "post", None)):
        return {"channel": "webhook", "delivered": False, "reason": "httpx_unavailable"}
    try:
        response = httpx.post(webhook_url, json=_dashboard_payload(alert), timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch
        return {
            "channel": "webhook",
            "delivered": False,
            "destination": webhook_url,
            "reason": str(exc),
        }
    return {"channel": "webhook", "delivered": True, "destination": webhook_url}


def _deliver_email(alert: dict[str, Any], tenant_config: dict[str, Any]) -> dict[str, Any]:
    recipients = tenant_config.get("alert_email_to") or os.getenv("ALERT_EMAIL_TO")
    return deliver_email(
        category="alerts",
        recipients=recipients,
        subject=f"[{alert['severity'].upper()}] {alert['alert_type']}",
        payload=_dashboard_payload(alert),
    )


def _deliver_sms(alert: dict[str, Any], tenant_config: dict[str, Any]) -> dict[str, Any]:
    recipients = tenant_config.get("alert_sms_to") or os.getenv("ALERT_SMS_TO")
    return deliver_sms(
        category="alerts",
        recipients=recipients,
        message=f"[{alert['severity'].upper()}] {alert['alert_type']}: {alert['message']}",
        payload=_dashboard_payload(alert),
    )


def _deliver_pager(alert: dict[str, Any], tenant_config: dict[str, Any]) -> dict[str, Any]:
    targets = tenant_config.get("alert_pager_to") or os.getenv("ALERT_PAGER_TO")
    return deliver_pager(
        category="alerts",
        targets=targets,
        summary=f"{alert['alert_type']}: {alert['message']}",
        severity=alert["severity"],
        payload=_dashboard_payload(alert),
    )


def notify(alert: dict, tenant_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = tenant_config or {}
    detection_meta = (alert.get("metrics") or {}).get("detection", {})
    forced_channels = detection_meta.get("channels")
    if isinstance(forced_channels, list):
        channels = [channel for channel in forced_channels if isinstance(channel, str)]
        if not channels:
            return {
                "alert_id": alert["id"],
                "delivered": False,
                "channels": [],
            }
    else:
        channels = _resolve_channels(config)
    attempts = []
    for channel in channels:
        if channel == "dashboard":
            attempts.append(_deliver_dashboard(alert))
            continue
        if channel == "webhook":
            attempts.append(_deliver_webhook(alert, config))
            continue
        if channel == "email":
            attempts.append(_deliver_email(alert, config))
            continue
        if channel == "sms":
            attempts.append(_deliver_sms(alert, config))
            continue
        if channel == "pager":
            attempts.append(_deliver_pager(alert, config))
            continue
        attempts.append({"channel": channel, "delivered": False, "reason": "unsupported_channel"})
    return {
        "alert_id": alert["id"],
        "delivered": any(attempt.get("delivered", False) for attempt in attempts),
        "channels": attempts,
    }

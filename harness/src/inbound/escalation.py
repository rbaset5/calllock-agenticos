from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def should_escalate(action: str, total_score: int) -> bool:
    return action == "exceptional"


def should_auto_archive(action: str) -> bool:
    return action in {"spam", "non-lead"}


def build_escalation_payload(
    tenant_id: str,
    message_id: str,
    from_addr: str,
    subject: str,
    total_score: int,
    reasoning: str,
    action: str,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "message_id": message_id,
        "from_addr": from_addr,
        "subject": subject,
        "total_score": total_score,
        "reasoning": reasoning,
        "action": action,
        "priority": "high" if total_score >= 90 else "normal",
        "channel": "founder_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_system_alert_payload(tenant_id: str, alert_type: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "alert_type": alert_type,
        "details": details,
        # TODO(founder): Route operational alerts to the final channel set once alerting policy is finalized.
        "channel": "ops",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def check_quarantine_rate(total_messages: int, blocked_messages: int, threshold: float = 0.5) -> bool:
    if total_messages <= 0:
        return False
    return (blocked_messages / total_messages) > threshold


def check_consecutive_poll_failures(failure_count: int, threshold: int = 3) -> bool:
    return failure_count >= threshold

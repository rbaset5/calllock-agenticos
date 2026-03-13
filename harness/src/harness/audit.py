from __future__ import annotations

from typing import Any

from db.repository import create_audit_log


def log_audit_event(
    *,
    action_type: str,
    actor_id: str,
    reason: str,
    tenant_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return create_audit_log(
        {
            "tenant_id": tenant_id,
            "action_type": action_type,
            "actor_id": actor_id,
            "reason": reason,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
        }
    )

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from db.repository import get_tenant_config

logger = logging.getLogger("observability.inngest_emitter")

AGENT_STATE_CHANGED_EVENT = "calllock/agent.state.changed"


class InngestEventEmitter:
    """Best-effort Inngest emitter for office dashboard agent state transitions."""

    def _office_dashboard_enabled(
        self,
        tenant_id: str | None,
        tenant_config: dict[str, Any] | None = None,
    ) -> bool:
        if not tenant_id:
            return False

        config = tenant_config
        if config is None:
            try:
                config = get_tenant_config(tenant_id)
            except Exception:
                logger.warning(
                    "emit skipped: tenant_config lookup failed",
                    extra={"tenant_id": tenant_id},
                )
                return False

        return bool((config or {}).get("office_dashboard_enabled"))

    def emit_node_entry(
        self,
        *,
        agent_id: str | None,
        tenant_id: str | None,
        department: str | None,
        role: str | None,
        from_state: str | None,
        to_state: str | None,
        description: str | None = None,
        tenant_config: dict[str, Any] | None = None,
    ) -> None:
        if not agent_id or not tenant_id or not department or not role or not to_state:
            logger.warning(
                "emit skipped: missing required agent state fields",
                extra={
                    "agent_id": agent_id,
                    "tenant_id": tenant_id,
                    "department": department,
                    "role": role,
                    "to_state": to_state,
                },
            )
            return None

        if not self._office_dashboard_enabled(tenant_id, tenant_config):
            return None

        endpoint = os.getenv("INNGEST_EVENT_URL")
        if not endpoint:
            return None

        headers = {"Content-Type": "application/json"}
        event_key = os.getenv("INNGEST_EVENT_KEY")
        if event_key:
            headers["Authorization"] = f"Bearer {event_key}"

        payload = {
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "department": department,
            "role": role,
            "from_state": from_state or "",
            "to_state": to_state,
            "description": description,
        }

        try:
            response = httpx.post(
                endpoint,
                json={"name": AGENT_STATE_CHANGED_EVENT, "data": payload},
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError, TypeError) as exc:
            logger.error(
                "emit failed: %s",
                str(exc),
                extra={
                    "event_name": AGENT_STATE_CHANGED_EVENT,
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "to_state": to_state,
                    "error_type": type(exc).__name__,
                    "error_detail": str(exc),
                },
            )
        return None

from __future__ import annotations

from typing import Any


def _response_data(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", result)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _scoped_agent_state_rows(
    *,
    supabase_client: Any,
    tenant_id: str | None = None,
    agent_id: str | None = None,
    department: str | None = None,
    non_idle_only: bool = False,
) -> list[dict[str, Any]]:
    query = supabase_client.table("agent_office_state").select("*")
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    if agent_id:
        query = query.eq("agent_id", agent_id)
    if department:
        query = query.eq("department", department)
    if non_idle_only:
        query = query.neq("current_state", "idle")
    query = query.order("updated_at", desc=True)
    return _response_data(query.execute())


def check_agent_available(agent_id: str, supabase_client: Any) -> bool:
    """Check agent_office_state. Available if current_state == 'idle'."""
    rows = _scoped_agent_state_rows(
        supabase_client=supabase_client,
        agent_id=agent_id,
    )
    if not rows:
        return True
    return rows[0].get("current_state") == "idle"


def check_department_capacity(department: str, supabase_client: Any) -> int:
    """Count non-idle agents in department. Cap is 3."""
    rows = _scoped_agent_state_rows(
        supabase_client=supabase_client,
        department=department,
        non_idle_only=True,
    )
    return len(rows)


def _check_agent_available_for_tenant(
    *,
    tenant_id: str,
    agent_id: str,
    supabase_client: Any,
) -> bool:
    rows = _scoped_agent_state_rows(
        supabase_client=supabase_client,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )
    if not rows:
        return True
    return rows[0].get("current_state") == "idle"


def _check_department_capacity_for_tenant(
    *,
    tenant_id: str,
    department: str,
    supabase_client: Any,
) -> int:
    rows = _scoped_agent_state_rows(
        supabase_client=supabase_client,
        tenant_id=tenant_id,
        department=department,
        non_idle_only=True,
    )
    return len(rows)

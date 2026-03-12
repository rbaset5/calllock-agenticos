from __future__ import annotations

from collections.abc import Iterable


def resolve_granted_tools(
    authored: Iterable[str],
    tenant_allowed: Iterable[str] | None = None,
    environment_allowed: Iterable[str] | None = None,
    runtime_denied: Iterable[str] | None = None,
) -> list[str]:
    authored_set = {tool for tool in authored if tool}
    tenant_set = set(tenant_allowed or authored_set)
    environment_set = set(environment_allowed or authored_set)
    denied_set = set(runtime_denied or [])
    granted = authored_set & tenant_set & environment_set
    return sorted(granted - denied_set)

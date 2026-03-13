from __future__ import annotations

from typing import Any


def assert_tenant_access(tenant_id: str, artifact: dict[str, Any]) -> None:
    if artifact.get("tenant_id") != tenant_id:
        raise PermissionError("Artifact access denied for tenant")

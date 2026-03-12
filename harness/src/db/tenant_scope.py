from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantScope:
    tenant_id: str

    def apply_sql(self, sql: str) -> str:
        prefix = f"select set_config('app.current_tenant', '{self.tenant_id}', true); "
        return prefix + sql


def with_tenant_scope(tenant_id: str) -> TenantScope:
    return TenantScope(tenant_id=tenant_id)

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_SEED_PATH = REPO_ROOT / "supabase" / "local_seed.json"


@lru_cache(maxsize=1)
def load_local_seed() -> dict[str, Any]:
    return json.loads(LOCAL_SEED_PATH.read_text())


def _matches(identifier: str, record: dict[str, Any]) -> bool:
    return identifier in {record.get("id"), record.get("slug"), record.get("tenant_id")}


def get_tenant(identifier: str) -> dict[str, Any]:
    for tenant in load_local_seed()["tenants"]:
        if _matches(identifier, tenant):
            return tenant
    raise KeyError(f"Unknown tenant: {identifier}")


def get_tenant_config(identifier: str) -> dict[str, Any]:
    for config in load_local_seed()["tenant_configs"]:
        if _matches(identifier, config):
            return config
    tenant = get_tenant(identifier)
    return {"tenant_id": tenant["id"], "industry_pack_id": tenant["industry_pack_id"], "allowed_tools": []}


def get_compliance_rules(identifier: str) -> list[dict[str, Any]]:
    tenant = get_tenant(identifier)
    rules = []
    for rule in load_local_seed()["compliance_rules"]:
        if rule.get("tenant_id") in (None, tenant["id"]):
            rules.append(rule)
    return rules

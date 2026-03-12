from __future__ import annotations

from typing import Any

from db import local_repository, supabase_repository
from harness.artifacts import write_run_artifact


def using_supabase() -> bool:
    return supabase_repository.is_configured()


def get_tenant(identifier: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_tenant(identifier)
    return local_repository.get_tenant(identifier)


def get_tenant_config(identifier: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_tenant_config(identifier)
    return local_repository.get_tenant_config(identifier)


def get_compliance_rules(identifier: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_compliance_rules(identifier)
    return local_repository.get_compliance_rules(identifier)


def persist_run_record(record: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.persist_run_record(record)
    record["artifact_path"] = write_run_artifact(record)
    return record

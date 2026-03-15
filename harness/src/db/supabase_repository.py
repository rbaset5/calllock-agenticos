from __future__ import annotations

import os
import re
from typing import Any

import httpx


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1"


def _raise_for_status(response: httpx.Response, table: str) -> None:
    if response.status_code == 404:
        raise RuntimeError(
            f"Supabase table or endpoint '{table}' was not found. Apply the repo migrations before using the live repository path."
        )
    response.raise_for_status()


def _fetch_first(table: str, params: dict[str, str]) -> dict[str, Any]:
    response = httpx.get(
        f"{_base_url()}/{table}",
        params={**params, "limit": "1"},
        headers=_headers(),
        timeout=10.0,
    )
    _raise_for_status(response, table)
    data = response.json()
    if not data:
        raise KeyError(f"No row found in {table} for params {params}")
    return data[0]


def get_tenant(identifier: str) -> dict[str, Any]:
    if UUID_RE.match(identifier):
        return _fetch_first("tenants", {"id": f"eq.{identifier}"})
    return _fetch_first("tenants", {"slug": f"eq.{identifier}"})


def get_tenant_config(identifier: str) -> dict[str, Any]:
    tenant = get_tenant(identifier)
    return _fetch_first("tenant_configs", {"tenant_id": f"eq.{tenant['id']}"})


def get_compliance_rules(identifier: str) -> list[dict[str, Any]]:
    tenant = get_tenant(identifier)
    response = httpx.get(
        f"{_base_url()}/compliance_rules",
        params={"or": f"(tenant_id.is.null,tenant_id.eq.{tenant['id']})"},
        headers=_headers(),
        timeout=10.0,
    )
    _raise_for_status(response, "compliance_rules")
    return response.json()


def persist_run_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "tenant_id": record["tenant_id"],
        "origin_worker_id": record["worker_id"],
        "origin_run_id": record["run_id"],
        "job_type": "harness_run",
        "status": record["status"],
        "idempotency_key": record["run_id"],
        "payload": {},
        "result": record,
    }
    response = httpx.post(
        f"{_base_url()}/jobs",
        params={"on_conflict": "idempotency_key"},
        headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
        json=payload,
        timeout=10.0,
    )
    _raise_for_status(response, "jobs")
    data = response.json()
    record["supabase_result"] = data[0] if data else {}
    return record

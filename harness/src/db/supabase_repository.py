from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
import re
from typing import Any
from uuid import uuid4

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from harness.artifacts.lifecycle import validate_transition
from harness.alerts.lifecycle import validate_alert_transition
from growth.memory.models import GrowthDuplicateError
from harness.incident_sync_payload import build_incident_sync_payload
from harness.jobs.state_machine import validate_transition as validate_job_transition
from harness.resilience.retry import retry_call


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(httpx and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


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


def _is_retryable_error(exc: Exception) -> bool:
    if httpx is None:
        return False
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _request(method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, prefer: str | None = None) -> Any:
    if httpx is None:
        raise RuntimeError("httpx is required for live Supabase access")

    def _perform() -> Any:
        headers = _headers()
        if prefer:
            headers["Prefer"] = prefer
        response = httpx.request(
            method,
            f"{_base_url()}/{table}",
            params=params,
            headers=headers,
            json=json,
            timeout=10.0,
        )
        _raise_for_status(response, table)
        if response.content:
            return response.json()
        return None

    return retry_call(_perform, attempts=3, delay_seconds=0.15, retryable=_is_retryable_error)


def _is_duplicate_status_error(exc: Exception) -> bool:
    if httpx is None or not isinstance(exc, httpx.HTTPStatusError):
        return False
    if exc.response.status_code != 409:
        return False
    try:
        payload = exc.response.json()
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    message = str(payload.get("message", ""))
    details = str(payload.get("details", ""))
    return code == "23505" or "duplicate key value" in message.lower() or "duplicate key value" in details.lower()


def _insert_growth_row(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = _request("POST", table, json=payload, prefer="return=representation")
    except Exception as exc:
        if _is_duplicate_status_error(exc):
            raise GrowthDuplicateError(table) from exc
        raise
    return data[0] if data else payload


def _rpc(function_name: str, payload: dict[str, Any]) -> Any:
    return _request("POST", f"rpc/{function_name}", json=payload, prefer="return=representation")


def _fetch_first(table: str, params: dict[str, str]) -> dict[str, Any]:
    data = _request("GET", table, params={**params, "limit": "1"})
    if not data:
        raise KeyError(f"No row found in {table} for params {params}")
    return data[0]


def _fetch_optional(table: str, params: dict[str, str]) -> dict[str, Any] | None:
    data = _request("GET", table, params={**params, "limit": "1"})
    if not data:
        return None
    return data[0]


def get_tenant(identifier: str) -> dict[str, Any]:
    if UUID_RE.match(identifier):
        return _fetch_first("tenants", {"id": f"eq.{identifier}"})
    return _fetch_first("tenants", {"slug": f"eq.{identifier}"})


def list_tenants() -> list[dict[str, Any]]:
    return _request("GET", "tenants")


def get_tenant_config(identifier: str) -> dict[str, Any]:
    tenant = get_tenant(identifier)
    return _fetch_first("tenant_configs", {"tenant_id": f"eq.{tenant['id']}"})


def get_compliance_rules(identifier: str) -> list[dict[str, Any]]:
    tenant = get_tenant(identifier)
    return _request("GET", "compliance_rules", params={"or": f"(tenant_id.is.null,tenant_id.eq.{tenant['id']})"})


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
    data = _request(
        "POST",
        "jobs",
        params={"on_conflict": "idempotency_key"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    result = dict(record)
    result["job"] = data[0] if data else {}
    return result


def upsert_agent_report(report: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "agent_reports",
        params={"on_conflict": "agent_id,report_date,tenant_id"},
        json=report,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else report


def create_shadow_comparison(record: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "shadow_comparisons", json=record, prefer="return=representation")
    return data[0] if data else record


def create_artifact(record: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "artifacts", json=record, prefer="return=representation")
    return data[0] if data else record


def update_artifact_lifecycle(artifact_id: str, target_state: str, *, tenant_id: str) -> dict[str, Any]:
    artifact = _fetch_first("artifacts", {"id": f"eq.{artifact_id}", "tenant_id": f"eq.{tenant_id}"})
    validate_transition(artifact["lifecycle_state"], target_state)
    data = _request("PATCH", "artifacts", params={"id": f"eq.{artifact_id}"}, json={"lifecycle_state": target_state}, prefer="return=representation")
    return data[0]


def list_artifacts(tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "artifacts", params={"tenant_id": f"eq.{tenant_id}"})


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "jobs",
        params={"on_conflict": "idempotency_key"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def update_job_status(job_id: str, status: str, *, result: dict[str, Any] | None = None) -> dict[str, Any]:
    job = _fetch_first("jobs", {"id": f"eq.{job_id}"})
    validate_job_transition(job["status"], status)
    patch = {"status": status}
    if result is not None:
        patch["result"] = result
    data = _request("PATCH", "jobs", params={"id": f"eq.{job_id}"}, json=patch, prefer="return=representation")
    return data[0]


def get_job(job_id: str) -> dict[str, Any]:
    return _fetch_first("jobs", {"id": f"eq.{job_id}"})


def list_jobs(*, tenant_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id is not None:
        params["tenant_id"] = f"eq.{tenant_id}"
    if run_id is not None:
        params["origin_run_id"] = f"eq.{run_id}"
    return _request("GET", "jobs", params=params)


def count_active_jobs(tenant_id: str) -> int:
    jobs = _request("GET", "jobs", params={"tenant_id": f"eq.{tenant_id}", "status": "in.(queued,running)"})
    return len(jobs)


def create_tenant(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "tenants", json=payload, prefer="return=representation")
    return data[0]


def create_tenant_config(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "tenant_configs", json=payload, prefer="return=representation")
    return data[0]


def update_tenant_config(tenant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = _request("PATCH", "tenant_configs", params={"tenant_id": f"eq.{tenant_id}"}, json=updates, prefer="return=representation")
    return data[0]


def delete_tenant(identifier: str) -> None:
    tenant = get_tenant(identifier)
    _request("DELETE", "tenants", params={"id": f"eq.{tenant['id']}"})


def save_kill_switch(payload: dict[str, Any]) -> dict[str, Any]:
    params = {"scope": f"eq.{payload['scope']}"}
    if payload.get("scope_id") is None:
        params["scope_id"] = "is.null"
    else:
        params["scope_id"] = f"eq.{payload['scope_id']}"
    existing = _request("GET", "kill_switches", params=params)
    if existing:
        data = _request("PATCH", "kill_switches", params=params, json=payload, prefer="return=representation")
        return data[0]
    data = _request("POST", "kill_switches", json=payload, prefer="return=representation")
    return data[0]


def list_kill_switches(*, active_only: bool = False) -> list[dict[str, Any]]:
    params = {"active": "eq.true"} if active_only else {}
    return _request("GET", "kill_switches", params=params)


def create_alert(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "alerts", json=payload, prefer="return=representation")
    return data[0]


def create_alert_and_sync_incident(payload: dict[str, Any]) -> dict[str, Any]:
    alert_payload = dict(payload)
    alert_payload.setdefault("id", str(uuid4()))
    tenant_config = get_tenant_config(alert_payload["tenant_id"]) if alert_payload.get("tenant_id") else {}
    incident_sync = build_incident_sync_payload(alert_payload, tenant_config)
    try:
        data = _rpc(
            "create_alert_and_sync_incident",
            {
                "p_alert": alert_payload,
                "p_incident_sync": incident_sync,
            },
        )
    except Exception as exc:
        raise _translate_alert_sync_rpc_error(exc) from exc
    return _first_row(data)


def list_alerts(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if status:
        params["status"] = f"eq.{status}"
    return _request("GET", "alerts", params=params)


def update_alert(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    alert = _fetch_first("alerts", {"id": f"eq.{alert_id}"})
    if "status" in updates:
        validate_alert_transition(alert.get("status", "open"), updates["status"])
    data = _request("PATCH", "alerts", params={"id": f"eq.{alert_id}"}, json=updates, prefer="return=representation")
    return data[0]


def _translate_alert_sync_rpc_error(exc: Exception) -> Exception:
    message = _extract_rpc_error_message(exc)
    if not message:
        return exc
    if message.startswith("CLLKAS_NOT_FOUND:"):
        return KeyError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKAS_INVALID:"):
        return ValueError(message.split(":", 1)[1].strip())
    return exc


def update_alert_and_sync_incident(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    current = _fetch_first("alerts", {"id": f"eq.{alert_id}"})
    merged_alert = {**current, **updates}
    if "status" in updates:
        validate_alert_transition(current.get("status", "open"), updates["status"])
    tenant_config = get_tenant_config(current["tenant_id"]) if current.get("tenant_id") else {}
    incident_sync = build_incident_sync_payload(merged_alert, tenant_config)
    try:
        data = _rpc(
            "mutate_alert_and_sync_incident",
            {
                "p_alert_id": alert_id,
                "p_updates": updates,
                "p_incident_sync": incident_sync,
            },
        )
    except Exception as exc:
        raise _translate_alert_sync_rpc_error(exc) from exc
    return _first_row(data)


def upsert_incident(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "incidents",
        params={"on_conflict": "incident_key"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def _translate_incident_sync_rpc_error(exc: Exception) -> Exception:
    message = _extract_rpc_error_message(exc)
    if not message:
        return exc
    if message.startswith("CLLKIS_NOT_FOUND:"):
        return KeyError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKIS_INVALID:"):
        return ValueError(message.split(":", 1)[1].strip())
    return exc


def sync_incident_from_alert(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = _rpc(
            "sync_incident_from_alert",
            {
                "p_incident_key": payload["incident_key"],
                "p_tenant_id": payload.get("tenant_id"),
                "p_alert_id": payload.get("alert_id"),
                "p_alert_type": payload["alert_type"],
                "p_severity": payload.get("severity", "medium"),
                "p_alert_status": payload.get("alert_status", "open"),
                "p_alert_created_at": payload.get("alert_created_at"),
                "p_alert_last_observed_at": payload.get("alert_last_observed_at"),
                "p_alert_resolved_at": payload.get("alert_resolved_at"),
                "p_alert_occurrence_count": payload.get("alert_occurrence_count", 1),
                "p_incident_domain": payload.get("incident_domain", "general"),
                "p_incident_category": payload.get("incident_category", payload["alert_type"]),
                "p_remediation_category": payload.get("remediation_category", "manual_review"),
                "p_incident_urgency": payload.get("incident_urgency", payload.get("severity", "medium")),
                "p_runbook_id": payload.get("runbook_id"),
                "p_runbook_title": payload.get("runbook_title"),
                "p_runbook_steps": payload.get("runbook_steps", []),
                "p_completion_policy": payload.get("completion_policy", {"required_workflow_statuses": []}),
                "p_approval_policy": payload.get("approval_policy", {"required_workflow_statuses": []}),
                "p_initial_runbook_progress": payload.get("initial_runbook_progress", []),
                "p_initial_runbook_progress_summary": payload.get(
                    "initial_runbook_progress_summary",
                    {"total_steps": 0, "completed_steps": 0, "pending_steps": 0},
                ),
                "p_initial_runbook_execution_plan": payload.get(
                    "initial_runbook_execution_plan",
                    {"next_runnable_steps": [], "blocked_steps": [], "completed_steps": [], "parallel_groups": {}},
                ),
            },
        )
    except Exception as exc:
        raise _translate_incident_sync_rpc_error(exc) from exc
    return _first_row(data)


def list_incidents(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if status:
        params["status"] = f"eq.{status}"
    return _request("GET", "incidents", params=params)


def update_incident(incident_id: str, updates: dict[str, Any], *, expected_revision: int | None = None) -> dict[str, Any]:
    params = {"id": f"eq.{incident_id}"}
    payload = dict(updates)
    if expected_revision is not None:
        params["incident_revision"] = f"eq.{expected_revision}"
        payload["incident_revision"] = expected_revision + 1
    data = _request("PATCH", "incidents", params=params, json=payload, prefer="return=representation")
    if not data:
        if expected_revision is not None:
            raise ValueError(f"incident revision conflict: expected {expected_revision}")
        raise KeyError(f"Unknown incident: {incident_id}")
    return data[0]


def _extract_rpc_error_message(exc: Exception) -> str | None:
    if httpx is None or not isinstance(exc, httpx.HTTPStatusError):
        return None
    try:
        payload = exc.response.json()
    except Exception:
        return exc.response.text or str(exc)
    if isinstance(payload, dict):
        for key in ("message", "details", "hint"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return exc.response.text or str(exc)


def _translate_incident_runbook_rpc_error(exc: Exception) -> Exception:
    message = _extract_rpc_error_message(exc)
    if not message:
        return exc
    if message.startswith("CLLKRB_NOT_FOUND:"):
        return KeyError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKRB_INDEX:"):
        return IndexError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKRB_INCIDENT_CONFLICT:"):
        return ValueError(f"incident revision conflict: {message.split(':', 1)[1].strip()}")
    if message.startswith("CLLKRB_STEP_CONFLICT:"):
        return ValueError(f"runbook step revision conflict: {message.split(':', 1)[1].strip()}")
    if message.startswith("CLLKRB_INVALID:") or message.startswith("CLLKRB_STATE:"):
        return ValueError(message.split(":", 1)[1].strip())
    return exc


def _first_row(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        if not data:
            raise KeyError("No row returned from Supabase RPC")
        return data[0]
    if isinstance(data, dict):
        return data
    raise RuntimeError(f"Unexpected Supabase RPC response: {data!r}")


def update_incident_runbook_progress(
    incident_id: str,
    *,
    step_index: int,
    status: str,
    actor_id: str,
    note: str = "",
    expected_revision: int | None = None,
    expected_step_revision: int | None = None,
) -> dict[str, Any]:
    try:
        data = _rpc(
            "mutate_incident_runbook_step",
            {
                "p_incident_id": incident_id,
                "p_step_index": step_index,
                "p_actor_id": actor_id,
                "p_operation": "progress",
                "p_status": status,
                "p_note": note,
                "p_expected_revision": expected_revision,
                "p_expected_step_revision": expected_step_revision,
            },
        )
    except Exception as exc:
        raise _translate_incident_runbook_rpc_error(exc) from exc
    return _first_row(data)


def update_incident_runbook_assignment(
    incident_id: str,
    *,
    step_index: int,
    actor_id: str,
    action: str,
    assigned_to: str | None = None,
    claim_ttl_seconds: int = 600,
    now_iso: str | None = None,
    expected_revision: int | None = None,
    expected_step_revision: int | None = None,
) -> dict[str, Any]:
    try:
        data = _rpc(
            "mutate_incident_runbook_step",
            {
                "p_incident_id": incident_id,
                "p_step_index": step_index,
                "p_actor_id": actor_id,
                "p_operation": "assignment",
                "p_action": action,
                "p_assigned_to": assigned_to,
                "p_claim_ttl_seconds": claim_ttl_seconds,
                "p_expected_revision": expected_revision,
                "p_expected_step_revision": expected_step_revision,
                "p_now": now_iso,
            },
        )
    except Exception as exc:
        raise _translate_incident_runbook_rpc_error(exc) from exc
    return _first_row(data)


def _translate_incident_workflow_rpc_error(exc: Exception) -> Exception:
    message = _extract_rpc_error_message(exc)
    if not message:
        return exc
    if message.startswith("CLLKWF_NOT_FOUND:"):
        return KeyError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKWF_CONFLICT:"):
        return ValueError(f"incident revision conflict: {message.split(':', 1)[1].strip()}")
    if message.startswith("CLLKWF_INVALID:"):
        return ValueError(message.split(":", 1)[1].strip())
    return exc


def update_incident_workflow(
    incident_id: str,
    *,
    workflow_status: str,
    actor_id: str,
    assigned_to: str | None = None,
    operator_notes: str = "",
    last_assignment_reason: str | None = None,
    assignment_history_entry: dict[str, Any] | None = None,
    now_iso: str | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    try:
        data = _rpc(
            "mutate_incident_workflow",
            {
                "p_incident_id": incident_id,
                "p_workflow_status": workflow_status,
                "p_actor_id": actor_id,
                "p_assigned_to": assigned_to,
                "p_operator_notes": operator_notes,
                "p_last_assignment_reason": last_assignment_reason,
                "p_assignment_history_entry": assignment_history_entry,
                "p_now": now_iso,
                "p_expected_revision": expected_revision,
            },
        )
    except Exception as exc:
        raise _translate_incident_workflow_rpc_error(exc) from exc
    return _first_row(data)


def _translate_incident_reminder_rpc_error(exc: Exception) -> Exception:
    message = _extract_rpc_error_message(exc)
    if not message:
        return exc
    if message.startswith("CLLKRM_NOT_FOUND:"):
        return KeyError(message.split(":", 1)[1].strip())
    if message.startswith("CLLKRM_CONFLICT:"):
        return ValueError(f"incident revision conflict: {message.split(':', 1)[1].strip()}")
    if message.startswith("CLLKRM_INVALID:"):
        return ValueError(message.split(":", 1)[1].strip())
    return exc


def update_incident_reminder(
    incident_id: str,
    *,
    actor_id: str,
    reminder_count: int,
    last_reminded_at: str,
    assigned_to: str | None = None,
    last_assignment_reason: str | None = None,
    assignment_history_entry: dict[str, Any] | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    try:
        data = _rpc(
            "mutate_incident_reminder",
            {
                "p_incident_id": incident_id,
                "p_actor_id": actor_id,
                "p_reminder_count": reminder_count,
                "p_last_reminded_at": last_reminded_at,
                "p_assigned_to": assigned_to,
                "p_last_assignment_reason": last_assignment_reason,
                "p_assignment_history_entry": assignment_history_entry,
                "p_expected_revision": expected_revision,
            },
        )
    except Exception as exc:
        raise _translate_incident_reminder_rpc_error(exc) from exc
    return _first_row(data)


def save_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "experiments", json=payload, prefer="return=representation")
    return data[0]


def list_experiments() -> list[dict[str, Any]]:
    return _request("GET", "experiments")


def acquire_lock(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "experiment_locks", json=payload, prefer="return=representation")
    return data[0]


def release_lock(mutation_surface: str) -> None:
    _request("DELETE", "experiment_locks", params={"mutation_surface": f"eq.{mutation_surface}"})


def heartbeat_lock(mutation_surface: str, ttl_seconds: int) -> dict[str, Any]:
    data = _request(
        "PATCH",
        "experiment_locks",
        params={"mutation_surface": f"eq.{mutation_surface}"},
        json={"ttl_seconds": ttl_seconds},
        prefer="return=representation",
    )
    return data[0]


def save_customer_content(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "customer_content", json=payload, prefer="return=representation")
    return data[0]


def list_customer_content(tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "customer_content", params={"tenant_id": f"eq.{tenant_id}"})


def delete_customer_content_before(tenant_id: str, cutoff_iso: str, *, dry_run: bool = False) -> int:
    existing = _request("GET", "customer_content", params={"tenant_id": f"eq.{tenant_id}", "created_at": f"lt.{cutoff_iso}"})
    if not dry_run and existing:
        _request("DELETE", "customer_content", params={"tenant_id": f"eq.{tenant_id}", "created_at": f"lt.{cutoff_iso}"})
    return len(existing)


def save_eval_run(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "eval_runs", json=payload, prefer="return=representation")
    return data[0]


def list_eval_runs(*, tenant_id: str | None = None) -> list[dict[str, Any]]:
    params = {"tenant_id": f"eq.{tenant_id}"} if tenant_id else {}
    return _request("GET", "eval_runs", params=params)


def create_audit_log(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "audit_logs", json=payload, prefer="return=representation")
    return data[0]


def list_audit_logs(*, tenant_id: str | None = None, action_type: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if action_type:
        params["action_type"] = f"eq.{action_type}"
    return _request("GET", "audit_logs", params=params)


def delete_audit_logs_before(cutoff_iso: str, *, tenant_id: str | None = None, dry_run: bool = False) -> int:
    params: dict[str, str] = {"created_at": f"lt.{cutoff_iso}"}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    existing = _request("GET", "audit_logs", params=params)
    if not dry_run and existing:
        _request("DELETE", "audit_logs", params=params)
    return len(existing)


def create_approval_request(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "approval_requests", json=payload, prefer="return=representation")
    return data[0]


def update_approval_request(approval_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = _request("PATCH", "approval_requests", params={"id": f"eq.{approval_id}"}, json=updates, prefer="return=representation")
    return data[0]


def list_approval_requests(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if status:
        params["status"] = f"eq.{status}"
    return _request("GET", "approval_requests", params=params)


def create_skill_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "skill_candidates", json=payload, prefer="return=representation")
    return data[0] if data else payload


def list_skill_candidates(*, tenant_id: str | None = None, status: str | None = None, worker_id: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if status:
        params["status"] = f"eq.{status}"
    if worker_id:
        params["worker_id"] = f"eq.{worker_id}"
    return _request("GET", "skill_candidates", params=params)


def update_skill_candidate(candidate_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = _request("PATCH", "skill_candidates", params={"id": f"eq.{candidate_id}"}, json=updates, prefer="return=representation")
    return data[0]


def upsert_scheduler_backlog_entry(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "scheduler_backlog",
        params={"on_conflict": "tenant_id,job_type,scheduled_for"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def list_scheduler_backlog(
    *,
    tenant_id: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if tenant_id:
        params["tenant_id"] = f"eq.{tenant_id}"
    if job_type:
        params["job_type"] = f"eq.{job_type}"
    if status:
        params["status"] = f"eq.{status}"
    return _request("GET", "scheduler_backlog", params=params)


def update_scheduler_backlog_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "PATCH",
        "scheduler_backlog",
        params={"id": f"eq.{entry_id}"},
        json=updates,
        prefer="return=representation",
    )
    return data[0]


def claim_scheduler_backlog_entries(
    *,
    job_type: str,
    claimed_before_iso: str,
    max_entries: int,
    claimer_id: str,
    claim_ttl_seconds: int,
) -> list[dict[str, Any]]:
    data = _rpc(
        "claim_scheduler_backlog_entries",
        {
            "p_job_type": job_type,
            "p_claimed_before": claimed_before_iso,
            "p_max_entries": max_entries,
            "p_claimer_id": claimer_id,
            "p_claim_ttl_seconds": claim_ttl_seconds,
        },
    )
    return data or []


def insert_inbound_message(msg: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "inbound_messages",
        params={"on_conflict": "tenant_id,rfc_message_id"},
        json=msg,
        prefer="resolution=ignore-duplicates,return=representation",
    )
    if data:
        return data[0]
    logger.info("dedup_hit", extra={"tenant_id": msg["tenant_id"], "rfc_message_id": msg["rfc_message_id"]})
    existing = _fetch_optional(
        "inbound_messages",
        {"tenant_id": f"eq.{msg['tenant_id']}", "rfc_message_id": f"eq.{msg['rfc_message_id']}"},
    )
    if existing is None:
        raise KeyError(f"Duplicate inbound message not found for rfc_message_id={msg['rfc_message_id']}")
    return existing


def get_inbound_message(tenant_id: str, message_id: str) -> dict[str, Any] | None:
    return _fetch_optional("inbound_messages", {"tenant_id": f"eq.{tenant_id}", "id": f"eq.{message_id}"})


def get_inbound_messages_by_thread(tenant_id: str, thread_id: str) -> list[dict[str, Any]]:
    return _request(
        "GET",
        "inbound_messages",
        params={"tenant_id": f"eq.{tenant_id}", "thread_id": f"eq.{thread_id}", "order": "received_at.asc"},
    )


def get_pending_scoring_messages(tenant_id: str, max_age_hours: int = 24) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    return _request(
        "GET",
        "inbound_messages",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "scoring_status": "eq.pending",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.asc",
        },
    )


def update_inbound_message_scoring(tenant_id: str, message_id: str, scoring_data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in scoring_data.items()
        if key in {"scoring_status", "action", "total_score", "score_dimensions", "score_reasoning", "rubric_hash"}
    }
    payload["updated_at"] = scoring_data.get("updated_at", datetime.now(timezone.utc).isoformat())
    data = _request(
        "PATCH",
        "inbound_messages",
        params={"tenant_id": f"eq.{tenant_id}", "id": f"eq.{message_id}"},
        json=payload,
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown inbound message: {message_id}")
    return data[0]


def update_inbound_message_prospect(tenant_id: str, message_id: str, prospect_id: str) -> dict[str, Any]:
    data = _request(
        "PATCH",
        "inbound_messages",
        params={"tenant_id": f"eq.{tenant_id}", "id": f"eq.{message_id}"},
        json={"prospect_id": prospect_id, "updated_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown inbound message: {message_id}")
    return data[0]


def update_inbound_message_stage(tenant_id: str, message_id: str, stage: str) -> dict[str, Any]:
    data = _request(
        "PATCH",
        "inbound_messages",
        params={"tenant_id": f"eq.{tenant_id}", "id": f"eq.{message_id}"},
        json={"stage": stage, "updated_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown inbound message: {message_id}")
    return data[0]


def insert_inbound_draft(draft: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "inbound_drafts",
        params={"on_conflict": "tenant_id,message_id"},
        json=draft,
        prefer="resolution=ignore-duplicates,return=representation",
    )
    if data:
        return data[0]
    logger.info("dedup_hit", extra={"tenant_id": draft["tenant_id"], "message_id": draft["message_id"]})
    existing = _fetch_optional(
        "inbound_drafts",
        {"tenant_id": f"eq.{draft['tenant_id']}", "message_id": f"eq.{draft['message_id']}"},
    )
    if existing is None:
        raise KeyError(f"Duplicate inbound draft not found for message_id={draft['message_id']}")
    return existing


def get_inbound_draft(tenant_id: str, message_id: str) -> dict[str, Any] | None:
    return _fetch_optional("inbound_drafts", {"tenant_id": f"eq.{tenant_id}", "message_id": f"eq.{message_id}"})


def get_pending_review_drafts(tenant_id: str) -> list[dict[str, Any]]:
    return _request(
        "GET",
        "inbound_drafts",
        params={"tenant_id": f"eq.{tenant_id}", "send_status": "eq.pending_review", "order": "created_at.asc"},
    )


def update_inbound_draft_gate(tenant_id: str, draft_id: str, gate_data: dict[str, Any]) -> dict[str, Any]:
    payload = {key: gate_data[key] for key in ("content_gate_status", "content_gate_flags") if key in gate_data}
    data = _request(
        "PATCH",
        "inbound_drafts",
        params={"tenant_id": f"eq.{tenant_id}", "id": f"eq.{draft_id}"},
        json=payload,
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown inbound draft: {draft_id}")
    return data[0]


def update_inbound_draft_status(tenant_id: str, draft_id: str, send_status: str) -> dict[str, Any]:
    data = _request(
        "PATCH",
        "inbound_drafts",
        params={"tenant_id": f"eq.{tenant_id}", "id": f"eq.{draft_id}"},
        json={"send_status": send_status},
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown inbound draft: {draft_id}")
    return data[0]


def insert_stage_transition(transition: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "inbound_stage_log", json=transition, prefer="return=representation")
    return data[0] if data else transition


def get_latest_stage(tenant_id: str, thread_id: str) -> dict[str, Any] | None:
    return _fetch_optional(
        "inbound_stage_log",
        {"tenant_id": f"eq.{tenant_id}", "thread_id": f"eq.{thread_id}", "order": "created_at.desc"},
    )


def get_stage_history(tenant_id: str, thread_id: str) -> list[dict[str, Any]]:
    return _request(
        "GET",
        "inbound_stage_log",
        params={"tenant_id": f"eq.{tenant_id}", "thread_id": f"eq.{thread_id}", "order": "created_at.asc"},
    )


def upsert_poll_checkpoint(
    tenant_id: str,
    account_id: str,
    folder: str,
    last_uid: int,
    status: str = "ok",
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "folder": folder,
        "last_uid": last_uid,
        "last_polled_at": datetime.now(timezone.utc).isoformat(),
        "poll_status": status,
        "last_error": error,
    }
    data = _request(
        "POST",
        "poll_checkpoints",
        params={"on_conflict": "tenant_id,account_id,folder"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def get_poll_checkpoint(tenant_id: str, account_id: str, folder: str) -> dict[str, Any] | None:
    return _fetch_optional(
        "poll_checkpoints",
        {"tenant_id": f"eq.{tenant_id}", "account_id": f"eq.{account_id}", "folder": f"eq.{folder}"},
    )


def upsert_enrichment(tenant_id: str, cache_key: str, cache_type: str, source: str, data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    enrichment_data = data.get("enrichment_data", data)
    existing = _fetch_optional(
        "enrichment_cache",
        {
            "tenant_id": f"eq.{tenant_id}",
            "business_domain": f"eq.{cache_key}",
            "cache_type": f"eq.{cache_type}",
        },
    )
    payload = {
        "tenant_id": tenant_id,
        "prospect_id": data.get("prospect_id", existing.get("prospect_id") if existing else None),
        "business_domain": cache_key,
        "enrichment_data": enrichment_data,
        "enrichment_quality": data.get("enrichment_quality", existing.get("enrichment_quality") if existing else None),
        "estimated_monthly_lost_revenue": data.get(
            "estimated_monthly_lost_revenue",
            existing.get("estimated_monthly_lost_revenue") if existing else None,
        ),
        "enriched_at": data.get("enriched_at", data.get("fetched_at", now)),
        "cache_type": cache_type,
        "source": source,
    }
    data_rows = _request(
        "POST",
        "enrichment_cache",
        params={"on_conflict": "tenant_id,business_domain,cache_type"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data_rows[0] if data_rows else payload


def get_enrichment(tenant_id: str, cache_key: str, cache_type: str, ttl_hours: int = 168) -> dict[str, Any] | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=ttl_hours)).isoformat()
    return _fetch_optional(
        "enrichment_cache",
        {
            "tenant_id": f"eq.{tenant_id}",
            "business_domain": f"eq.{cache_key}",
            "cache_type": f"eq.{cache_type}",
            "enriched_at": f"gte.{cutoff}",
            "order": "enriched_at.desc",
        },
    )


def delete_expired_enrichment(tenant_id: str, max_age_hours: int = 336) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    params = {"tenant_id": f"eq.{tenant_id}", "enriched_at": f"lt.{cutoff}"}
    rows = _request("GET", "enrichment_cache", params=params)
    if not rows:
        return 0
    _request("DELETE", "enrichment_cache", params=params)
    return len(rows)


def insert_prospect_email(tenant_id: str, prospect_id: str, email: str, source: str = "outbound") -> dict[str, Any]:
    payload = {
        "tenant_id": tenant_id,
        "prospect_id": prospect_id,
        "email": email,
        "source": source,
    }
    data = _request(
        "POST",
        "prospect_emails",
        params={"on_conflict": "tenant_id,email"},
        json=payload,
        prefer="resolution=ignore-duplicates,return=representation",
    )
    if data:
        return data[0]
    logger.info("dedup_hit", extra={"tenant_id": tenant_id, "email": email})
    existing = _fetch_optional("prospect_emails", {"tenant_id": f"eq.{tenant_id}", "email": f"eq.{email}"})
    if existing is None:
        raise KeyError(f"Duplicate prospect email not found for email={email}")
    return existing


def get_prospect_by_email(tenant_id: str, email: str) -> dict[str, Any] | None:
    return _fetch_optional("prospect_emails", {"tenant_id": f"eq.{tenant_id}", "email": f"eq.{email}"})


def get_emails_for_prospect(tenant_id: str, prospect_id: str) -> list[dict[str, Any]]:
    return _request(
        "GET",
        "prospect_emails",
        params={"tenant_id": f"eq.{tenant_id}", "prospect_id": f"eq.{prospect_id}", "order": "created_at.asc"},
    )


def get_enabled_email_accounts(tenant_id: str) -> list[dict[str, Any]]:
    return _request(
        "GET",
        "email_accounts",
        params={"tenant_id": f"eq.{tenant_id}", "enabled": "eq.true", "order": "created_at.asc"},
    )


def get_email_account(tenant_id: str, account_id: str) -> dict[str, Any] | None:
    return _fetch_optional("email_accounts", {"tenant_id": f"eq.{tenant_id}", "account_id": f"eq.{account_id}"})


def get_tenants_with_email_accounts() -> list[str]:
    rows = _request("GET", "email_accounts", params={"enabled": "eq.true", "select": "tenant_id"})
    tenant_ids = {str(row["tenant_id"]) for row in rows if row.get("tenant_id")}
    return sorted(tenant_ids)


def insert_growth_touchpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_growth_row("touchpoint_log", payload)


def list_growth_touchpoints(*, tenant_id: str, touchpoint_type: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"}
    if touchpoint_type is not None:
        params["touchpoint_type"] = f"eq.{touchpoint_type}"
    return _request("GET", "touchpoint_log", params=params)


def insert_growth_belief_event(payload: dict[str, Any]) -> dict[str, Any]:
    return _insert_growth_row("belief_events", payload)


def list_growth_belief_events(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "belief_events", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def insert_growth_dlq_entry(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "growth_dead_letter_queue", json=payload, prefer="return=representation")
    return data[0] if data else payload


def resolve_growth_dlq_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    payload = dict(updates)
    payload.setdefault("resolved_at", datetime.now(timezone.utc).isoformat())
    data = _request(
        "PATCH",
        "growth_dead_letter_queue",
        params={"id": f"eq.{entry_id}"},
        json=payload,
        prefer="return=representation",
    )
    return data[0]


def list_growth_dlq_entries(*, tenant_id: str, unresolved_only: bool = False) -> list[dict[str, Any]]:
    params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"}
    if unresolved_only:
        params["resolved_at"] = "is.null"
    return _request("GET", "growth_dead_letter_queue", params=params)


def upsert_growth_experiment_history(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "experiment_history",
        params={"on_conflict": "experiment_id"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def get_growth_experiment_history(experiment_id: str) -> dict[str, Any]:
    return _fetch_first("experiment_history", {"experiment_id": f"eq.{experiment_id}"})


def list_growth_experiment_history(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "experiment_history", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_segment_performance(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "segment_performance", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_cost_per_acquisition(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "cost_per_acquisition", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_insights(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "insight_log", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_founder_overrides(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "founder_overrides", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_loss_records(*, tenant_id: str) -> list[dict[str, Any]]:
    return _request("GET", "loss_records", params={"tenant_id": f"eq.{tenant_id}", "order": "created_at.asc"})


def list_growth_wedges(*, tenant_id: str) -> list[str]:
    rows = _request("GET", "experiment_history", params={"tenant_id": f"eq.{tenant_id}", "select": "wedge_id"})
    wedges = {str(row["wedge_id"]) for row in rows if row.get("wedge_id")}
    return sorted(wedges)


def upsert_growth_wedge_fitness_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    data = _request(
        "POST",
        "wedge_fitness_snapshots",
        params={"on_conflict": "tenant_id,wedge,snapshot_week"},
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0] if data else payload


def get_latest_growth_wedge_fitness_snapshot(*, tenant_id: str, wedge: str) -> dict[str, Any] | None:
    data = _request(
        "GET",
        "wedge_fitness_snapshots",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "wedge": f"eq.{wedge}",
            "order": "snapshot_week.desc",
            "limit": "1",
        },
    )
    if not data:
        return None
    return data[0]


# --- Voice CRUD ---


def insert_call_record(
    tenant_id: str,
    call_id: str,
    retell_call_id: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any] | None:
    payload = {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "retell_call_id": retell_call_id,
        "phone_number": raw_payload.get("from_number"),
        "transcript": raw_payload.get("transcript"),
        "raw_retell_payload": raw_payload,
        "extraction_status": "pending",
    }
    try:
        data = _request(
            "POST",
            "call_records",
            params={"on_conflict": "tenant_id,call_id"},
            json=payload,
            prefer="resolution=ignore-duplicates,return=representation",
        )
    except Exception as exc:
        if _is_duplicate_status_error(exc):
            return None
        raise
    if not data:
        return None
    return data[0]


def update_call_record_extraction(
    tenant_id: str,
    call_id: str,
    extracted_fields: dict[str, Any],
    *,
    end_call_reason: str | None = None,
    booking_id: str | None = None,
    callback_scheduled: bool = False,
    call_duration_seconds: int | None = None,
    call_recording_url: str | None = None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "extracted_fields": extracted_fields,
        "extraction_status": extracted_fields.get("extraction_status", "complete"),
        "quality_score": extracted_fields.get("quality_score"),
        "tags": extracted_fields.get("tags"),
        "route": extracted_fields.get("route"),
        "urgency_tier": extracted_fields.get("urgency_tier"),
        "caller_type": extracted_fields.get("caller_type"),
        "primary_intent": extracted_fields.get("primary_intent"),
        "revenue_tier": extracted_fields.get("revenue_tier"),
        "end_call_reason": end_call_reason,
        "booking_id": booking_id,
        "callback_scheduled": callback_scheduled,
        "call_duration_seconds": call_duration_seconds,
        "call_recording_url": call_recording_url,
    }
    data = _request(
        "PATCH",
        "call_records",
        params={"tenant_id": f"eq.{tenant_id}", "call_id": f"eq.{call_id}"},
        json=patch,
        prefer="return=representation",
    )
    if not data:
        raise KeyError(f"Unknown call record: tenant_id={tenant_id}, call_id={call_id}")
    return data[0]


def update_raw_payload(
    tenant_id: str,
    call_id: str,
    raw_payload: dict[str, Any],
) -> None:
    """Persist enriched raw_retell_payload after Retell API fetch."""
    _request(
        "PATCH",
        "call_records",
        params={"tenant_id": f"eq.{tenant_id}", "call_id": f"eq.{call_id}"},
        json={"raw_retell_payload": raw_payload},
    )


def get_call_record(tenant_id: str, call_id: str) -> dict[str, Any] | None:
    """Get a single call record by tenant + call_id."""
    data = _request(
        "GET",
        "call_records",
        params={"tenant_id": f"eq.{tenant_id}", "call_id": f"eq.{call_id}", "limit": "1"},
    )
    return data[0] if data else None


def get_caller_history(tenant_id: str, phone: str) -> dict[str, Any]:
    jobs = _request(
        "GET",
        "jobs",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "customer_phone": f"eq.{phone}",
            "order": "created_at.desc",
            "limit": "10",
        },
    ) or []
    calls = _request(
        "GET",
        "call_records",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "phone_number": f"eq.{phone}",
            "order": "created_at.desc",
            "limit": "5",
        },
    ) or []
    bookings = _request(
        "GET",
        "bookings",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "customer_phone": f"eq.{phone}",
            "order": "created_at.desc",
            "limit": "5",
        },
    ) or []
    return {"jobs": jobs, "calls": calls, "bookings": bookings}


def query_jobs_by_phone(phone: str) -> list[dict[str, Any]]:
    return _request("GET", "jobs", params={"customer_phone": f"eq.{phone}", "order": "created_at.desc", "limit": "10"}) or []


def query_calls_by_phone(phone: str) -> list[dict[str, Any]]:
    return _request("GET", "call_records", params={"phone_number": f"eq.{phone}", "order": "created_at.desc", "limit": "5"}) or []


def query_bookings_by_phone(phone: str) -> list[dict[str, Any]]:
    return _request("GET", "bookings", params={"customer_phone": f"eq.{phone}", "order": "created_at.desc", "limit": "5"}) or []


def get_voice_api_keys() -> list[dict[str, Any]]:
    return _request(
        "GET",
        "voice_api_keys",
        params={"revoked_at": "is.null"},
    ) or []

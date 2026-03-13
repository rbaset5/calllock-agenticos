from __future__ import annotations

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
from harness.incident_sync_payload import build_incident_sync_payload
from harness.jobs.state_machine import validate_transition as validate_job_transition
from harness.resilience.retry import retry_call


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


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


def _rpc(function_name: str, payload: dict[str, Any]) -> Any:
    return _request("POST", f"rpc/{function_name}", json=payload, prefer="return=representation")


def _fetch_first(table: str, params: dict[str, str]) -> dict[str, Any]:
    data = _request("GET", table, params={**params, "limit": "1"})
    if not data:
        raise KeyError(f"No row found in {table} for params {params}")
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

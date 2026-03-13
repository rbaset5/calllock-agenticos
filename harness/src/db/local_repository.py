from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from harness.artifacts.access import assert_tenant_access
from harness.artifacts.lifecycle import validate_transition
from harness.alerts.lifecycle import validate_alert_transition
from harness.artifacts.storage import normalize_artifact, write_run_artifact
from harness.incident_runbooks import apply_runbook_step_assignment, apply_runbook_step_update, get_runbook_step
from harness.jobs.state_machine import validate_transition as validate_job_transition

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_SEED_PATH = REPO_ROOT / "supabase" / "local_seed.json"
ARTIFACTS_DIR = REPO_ROOT / ".context" / "artifacts"


_RUNTIME_STATE: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def load_local_seed() -> dict[str, Any]:
    return json.loads(LOCAL_SEED_PATH.read_text())


def _initial_state() -> dict[str, Any]:
    seed = deepcopy(load_local_seed())
    seed.setdefault("jobs", [])
    seed.setdefault("artifacts", [])
    seed.setdefault("kill_switches", [])
    seed.setdefault("alerts", [])
    seed.setdefault("experiments", [])
    seed.setdefault("locks", [])
    seed.setdefault("customer_content", [])
    seed.setdefault("eval_runs", [])
    seed.setdefault("audit_logs", [])
    seed.setdefault("approval_requests", [])
    seed.setdefault("scheduler_backlog", [])
    seed.setdefault("incidents", [])
    return seed


def _state() -> dict[str, Any]:
    global _RUNTIME_STATE
    if _RUNTIME_STATE is None:
        _RUNTIME_STATE = _initial_state()
    return _RUNTIME_STATE


def reset_local_state() -> None:
    global _RUNTIME_STATE
    _RUNTIME_STATE = _initial_state()


def _matches(identifier: str, record: dict[str, Any]) -> bool:
    return identifier in {record.get("id"), record.get("slug"), record.get("tenant_id")}


def get_tenant(identifier: str) -> dict[str, Any]:
    for tenant in _state()["tenants"]:
        if _matches(identifier, tenant):
            return tenant
    raise KeyError(f"Unknown tenant: {identifier}")


def list_tenants() -> list[dict[str, Any]]:
    return list(_state()["tenants"])


def get_tenant_config(identifier: str) -> dict[str, Any]:
    for config in _state()["tenant_configs"]:
        if _matches(identifier, config):
            return config
    tenant = get_tenant(identifier)
    return {
        "tenant_id": tenant["id"],
        "industry_pack_id": tenant["industry_pack_id"],
        "allowed_tools": [],
        "tone_profile": {"formality": "direct", "banned_words": []},
        "feature_flags": {"harness_enabled": True},
        "timezone": "UTC",
        "retention_local_hour": 3,
        "tenant_eval_local_hour": 4,
        "max_schedule_lag_hours": 24,
        "max_active_jobs": 5,
        "alert_thresholds": {},
        "alert_channels": ["dashboard"],
        "alert_escalation_policy": {},
        "alert_suppression_window_minutes": 60,
        "alert_recovery_cooldown_minutes": 15,
        "incident_notification_channels": ["dashboard"],
        "incident_assignees": {},
        "incident_reminder_minutes": 60,
        "incident_default_assignee": None,
        "incident_reassign_after_reminders": 2,
        "incident_oncall_rotation": [],
        "incident_rotation_interval_hours": 24,
        "incident_skill_requirements": {},
        "incident_classification_rules": [],
        "incident_runbooks": {},
    }


def get_compliance_rules(identifier: str) -> list[dict[str, Any]]:
    tenant = get_tenant(identifier)
    rules = []
    for rule in _state()["compliance_rules"]:
        if rule.get("tenant_id") in (None, tenant["id"]):
            rules.append(rule)
    return rules


def persist_run_record(record: dict[str, Any]) -> dict[str, Any]:
    job = create_job(
        {
            "tenant_id": record["tenant_id"],
            "origin_worker_id": record["worker_id"],
            "origin_run_id": record["run_id"],
            "job_type": "harness_run",
            "status": "completed" if record.get("status") == "verified" else "failed",
            "idempotency_key": record["run_id"],
            "payload": {"policy_verdict": record.get("policy_verdict")},
            "result": record,
            "created_by": record["worker_id"],
        }
    )
    stored = deepcopy(record)
    stored["job"] = job
    return stored


def create_artifact(record: dict[str, Any]) -> dict[str, Any]:
    artifact = normalize_artifact(record)
    artifact["artifact_path"] = write_run_artifact(artifact)
    _state()["artifacts"].append(artifact)
    return artifact


def update_artifact_lifecycle(artifact_id: str, target_state: str, *, tenant_id: str) -> dict[str, Any]:
    for artifact in _state()["artifacts"]:
        if artifact["id"] == artifact_id:
            assert_tenant_access(tenant_id, artifact)
            validate_transition(artifact["lifecycle_state"], target_state)
            artifact["lifecycle_state"] = target_state
            return artifact
    raise KeyError(f"Unknown artifact: {artifact_id}")


def list_artifacts(tenant_id: str) -> list[dict[str, Any]]:
    return [artifact for artifact in _state()["artifacts"] if artifact["tenant_id"] == tenant_id]


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    for job in _state()["jobs"]:
        if job["idempotency_key"] == payload["idempotency_key"]:
            return job
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload["tenant_id"],
        "origin_worker_id": payload["origin_worker_id"],
        "origin_run_id": payload["origin_run_id"],
        "job_type": payload["job_type"],
        "status": payload.get("status", "queued"),
        "supersedes_job_id": payload.get("supersedes_job_id"),
        "source_call_id": payload.get("source_call_id"),
        "idempotency_key": payload["idempotency_key"],
        "payload": payload.get("payload", {}),
        "result": payload.get("result", {}),
        "created_by": payload.get("created_by", "harness"),
        "created_at": payload.get("created_at", now),
        "updated_at": payload.get("updated_at", now),
    }
    _state()["jobs"].append(job)
    return job


def update_job_status(job_id: str, status: str, *, result: dict[str, Any] | None = None) -> dict[str, Any]:
    for job in _state()["jobs"]:
        if job["id"] == job_id:
            validate_job_transition(job["status"], status)
            job["status"] = status
            if result is not None:
                job["result"] = result
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            return job
    raise KeyError(f"Unknown job: {job_id}")


def get_job(job_id: str) -> dict[str, Any]:
    for job in _state()["jobs"]:
        if job["id"] == job_id:
            return job
    raise KeyError(f"Unknown job: {job_id}")


def list_jobs(*, tenant_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    jobs = list(_state()["jobs"])
    if tenant_id is not None:
        jobs = [job for job in jobs if job["tenant_id"] == tenant_id]
    if run_id is not None:
        jobs = [job for job in jobs if job["origin_run_id"] == run_id]
    return jobs


def count_active_jobs(tenant_id: str) -> int:
    return sum(1 for job in _state()["jobs"] if job["tenant_id"] == tenant_id and job["status"] in {"queued", "running"})


def create_tenant(payload: dict[str, Any]) -> dict[str, Any]:
    tenant = {
        "id": payload.get("id", str(uuid4())),
        "slug": payload["slug"],
        "name": payload["name"],
        "industry_pack_id": payload.get("industry_pack_id", "hvac"),
        "status": payload.get("status", "active"),
    }
    _state()["tenants"].append(tenant)
    return tenant


def create_tenant_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = {
        "tenant_id": payload["tenant_id"],
        "slug": payload.get("slug"),
        "tone_profile": payload.get("tone_profile", {"formality": "direct", "banned_words": []}),
        "allowed_tools": payload.get("allowed_tools", []),
        "industry_pack_id": payload.get("industry_pack_id", "hvac"),
        "feature_flags": payload.get("feature_flags", {"harness_enabled": True}),
        "timezone": payload.get("timezone", "UTC"),
        "retention_local_hour": payload.get("retention_local_hour", 3),
        "tenant_eval_local_hour": payload.get("tenant_eval_local_hour", 4),
        "max_schedule_lag_hours": payload.get("max_schedule_lag_hours", 24),
        "max_active_jobs": payload.get("max_active_jobs", 5),
        "alert_thresholds": payload.get("alert_thresholds", {}),
        "alert_channels": payload.get("alert_channels", ["dashboard"]),
        "alert_webhook_url": payload.get("alert_webhook_url"),
        "alert_escalation_policy": payload.get("alert_escalation_policy", {}),
        "alert_suppression_window_minutes": payload.get("alert_suppression_window_minutes", 60),
        "alert_recovery_cooldown_minutes": payload.get("alert_recovery_cooldown_minutes", 15),
        "incident_notification_channels": payload.get("incident_notification_channels", ["dashboard"]),
        "incident_assignees": payload.get("incident_assignees", {}),
        "incident_reminder_minutes": payload.get("incident_reminder_minutes", 60),
        "incident_default_assignee": payload.get("incident_default_assignee"),
        "incident_reassign_after_reminders": payload.get("incident_reassign_after_reminders", 2),
        "incident_oncall_rotation": payload.get("incident_oncall_rotation", []),
        "incident_rotation_interval_hours": payload.get("incident_rotation_interval_hours", 24),
        "incident_skill_requirements": payload.get("incident_skill_requirements", {}),
        "incident_classification_rules": payload.get("incident_classification_rules", []),
        "incident_runbooks": payload.get("incident_runbooks", {}),
        "voice_agent": payload.get("voice_agent", {}),
        "automations": payload.get("automations", []),
    }
    _state()["tenant_configs"].append(config)
    return config


def update_tenant_config(tenant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    config = get_tenant_config(tenant_id)
    config.update(updates)
    return config


def delete_tenant(identifier: str) -> None:
    tenant = get_tenant(identifier)
    tenant_id = tenant["id"]
    for key in ("tenants", "tenant_configs", "jobs", "artifacts", "kill_switches", "alerts", "customer_content", "scheduler_backlog", "incidents"):
        _state()[key] = [record for record in _state()[key] if record.get("tenant_id") != tenant_id and record.get("id") != tenant_id]


def save_kill_switch(payload: dict[str, Any]) -> dict[str, Any]:
    for record in _state()["kill_switches"]:
        if record["scope"] == payload["scope"] and record.get("scope_id") == payload.get("scope_id"):
            record.update(payload)
            return record
    record = {
        "id": payload.get("id", str(uuid4())),
        "scope": payload["scope"],
        "scope_id": payload.get("scope_id"),
        "active": payload.get("active", True),
        "reason": payload["reason"],
        "created_by": payload.get("created_by", "operator"),
        "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    _state()["kill_switches"].append(record)
    return record


def list_kill_switches(*, active_only: bool = False) -> list[dict[str, Any]]:
    records = list(_state()["kill_switches"])
    if active_only:
        records = [record for record in records if record.get("active")]
    return records


def create_alert(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id"),
        "alert_type": payload["alert_type"],
        "severity": payload["severity"],
        "status": payload.get("status", "open"),
        "message": payload["message"],
        "metrics": payload.get("metrics", {}),
        "acknowledged_at": payload.get("acknowledged_at"),
        "acknowledged_by": payload.get("acknowledged_by"),
        "escalated_at": payload.get("escalated_at"),
        "escalated_by": payload.get("escalated_by"),
        "resolved_at": payload.get("resolved_at"),
        "resolved_by": payload.get("resolved_by"),
        "resolution_notes": payload.get("resolution_notes", ""),
        "occurrence_count": payload.get("occurrence_count", 1),
        "last_observed_at": payload.get("last_observed_at", payload.get("created_at", datetime.now(timezone.utc).isoformat())),
        "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    _state()["alerts"].append(record)
    return record


def create_alert_and_sync_incident(payload: dict[str, Any]) -> dict[str, Any]:
    from harness.incidents import record_incident_from_alert

    created = create_alert(payload)
    record_incident_from_alert(created)
    return created


def list_alerts(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    alerts = list(_state()["alerts"])
    if tenant_id is not None:
        alerts = [alert for alert in alerts if alert.get("tenant_id") in (None, tenant_id)]
    if status is not None:
        alerts = [alert for alert in alerts if alert.get("status") == status]
    return alerts


def update_alert(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for alert in _state()["alerts"]:
        if alert["id"] == alert_id:
            if "status" in updates:
                validate_alert_transition(alert.get("status", "open"), updates["status"])
            alert.update(updates)
            return alert
    raise KeyError(f"Unknown alert: {alert_id}")


def update_alert_and_sync_incident(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    from harness.incidents import record_incident_from_alert

    updated = update_alert(alert_id, updates)
    record_incident_from_alert(updated)
    return updated


def upsert_incident(payload: dict[str, Any]) -> dict[str, Any]:
    for incident in _state()["incidents"]:
        if incident["incident_key"] == payload["incident_key"]:
            next_revision = int(incident.get("incident_revision", 1)) + 1
            incident.update({**payload, "incident_revision": payload.get("incident_revision", next_revision)})
            return incident
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id"),
        "incident_key": payload["incident_key"],
        "alert_type": payload["alert_type"],
        "severity": payload.get("severity", "medium"),
        "incident_domain": payload.get("incident_domain", "general"),
        "incident_category": payload.get("incident_category", payload["alert_type"]),
        "remediation_category": payload.get("remediation_category", "manual_review"),
        "incident_urgency": payload.get("incident_urgency", payload.get("severity", "medium")),
        "runbook_id": payload.get("runbook_id"),
        "runbook_title": payload.get("runbook_title"),
        "runbook_steps": payload.get("runbook_steps", []),
        "runbook_progress": payload.get("runbook_progress", []),
        "runbook_progress_summary": payload.get(
            "runbook_progress_summary",
            {"total_steps": len(payload.get("runbook_steps", [])), "completed_steps": 0, "pending_steps": len(payload.get("runbook_steps", []))},
        ),
        "runbook_execution_plan": payload.get(
            "runbook_execution_plan",
            {"next_runnable_steps": [], "blocked_steps": [], "completed_steps": [], "parallel_groups": {}},
        ),
        "completion_policy": payload.get("completion_policy", {"required_workflow_statuses": []}),
        "approval_policy": payload.get("approval_policy", {"required_workflow_statuses": []}),
        "status": payload.get("status", "open"),
        "workflow_status": payload.get("workflow_status", "new"),
        "assigned_to": payload.get("assigned_to"),
        "operator_notes": payload.get("operator_notes", ""),
        "last_reviewed_at": payload.get("last_reviewed_at"),
        "last_reviewed_by": payload.get("last_reviewed_by"),
        "last_reminded_at": payload.get("last_reminded_at"),
        "reminder_count": payload.get("reminder_count", 0),
        "assignment_history": payload.get("assignment_history", []),
        "last_assignment_reason": payload.get("last_assignment_reason"),
        "started_at": payload.get("started_at", datetime.now(timezone.utc).isoformat()),
        "last_seen_at": payload.get("last_seen_at", datetime.now(timezone.utc).isoformat()),
        "resolved_at": payload.get("resolved_at"),
        "current_episode": payload.get("current_episode", 1),
        "episode_count": payload.get("episode_count", 1),
        "episode_history": payload.get("episode_history", []),
        "current_alert_id": payload.get("current_alert_id"),
        "last_alert_status": payload.get("last_alert_status", "open"),
        "alert_ids": payload.get("alert_ids", []),
        "occurrence_count": payload.get("occurrence_count", 1),
        "incident_revision": payload.get("incident_revision", 1),
    }
    _state()["incidents"].append(record)
    return record


def sync_incident_from_alert(payload: dict[str, Any]) -> dict[str, Any]:
    existing = next(
        (incident for incident in _state()["incidents"] if incident["incident_key"] == payload["incident_key"]),
        None,
    )
    status = "resolved" if payload.get("alert_status") == "resolved" else "open"
    previous_status = (existing or {}).get("status")
    previous_episode = int((existing or {}).get("episode_count", 0))
    episode_count = previous_episode or 1
    episode_history = list((existing or {}).get("episode_history", []))
    started_at = (existing or {}).get("started_at") or payload.get("alert_created_at")
    reset_runbook_progress = False
    if previous_status == "resolved" and status == "open":
        if existing:
            prior_episode_number = int(existing.get("current_episode", previous_episode or 1))
            episode_history.append(
                {
                    "episode": prior_episode_number,
                    "started_at": existing.get("started_at"),
                    "resolved_at": existing.get("resolved_at"),
                    "last_seen_at": existing.get("last_seen_at"),
                    "occurrence_count": existing.get("occurrence_count", 1),
                }
            )
        episode_count = (previous_episode or 1) + 1
        started_at = payload.get("alert_created_at") or payload.get("alert_last_observed_at")
        reset_runbook_progress = True

    runbook_changed = bool(existing) and (
        existing.get("runbook_id") != payload.get("runbook_id")
        or existing.get("runbook_steps", []) != payload.get("runbook_steps", [])
        or existing.get("completion_policy", {"required_workflow_statuses": []}) != payload.get("completion_policy", {"required_workflow_statuses": []})
        or existing.get("approval_policy", {"required_workflow_statuses": []}) != payload.get("approval_policy", {"required_workflow_statuses": []})
    )

    alert_ids = list((existing or {}).get("alert_ids", []))
    alert_id = payload.get("alert_id")
    if alert_id and alert_id not in alert_ids:
        alert_ids.append(alert_id)

    merged_payload = {
        "incident_key": payload["incident_key"],
        "tenant_id": payload.get("tenant_id"),
        "alert_type": payload["alert_type"],
        "severity": payload.get("severity", "medium"),
        "incident_domain": payload.get("incident_domain", "general"),
        "incident_category": payload.get("incident_category", payload["alert_type"]),
        "remediation_category": payload.get("remediation_category", "manual_review"),
        "incident_urgency": payload.get("incident_urgency", payload.get("severity", "medium")),
        "runbook_id": payload.get("runbook_id"),
        "runbook_title": payload.get("runbook_title"),
        "runbook_steps": payload.get("runbook_steps", []),
        "runbook_progress": payload.get("initial_runbook_progress", []),
        "runbook_progress_summary": payload.get("initial_runbook_progress_summary", {"total_steps": 0, "completed_steps": 0, "pending_steps": 0}),
        "runbook_execution_plan": payload.get("initial_runbook_execution_plan", {"next_runnable_steps": [], "blocked_steps": [], "completed_steps": [], "parallel_groups": {}}),
        "completion_policy": payload.get("completion_policy", {"required_workflow_statuses": []}),
        "approval_policy": payload.get("approval_policy", {"required_workflow_statuses": []}),
        "status": status,
        "workflow_status": (existing or {}).get("workflow_status", "new"),
        "assigned_to": (existing or {}).get("assigned_to"),
        "operator_notes": (existing or {}).get("operator_notes", ""),
        "last_reviewed_at": (existing or {}).get("last_reviewed_at"),
        "last_reviewed_by": (existing or {}).get("last_reviewed_by"),
        "last_reminded_at": (existing or {}).get("last_reminded_at"),
        "reminder_count": (existing or {}).get("reminder_count", 0),
        "assignment_history": (existing or {}).get("assignment_history", []),
        "last_assignment_reason": (existing or {}).get("last_assignment_reason"),
        "started_at": started_at,
        "last_seen_at": payload.get("alert_last_observed_at") or payload.get("alert_resolved_at") or payload.get("alert_created_at"),
        "resolved_at": payload.get("alert_resolved_at") if status == "resolved" else None,
        "current_episode": episode_count,
        "episode_count": episode_count,
        "episode_history": episode_history,
        "current_alert_id": alert_id,
        "last_alert_status": payload.get("alert_status", "open"),
        "alert_ids": alert_ids,
        "occurrence_count": max(
            int(payload.get("alert_occurrence_count", 1)),
            int((existing or {}).get("occurrence_count", 0)),
        ),
    }
    if existing and not reset_runbook_progress and not runbook_changed:
        merged_payload["runbook_progress"] = existing.get("runbook_progress", [])
        merged_payload["runbook_progress_summary"] = existing.get("runbook_progress_summary", merged_payload["runbook_progress_summary"])
        merged_payload["runbook_execution_plan"] = existing.get("runbook_execution_plan", merged_payload["runbook_execution_plan"])
    return upsert_incident(merged_payload)


def list_incidents(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    incidents = list(_state()["incidents"])
    if tenant_id is not None:
        incidents = [incident for incident in incidents if incident.get("tenant_id") in (None, tenant_id)]
    if status is not None:
        incidents = [incident for incident in incidents if incident.get("status") == status]
    return incidents


def _get_incident(incident_id: str) -> dict[str, Any]:
    for incident in _state()["incidents"]:
        if incident["id"] == incident_id:
            return incident
    raise KeyError(f"Unknown incident: {incident_id}")


def update_incident(incident_id: str, updates: dict[str, Any], *, expected_revision: int | None = None) -> dict[str, Any]:
    incident = _get_incident(incident_id)
    current_revision = int(incident.get("incident_revision", 1))
    if expected_revision is not None and current_revision != expected_revision:
        raise ValueError(f"incident revision conflict: expected {expected_revision}, found {current_revision}")
    incident.update({**updates, "incident_revision": current_revision + 1})
    return incident


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
    current = _get_incident(incident_id)
    expected_revision = expected_revision or int(current.get("incident_revision", 1))
    expected_step_revision = expected_step_revision or int((get_runbook_step(current, step_index) or {}).get("step_revision", 1))
    patch = apply_runbook_step_update(
        current,
        step_index=step_index,
        status=status,
        actor_id=actor_id,
        note=note,
    )
    try:
        return update_incident(incident_id, patch, expected_revision=expected_revision)
    except ValueError:
        latest = _get_incident(incident_id)
        latest_step = get_runbook_step(latest, step_index) or {}
        latest_step_revision = int(latest_step.get("step_revision", 1))
        if latest_step_revision != expected_step_revision:
            raise ValueError(f"runbook step revision conflict: expected {expected_step_revision}, found {latest_step_revision}")
        retry_patch = apply_runbook_step_update(
            latest,
            step_index=step_index,
            status=status,
            actor_id=actor_id,
            note=note,
        )
        return update_incident(
            incident_id,
            retry_patch,
            expected_revision=int(latest.get("incident_revision", 1)),
        )


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
    current = _get_incident(incident_id)
    expected_revision = expected_revision or int(current.get("incident_revision", 1))
    expected_step_revision = expected_step_revision or int((get_runbook_step(current, step_index) or {}).get("step_revision", 1))
    patch = apply_runbook_step_assignment(
        current,
        step_index=step_index,
        actor_id=actor_id,
        action=action,
        assigned_to=assigned_to,
        claim_ttl_seconds=claim_ttl_seconds,
        now_iso=now_iso,
    )
    try:
        return update_incident(incident_id, patch, expected_revision=expected_revision)
    except ValueError:
        latest = _get_incident(incident_id)
        latest_step = get_runbook_step(latest, step_index) or {}
        latest_step_revision = int(latest_step.get("step_revision", 1))
        if latest_step_revision != expected_step_revision:
            raise ValueError(f"runbook step revision conflict: expected {expected_step_revision}, found {latest_step_revision}")
        retry_patch = apply_runbook_step_assignment(
            latest,
            step_index=step_index,
            actor_id=actor_id,
            action=action,
            assigned_to=assigned_to,
            claim_ttl_seconds=claim_ttl_seconds,
            now_iso=now_iso,
        )
        return update_incident(
            incident_id,
            retry_patch,
            expected_revision=int(latest.get("incident_revision", 1)),
        )


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
    current = _get_incident(incident_id)
    timestamp = now_iso or datetime.now(timezone.utc).isoformat()
    updates = {
        "workflow_status": workflow_status,
        "assigned_to": assigned_to,
        "operator_notes": operator_notes,
        "last_reviewed_at": timestamp,
        "last_reviewed_by": actor_id,
        "last_assignment_reason": last_assignment_reason,
        "assignment_history": list(current.get("assignment_history", [])),
    }
    if assignment_history_entry:
        updates["assignment_history"].append(assignment_history_entry)
    return update_incident(
        incident_id,
        updates,
        expected_revision=expected_revision,
    )


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
    current = _get_incident(incident_id)
    updates = {
        "last_reminded_at": last_reminded_at,
        "reminder_count": reminder_count,
    }
    if assigned_to is not None:
        updates["assigned_to"] = assigned_to
    if last_assignment_reason is not None:
        updates["last_assignment_reason"] = last_assignment_reason
    history = list(current.get("assignment_history", []))
    if assignment_history_entry:
        history.append(assignment_history_entry)
        updates["assignment_history"] = history
    return update_incident(
        incident_id,
        updates,
        expected_revision=expected_revision,
    )


def save_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "id": payload.get("id", str(uuid4())),
        **payload,
        "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    _state()["experiments"].append(record)
    return record


def list_experiments() -> list[dict[str, Any]]:
    return list(_state()["experiments"])


def acquire_lock(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).timestamp()
    surface = payload["mutation_surface"]
    for record in _state()["locks"]:
        expires_at = record["expires_at"]
        if record["mutation_surface"] == surface and expires_at > now:
            raise ValueError(f"Mutation surface already locked: {surface}")
    record = {
        "id": payload.get("id", str(uuid4())),
        "mutation_surface": surface,
        "expires_at": now + payload.get("ttl_seconds", 900),
        "heartbeat_at": now,
    }
    _state()["locks"] = [record for record in _state()["locks"] if record["mutation_surface"] != surface]
    _state()["locks"].append(record)
    return record


def release_lock(mutation_surface: str) -> None:
    _state()["locks"] = [record for record in _state()["locks"] if record["mutation_surface"] != mutation_surface]


def heartbeat_lock(mutation_surface: str, ttl_seconds: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc).timestamp()
    for record in _state()["locks"]:
        if record["mutation_surface"] == mutation_surface:
            record["heartbeat_at"] = now
            record["expires_at"] = now + ttl_seconds
            return record
    raise KeyError(f"Unknown lock: {mutation_surface}")


def save_customer_content(payload: dict[str, Any]) -> dict[str, Any]:
    record = {"id": str(uuid4()), **payload, "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat())}
    _state()["customer_content"].append(record)
    return record


def list_customer_content(tenant_id: str) -> list[dict[str, Any]]:
    return [record for record in _state()["customer_content"] if record["tenant_id"] == tenant_id]


def delete_customer_content_before(tenant_id: str, cutoff_iso: str, *, dry_run: bool = False) -> int:
    kept = []
    deleted = 0
    for record in _state()["customer_content"]:
        if record["tenant_id"] == tenant_id and record["created_at"] < cutoff_iso:
            deleted += 1
        else:
            kept.append(record)
    if not dry_run:
        _state()["customer_content"] = kept
    return deleted


def save_eval_run(payload: dict[str, Any]) -> dict[str, Any]:
    _state()["eval_runs"].append(payload)
    return payload


def list_eval_runs(*, tenant_id: str | None = None) -> list[dict[str, Any]]:
    runs = list(_state()["eval_runs"])
    if tenant_id is not None:
        runs = [run for run in runs if run.get("tenant_id") == tenant_id]
    return runs


def create_audit_log(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "tenant_id": payload.get("tenant_id"),
        "action_type": payload["action_type"],
        "actor_id": payload["actor_id"],
        "reason": payload["reason"],
        "target_type": payload.get("target_type"),
        "target_id": payload.get("target_id"),
        "payload": payload.get("payload", {}),
        "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    _state()["audit_logs"].append(record)
    return record


def list_audit_logs(*, tenant_id: str | None = None, action_type: str | None = None) -> list[dict[str, Any]]:
    logs = list(_state()["audit_logs"])
    if tenant_id is not None:
        logs = [log for log in logs if log.get("tenant_id") == tenant_id]
    if action_type is not None:
        logs = [log for log in logs if log["action_type"] == action_type]
    return logs


def delete_audit_logs_before(cutoff_iso: str, *, tenant_id: str | None = None, dry_run: bool = False) -> int:
    kept = []
    deleted = 0
    for log in _state()["audit_logs"]:
        matches_tenant = tenant_id is None or log.get("tenant_id") == tenant_id
        if matches_tenant and log["created_at"] < cutoff_iso:
            deleted += 1
        else:
            kept.append(log)
    if not dry_run:
        _state()["audit_logs"] = kept
    return deleted


def create_approval_request(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "tenant_id": payload.get("tenant_id"),
        "run_id": payload.get("run_id"),
        "worker_id": payload.get("worker_id"),
        "status": payload.get("status", "pending"),
        "reason": payload["reason"],
        "requested_by": payload.get("requested_by", "harness"),
        "request_type": payload["request_type"],
        "payload": payload.get("payload", {}),
        "resolved_by": payload.get("resolved_by"),
        "resolution_notes": payload.get("resolution_notes"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _state()["approval_requests"].append(record)
    return record


def update_approval_request(approval_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for request in _state()["approval_requests"]:
        if request["id"] == approval_id:
            request.update(updates)
            return request
    raise KeyError(f"Unknown approval request: {approval_id}")


def list_approval_requests(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    requests = list(_state()["approval_requests"])
    if tenant_id is not None:
        requests = [request for request in requests if request.get("tenant_id") == tenant_id]
    if status is not None:
        requests = [request for request in requests if request["status"] == status]
    return requests


def upsert_scheduler_backlog_entry(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    for entry in _state()["scheduler_backlog"]:
        if (
            entry["tenant_id"] == payload["tenant_id"]
            and entry["job_type"] == payload["job_type"]
            and entry["scheduled_for"] == payload["scheduled_for"]
        ):
            entry.update(payload)
            entry["updated_at"] = payload.get("updated_at", now)
            return entry
    entry = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload["tenant_id"],
        "job_type": payload["job_type"],
        "scheduled_for": payload["scheduled_for"],
        "status": payload["status"],
        "scheduled_timezone": payload["scheduled_timezone"],
        "scheduled_hour": payload["scheduled_hour"],
        "scheduled_minute": payload["scheduled_minute"],
        "payload": payload.get("payload", {}),
        "created_at": payload.get("created_at", now),
        "updated_at": payload.get("updated_at", now),
        "last_seen_at": payload.get("last_seen_at", now),
        "completed_at": payload.get("completed_at"),
        "claimed_by": payload.get("claimed_by"),
        "claimed_at": payload.get("claimed_at"),
        "claim_expires_at": payload.get("claim_expires_at"),
    }
    _state()["scheduler_backlog"].append(entry)
    return entry


def list_scheduler_backlog(
    *,
    tenant_id: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    entries = list(_state()["scheduler_backlog"])
    if tenant_id is not None:
        entries = [entry for entry in entries if entry["tenant_id"] == tenant_id]
    if job_type is not None:
        entries = [entry for entry in entries if entry["job_type"] == job_type]
    if status is not None:
        entries = [entry for entry in entries if entry["status"] == status]
    return sorted(entries, key=lambda entry: (entry["scheduled_for"], entry["tenant_id"], entry["job_type"]))


def update_scheduler_backlog_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for entry in _state()["scheduler_backlog"]:
        if entry["id"] == entry_id:
            entry.update(updates)
            entry["updated_at"] = updates.get("updated_at", datetime.now(timezone.utc).isoformat())
            return entry
    raise KeyError(f"Unknown scheduler backlog entry: {entry_id}")


def claim_scheduler_backlog_entries(
    *,
    job_type: str,
    claimed_before_iso: str,
    max_entries: int,
    claimer_id: str,
    claim_ttl_seconds: int,
) -> list[dict[str, Any]]:
    claimed_before = datetime.fromisoformat(claimed_before_iso.replace("Z", "+00:00"))
    candidates = []
    for entry in _state()["scheduler_backlog"]:
        if entry["job_type"] != job_type or entry["status"] != "pending":
            continue
        scheduled_for = datetime.fromisoformat(entry["scheduled_for"].replace("Z", "+00:00"))
        if scheduled_for > claimed_before:
            continue
        payload = entry.get("payload", {})
        candidates.append(
            (
                -int(payload.get("lateness_minutes", 0)),
                payload.get("active_job_count", 0) / max(payload.get("max_active_jobs", 1), 1),
                entry["scheduled_minute"],
                payload.get("tenant_slug") or entry["tenant_id"],
                entry,
            )
        )
    candidates.sort(key=lambda item: item[:-1])
    claimed = []
    claim_expires_at = (claimed_before + timedelta(seconds=claim_ttl_seconds)).isoformat()
    for _, _, _, _, entry in candidates[:max_entries]:
        entry["status"] = "claimed"
        entry["claimed_by"] = claimer_id
        entry["claimed_at"] = claimed_before_iso
        entry["claim_expires_at"] = claim_expires_at
        entry["updated_at"] = claimed_before_iso
        claimed.append(entry)
    return claimed

from __future__ import annotations

from typing import Any

from db import local_repository, supabase_repository


def using_supabase() -> bool:
    return supabase_repository.is_configured()


def get_tenant(identifier: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_tenant(identifier)
    return local_repository.get_tenant(identifier)


def list_tenants() -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_tenants()
    return local_repository.list_tenants()


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
    return local_repository.persist_run_record(record)


def create_artifact(record: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_artifact(record)
    return local_repository.create_artifact(record)


def update_artifact_lifecycle(artifact_id: str, target_state: str, *, tenant_id: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_artifact_lifecycle(artifact_id, target_state, tenant_id=tenant_id)
    return local_repository.update_artifact_lifecycle(artifact_id, target_state, tenant_id=tenant_id)


def list_artifacts(tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_artifacts(tenant_id)
    return local_repository.list_artifacts(tenant_id)


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_job(payload)
    return local_repository.create_job(payload)


def update_job_status(job_id: str, status: str, *, result: dict[str, Any] | None = None) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_job_status(job_id, status, result=result)
    return local_repository.update_job_status(job_id, status, result=result)


def get_job(job_id: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_job(job_id)
    return local_repository.get_job(job_id)


def list_jobs(*, tenant_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_jobs(tenant_id=tenant_id, run_id=run_id)
    return local_repository.list_jobs(tenant_id=tenant_id, run_id=run_id)


def count_active_jobs(tenant_id: str) -> int:
    if using_supabase():
        return supabase_repository.count_active_jobs(tenant_id)
    return local_repository.count_active_jobs(tenant_id)


def create_tenant(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_tenant(payload)
    return local_repository.create_tenant(payload)


def create_tenant_config(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_tenant_config(payload)
    return local_repository.create_tenant_config(payload)


def update_tenant_config(tenant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_tenant_config(tenant_id, updates)
    return local_repository.update_tenant_config(tenant_id, updates)


def delete_tenant(identifier: str) -> None:
    if using_supabase():
        supabase_repository.delete_tenant(identifier)
        return
    local_repository.delete_tenant(identifier)


def save_kill_switch(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.save_kill_switch(payload)
    return local_repository.save_kill_switch(payload)


def list_kill_switches(*, active_only: bool = False) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_kill_switches(active_only=active_only)
    return local_repository.list_kill_switches(active_only=active_only)


def create_alert(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_alert(payload)
    return local_repository.create_alert(payload)


def create_alert_and_sync_incident(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_alert_and_sync_incident(payload)
    return local_repository.create_alert_and_sync_incident(payload)


def list_alerts(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_alerts(tenant_id=tenant_id, status=status)
    return local_repository.list_alerts(tenant_id=tenant_id, status=status)


def update_alert(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_alert(alert_id, updates)
    return local_repository.update_alert(alert_id, updates)


def update_alert_and_sync_incident(alert_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_alert_and_sync_incident(alert_id, updates)
    return local_repository.update_alert_and_sync_incident(alert_id, updates)


def upsert_incident(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_incident(payload)
    return local_repository.upsert_incident(payload)


def sync_incident_from_alert(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.sync_incident_from_alert(payload)
    return local_repository.sync_incident_from_alert(payload)


def list_incidents(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_incidents(tenant_id=tenant_id, status=status)
    return local_repository.list_incidents(tenant_id=tenant_id, status=status)


def update_incident(incident_id: str, updates: dict[str, Any], *, expected_revision: int | None = None) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_incident(incident_id, updates, expected_revision=expected_revision)
    return local_repository.update_incident(incident_id, updates, expected_revision=expected_revision)


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
    if using_supabase():
        return supabase_repository.update_incident_runbook_progress(
            incident_id,
            step_index=step_index,
            status=status,
            actor_id=actor_id,
            note=note,
            expected_revision=expected_revision,
            expected_step_revision=expected_step_revision,
        )
    return local_repository.update_incident_runbook_progress(
        incident_id,
        step_index=step_index,
        status=status,
        actor_id=actor_id,
        note=note,
        expected_revision=expected_revision,
        expected_step_revision=expected_step_revision,
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
    if using_supabase():
        return supabase_repository.update_incident_runbook_assignment(
            incident_id,
            step_index=step_index,
            actor_id=actor_id,
            action=action,
            assigned_to=assigned_to,
            claim_ttl_seconds=claim_ttl_seconds,
            now_iso=now_iso,
            expected_revision=expected_revision,
            expected_step_revision=expected_step_revision,
        )
    return local_repository.update_incident_runbook_assignment(
        incident_id,
        step_index=step_index,
        actor_id=actor_id,
        action=action,
        assigned_to=assigned_to,
        claim_ttl_seconds=claim_ttl_seconds,
        now_iso=now_iso,
        expected_revision=expected_revision,
        expected_step_revision=expected_step_revision,
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
    if using_supabase():
        return supabase_repository.update_incident_workflow(
            incident_id,
            workflow_status=workflow_status,
            actor_id=actor_id,
            assigned_to=assigned_to,
            operator_notes=operator_notes,
            last_assignment_reason=last_assignment_reason,
            assignment_history_entry=assignment_history_entry,
            now_iso=now_iso,
            expected_revision=expected_revision,
        )
    return local_repository.update_incident_workflow(
        incident_id,
        workflow_status=workflow_status,
        actor_id=actor_id,
        assigned_to=assigned_to,
        operator_notes=operator_notes,
        last_assignment_reason=last_assignment_reason,
        assignment_history_entry=assignment_history_entry,
        now_iso=now_iso,
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
    if using_supabase():
        return supabase_repository.update_incident_reminder(
            incident_id,
            actor_id=actor_id,
            reminder_count=reminder_count,
            last_reminded_at=last_reminded_at,
            assigned_to=assigned_to,
            last_assignment_reason=last_assignment_reason,
            assignment_history_entry=assignment_history_entry,
            expected_revision=expected_revision,
        )
    return local_repository.update_incident_reminder(
        incident_id,
        actor_id=actor_id,
        reminder_count=reminder_count,
        last_reminded_at=last_reminded_at,
        assigned_to=assigned_to,
        last_assignment_reason=last_assignment_reason,
        assignment_history_entry=assignment_history_entry,
        expected_revision=expected_revision,
    )


def save_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.save_experiment(payload)
    return local_repository.save_experiment(payload)


def list_experiments() -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_experiments()
    return local_repository.list_experiments()


def acquire_lock(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.acquire_lock(payload)
    return local_repository.acquire_lock(payload)


def release_lock(mutation_surface: str) -> None:
    if using_supabase():
        supabase_repository.release_lock(mutation_surface)
        return
    local_repository.release_lock(mutation_surface)


def heartbeat_lock(mutation_surface: str, ttl_seconds: int) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.heartbeat_lock(mutation_surface, ttl_seconds)
    return local_repository.heartbeat_lock(mutation_surface, ttl_seconds)


def save_customer_content(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.save_customer_content(payload)
    return local_repository.save_customer_content(payload)


def list_customer_content(tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_customer_content(tenant_id)
    return local_repository.list_customer_content(tenant_id)


def delete_customer_content_before(tenant_id: str, cutoff_iso: str, *, dry_run: bool = False) -> int:
    if using_supabase():
        return supabase_repository.delete_customer_content_before(tenant_id, cutoff_iso, dry_run=dry_run)
    return local_repository.delete_customer_content_before(tenant_id, cutoff_iso, dry_run=dry_run)


def save_eval_run(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.save_eval_run(payload)
    return local_repository.save_eval_run(payload)


def list_eval_runs(*, tenant_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_eval_runs(tenant_id=tenant_id)
    return local_repository.list_eval_runs(tenant_id=tenant_id)


def create_audit_log(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_audit_log(payload)
    return local_repository.create_audit_log(payload)


def list_audit_logs(*, tenant_id: str | None = None, action_type: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_audit_logs(tenant_id=tenant_id, action_type=action_type)
    return local_repository.list_audit_logs(tenant_id=tenant_id, action_type=action_type)


def delete_audit_logs_before(cutoff_iso: str, *, tenant_id: str | None = None, dry_run: bool = False) -> int:
    if using_supabase():
        return supabase_repository.delete_audit_logs_before(cutoff_iso, tenant_id=tenant_id, dry_run=dry_run)
    return local_repository.delete_audit_logs_before(cutoff_iso, tenant_id=tenant_id, dry_run=dry_run)


def create_approval_request(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_approval_request(payload)
    return local_repository.create_approval_request(payload)


def update_approval_request(approval_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_approval_request(approval_id, updates)
    return local_repository.update_approval_request(approval_id, updates)


def list_approval_requests(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_approval_requests(tenant_id=tenant_id, status=status)
    return local_repository.list_approval_requests(tenant_id=tenant_id, status=status)


def upsert_scheduler_backlog_entry(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_scheduler_backlog_entry(payload)
    return local_repository.upsert_scheduler_backlog_entry(payload)


def list_scheduler_backlog(
    *,
    tenant_id: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_scheduler_backlog(tenant_id=tenant_id, job_type=job_type, status=status)
    return local_repository.list_scheduler_backlog(tenant_id=tenant_id, job_type=job_type, status=status)


def update_scheduler_backlog_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_scheduler_backlog_entry(entry_id, updates)
    return local_repository.update_scheduler_backlog_entry(entry_id, updates)


def claim_scheduler_backlog_entries(
    *,
    job_type: str,
    claimed_before_iso: str,
    max_entries: int,
    claimer_id: str,
    claim_ttl_seconds: int,
) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.claim_scheduler_backlog_entries(
            job_type=job_type,
            claimed_before_iso=claimed_before_iso,
            max_entries=max_entries,
            claimer_id=claimer_id,
            claim_ttl_seconds=claim_ttl_seconds,
        )
    return local_repository.claim_scheduler_backlog_entries(
        job_type=job_type,
        claimed_before_iso=claimed_before_iso,
        max_entries=max_entries,
        claimer_id=claimer_id,
        claim_ttl_seconds=claim_ttl_seconds,
    )

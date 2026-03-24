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


def upsert_agent_report(report: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_agent_report(report)
    return local_repository.upsert_agent_report(report)


def list_agent_reports(*, tenant_id: str | None = None, agent_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_agent_reports(tenant_id=tenant_id, agent_id=agent_id)
    return local_repository.list_agent_reports(tenant_id=tenant_id, agent_id=agent_id)


def create_shadow_comparison(record: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_shadow_comparison(record)
    return local_repository.create_shadow_comparison(record)


def create_artifact(record: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_artifact(record)
    return local_repository.create_artifact(record)


def update_artifact_lifecycle(artifact_id: str, target_state: str, *, tenant_id: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_artifact_lifecycle(artifact_id, target_state, tenant_id=tenant_id)
    return local_repository.update_artifact_lifecycle(artifact_id, target_state, tenant_id=tenant_id)


def list_artifacts(tenant_id: str, *, run_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_artifacts(tenant_id, run_id=run_id)
    return local_repository.list_artifacts(tenant_id, run_id=run_id)


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


def create_skill_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_skill_candidate(payload)
    return local_repository.create_skill_candidate(payload)


def list_skill_candidates(*, tenant_id: str | None = None, status: str | None = None, worker_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_skill_candidates(tenant_id=tenant_id, status=status, worker_id=worker_id)
    return local_repository.list_skill_candidates(tenant_id=tenant_id, status=status, worker_id=worker_id)


def update_skill_candidate(candidate_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_skill_candidate(candidate_id, updates)
    return local_repository.update_skill_candidate(candidate_id, updates)


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


def insert_inbound_message(msg: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_inbound_message(msg)
    return local_repository.insert_inbound_message(msg)


def get_inbound_message(tenant_id: str, message_id: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_inbound_message(tenant_id, message_id)
    return local_repository.get_inbound_message(tenant_id, message_id)


def get_inbound_messages_by_thread(tenant_id: str, thread_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_inbound_messages_by_thread(tenant_id, thread_id)
    return local_repository.get_inbound_messages_by_thread(tenant_id, thread_id)


def get_pending_scoring_messages(tenant_id: str, max_age_hours: int = 24) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_pending_scoring_messages(tenant_id, max_age_hours=max_age_hours)
    return local_repository.get_pending_scoring_messages(tenant_id, max_age_hours=max_age_hours)


def update_inbound_message_scoring(tenant_id: str, message_id: str, scoring_data: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_inbound_message_scoring(tenant_id, message_id, scoring_data)
    return local_repository.update_inbound_message_scoring(tenant_id, message_id, scoring_data)


def update_inbound_message_prospect(tenant_id: str, message_id: str, prospect_id: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_inbound_message_prospect(tenant_id, message_id, prospect_id)
    return local_repository.update_inbound_message_prospect(tenant_id, message_id, prospect_id)


def update_inbound_message_stage(tenant_id: str, message_id: str, stage: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_inbound_message_stage(tenant_id, message_id, stage)
    return local_repository.update_inbound_message_stage(tenant_id, message_id, stage)


def insert_inbound_draft(draft: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_inbound_draft(draft)
    return local_repository.insert_inbound_draft(draft)


def get_inbound_draft(tenant_id: str, message_id: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_inbound_draft(tenant_id, message_id)
    return local_repository.get_inbound_draft(tenant_id, message_id)


def get_pending_review_drafts(tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_pending_review_drafts(tenant_id)
    return local_repository.get_pending_review_drafts(tenant_id)


def update_inbound_draft_gate(tenant_id: str, draft_id: str, gate_data: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_inbound_draft_gate(tenant_id, draft_id, gate_data)
    return local_repository.update_inbound_draft_gate(tenant_id, draft_id, gate_data)


def update_inbound_draft_status(tenant_id: str, draft_id: str, send_status: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_inbound_draft_status(tenant_id, draft_id, send_status)
    return local_repository.update_inbound_draft_status(tenant_id, draft_id, send_status)


def insert_stage_transition(transition: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_stage_transition(transition)
    return local_repository.insert_stage_transition(transition)


def get_latest_stage(tenant_id: str, thread_id: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_latest_stage(tenant_id, thread_id)
    return local_repository.get_latest_stage(tenant_id, thread_id)


def get_stage_history(tenant_id: str, thread_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_stage_history(tenant_id, thread_id)
    return local_repository.get_stage_history(tenant_id, thread_id)


def upsert_poll_checkpoint(
    tenant_id: str,
    account_id: str,
    folder: str,
    last_uid: int,
    status: str = "ok",
    error: str | None = None,
) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_poll_checkpoint(
            tenant_id,
            account_id,
            folder,
            last_uid,
            status=status,
            error=error,
        )
    return local_repository.upsert_poll_checkpoint(
        tenant_id,
        account_id,
        folder,
        last_uid,
        status=status,
        error=error,
    )


def get_poll_checkpoint(tenant_id: str, account_id: str, folder: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_poll_checkpoint(tenant_id, account_id, folder)
    return local_repository.get_poll_checkpoint(tenant_id, account_id, folder)


def upsert_enrichment(tenant_id: str, cache_key: str, cache_type: str, source: str, data: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_enrichment(tenant_id, cache_key, cache_type, source, data)
    return local_repository.upsert_enrichment(tenant_id, cache_key, cache_type, source, data)


def get_enrichment(tenant_id: str, cache_key: str, cache_type: str, ttl_hours: int = 168) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_enrichment(tenant_id, cache_key, cache_type, ttl_hours=ttl_hours)
    return local_repository.get_enrichment(tenant_id, cache_key, cache_type, ttl_hours=ttl_hours)


def delete_expired_enrichment(tenant_id: str, max_age_hours: int = 336) -> int:
    if using_supabase():
        return supabase_repository.delete_expired_enrichment(tenant_id, max_age_hours=max_age_hours)
    return local_repository.delete_expired_enrichment(tenant_id, max_age_hours=max_age_hours)


def insert_prospect_email(tenant_id: str, prospect_id: str, email: str, source: str = "outbound") -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_prospect_email(tenant_id, prospect_id, email, source=source)
    return local_repository.insert_prospect_email(tenant_id, prospect_id, email, source=source)


def get_prospect_by_email(tenant_id: str, email: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_prospect_by_email(tenant_id, email)
    return local_repository.get_prospect_by_email(tenant_id, email)


def get_emails_for_prospect(tenant_id: str, prospect_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_emails_for_prospect(tenant_id, prospect_id)
    return local_repository.get_emails_for_prospect(tenant_id, prospect_id)


def get_enabled_email_accounts(tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_enabled_email_accounts(tenant_id)
    return local_repository.get_enabled_email_accounts(tenant_id)


def get_email_account(tenant_id: str, account_id: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_email_account(tenant_id, account_id)
    return local_repository.get_email_account(tenant_id, account_id)


def get_tenants_with_email_accounts() -> list[str]:
    if using_supabase():
        return supabase_repository.get_tenants_with_email_accounts()
    return local_repository.get_tenants_with_email_accounts()


def insert_growth_touchpoint(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_growth_touchpoint(payload)
    return local_repository.insert_growth_touchpoint(payload)


def list_growth_touchpoints(*, tenant_id: str, touchpoint_type: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_touchpoints(tenant_id=tenant_id, touchpoint_type=touchpoint_type)
    return local_repository.list_growth_touchpoints(tenant_id=tenant_id, touchpoint_type=touchpoint_type)


def insert_growth_belief_event(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_growth_belief_event(payload)
    return local_repository.insert_growth_belief_event(payload)


def list_growth_belief_events(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_belief_events(tenant_id=tenant_id)
    return local_repository.list_growth_belief_events(tenant_id=tenant_id)


def insert_growth_dlq_entry(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.insert_growth_dlq_entry(payload)
    return local_repository.insert_growth_dlq_entry(payload)


def resolve_growth_dlq_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.resolve_growth_dlq_entry(entry_id, updates)
    return local_repository.resolve_growth_dlq_entry(entry_id, updates)


def list_growth_dlq_entries(*, tenant_id: str, unresolved_only: bool = False) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_dlq_entries(tenant_id=tenant_id, unresolved_only=unresolved_only)
    return local_repository.list_growth_dlq_entries(tenant_id=tenant_id, unresolved_only=unresolved_only)


def upsert_growth_experiment_history(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_growth_experiment_history(payload)
    return local_repository.upsert_growth_experiment_history(payload)


def get_growth_experiment_history(experiment_id: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_growth_experiment_history(experiment_id)
    return local_repository.get_growth_experiment_history(experiment_id)


def list_growth_experiment_history(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_experiment_history(tenant_id=tenant_id)
    return local_repository.list_growth_experiment_history(tenant_id=tenant_id)


def list_growth_segment_performance(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_segment_performance(tenant_id=tenant_id)
    return local_repository.list_growth_segment_performance(tenant_id=tenant_id)


def list_growth_cost_per_acquisition(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_cost_per_acquisition(tenant_id=tenant_id)
    return local_repository.list_growth_cost_per_acquisition(tenant_id=tenant_id)


def list_growth_insights(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_insights(tenant_id=tenant_id)
    return local_repository.list_growth_insights(tenant_id=tenant_id)


def list_growth_founder_overrides(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_founder_overrides(tenant_id=tenant_id)
    return local_repository.list_growth_founder_overrides(tenant_id=tenant_id)


def list_growth_loss_records(*, tenant_id: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_growth_loss_records(tenant_id=tenant_id)
    return local_repository.list_growth_loss_records(tenant_id=tenant_id)


def list_growth_wedges(*, tenant_id: str) -> list[str]:
    if using_supabase():
        return supabase_repository.list_growth_wedges(tenant_id=tenant_id)
    return local_repository.list_growth_wedges(tenant_id=tenant_id)


def upsert_growth_wedge_fitness_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.upsert_growth_wedge_fitness_snapshot(payload)
    return local_repository.upsert_growth_wedge_fitness_snapshot(payload)


def get_latest_growth_wedge_fitness_snapshot(*, tenant_id: str, wedge: str) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.get_latest_growth_wedge_fitness_snapshot(tenant_id=tenant_id, wedge=wedge)
    return local_repository.get_latest_growth_wedge_fitness_snapshot(tenant_id=tenant_id, wedge=wedge)


# --- Voice CRUD ---


def insert_call_record(
    tenant_id: str,
    call_id: str,
    retell_call_id: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any] | None:
    if using_supabase():
        return supabase_repository.insert_call_record(tenant_id, call_id, retell_call_id, raw_payload)
    return local_repository.insert_call_record(tenant_id, call_id, retell_call_id, raw_payload)


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
    kwargs = dict(
        end_call_reason=end_call_reason,
        booking_id=booking_id,
        callback_scheduled=callback_scheduled,
        call_duration_seconds=call_duration_seconds,
        call_recording_url=call_recording_url,
    )
    if using_supabase():
        return supabase_repository.update_call_record_extraction(tenant_id, call_id, extracted_fields, **kwargs)
    return local_repository.update_call_record_extraction(tenant_id, call_id, extracted_fields, **kwargs)


def update_raw_payload(
    tenant_id: str,
    call_id: str,
    raw_payload: dict[str, Any],
) -> None:
    """Persist enriched raw_retell_payload (after Retell API fetch adds tool-call data)."""
    if using_supabase():
        supabase_repository.update_raw_payload(tenant_id, call_id, raw_payload)
    else:
        local_repository.update_raw_payload(tenant_id, call_id, raw_payload)


def get_caller_history(tenant_id: str, phone: str) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.get_caller_history(tenant_id, phone)
    return local_repository.get_caller_history(tenant_id, phone)


def query_jobs_by_phone(phone: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.query_jobs_by_phone(phone)
    return local_repository.query_jobs_by_phone(phone)


def query_calls_by_phone(phone: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.query_calls_by_phone(phone)
    return local_repository.query_calls_by_phone(phone)


def query_bookings_by_phone(phone: str) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.query_bookings_by_phone(phone)
    return local_repository.query_bookings_by_phone(phone)


def get_voice_api_keys() -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.get_voice_api_keys()
    return local_repository.get_voice_api_keys()

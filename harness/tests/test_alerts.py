from pathlib import Path

from db.repository import create_alert, create_job, list_audit_logs, list_incidents, update_alert, update_incident, upsert_scheduler_backlog_entry
from harness.alerts.escalation import auto_escalate_alerts, resolve_escalation_policy
from harness.alerts.lifecycle import validate_alert_transition
from harness.alerts.recovery import auto_resolve_recovered_alerts, resolve_recovery_cooldown_minutes
from harness.alerts.evaluator import evaluate_alerts
from harness.incident_notifications import notify_incident
from harness.incident_classification import classify_incident
from harness.incident_runbooks import (
    apply_runbook_step_assignment,
    apply_runbook_step_update,
    build_runbook_execution_plan,
    pending_runbook_steps,
    resolve_incident_runbook,
    workflow_requires_approval,
    workflow_requires_completed_runbook,
)
from harness.alerts.suppression import resolve_suppression_window_minutes
from harness.alerts.thresholds import resolve_thresholds
from harness.incident_reminders import send_incident_reminders
from harness.incident_routing import resolve_assignee, resolve_reassign_after_reminders
from harness.incidents import record_incident_from_alert


def test_alerts_are_created_when_thresholds_breach() -> None:
    for index in range(3):
        create_job(
            {
                "tenant_id": "tenant-alpha",
                "origin_worker_id": "customer-analyst",
                "origin_run_id": f"run-{index}",
                "job_type": "harness_run",
                "status": "failed",
                "idempotency_key": f"job-{index}",
                "result": {"policy_verdict": "deny", "verification": {"passed": False}},
            }
        )
    alerts = evaluate_alerts(tenant_id="tenant-alpha")
    assert len(alerts) >= 1


def test_scheduler_alerts_are_created_for_stale_claims_and_old_backlog() -> None:
    upsert_scheduler_backlog_entry(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "job_type": "retention",
            "scheduled_for": "2026-01-15T06:00:00+00:00",
            "status": "pending",
            "scheduled_timezone": "America/Detroit",
            "scheduled_hour": 3,
            "scheduled_minute": 15,
            "payload": {"tenant_slug": "tenant-alpha", "lateness_minutes": 120},
        }
    )
    upsert_scheduler_backlog_entry(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "job_type": "tenant_eval",
            "scheduled_for": "2026-01-15T08:00:00+00:00",
            "status": "claimed",
            "scheduled_timezone": "America/Detroit",
            "scheduled_hour": 4,
            "scheduled_minute": 15,
            "claim_expires_at": "2026-01-15T08:10:00+00:00",
            "claimed_by": "scheduler-test",
            "payload": {"tenant_slug": "tenant-alpha", "lateness_minutes": 10},
        }
    )

    alerts = evaluate_alerts(tenant_id="00000000-0000-0000-0000-000000000001", window_minutes=15)
    alert_types = {alert["alert_type"] for alert in alerts}

    assert "scheduler_stale_claims" in alert_types
    assert "scheduler_backlog_age" in alert_types


def test_tenant_threshold_overrides_are_applied() -> None:
    for index in range(2):
        create_job(
            {
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "origin_worker_id": "customer-analyst",
                "origin_run_id": f"beta-run-{index}",
                "job_type": "harness_run",
                "status": "failed",
                "idempotency_key": f"beta-job-{index}",
                "result": {"policy_verdict": "deny", "verification": {"passed": False}},
            }
        )

    alerts = evaluate_alerts(tenant_id="00000000-0000-0000-0000-000000000002")
    alert_types = {alert["alert_type"] for alert in alerts}

    assert "job_failure_spike" in alert_types
    assert "policy_block_rate" not in alert_types

    failure_alert = next(alert for alert in alerts if alert["alert_type"] == "job_failure_spike")
    assert failure_alert["metrics"]["threshold"] == 2.0
    assert failure_alert["metrics"]["applied_thresholds"]["job_failure_spike"] == 2.0


def test_invalid_threshold_overrides_fall_back_to_defaults() -> None:
    thresholds = resolve_thresholds(
        {
            "alert_thresholds": {
                "policy_block_rate": -1,
                "job_failure_spike": "high",
                "scheduler_backlog_age": True,
            }
        }
    )

    assert thresholds["policy_block_rate"] == 0.5
    assert thresholds["job_failure_spike"] == 3
    assert thresholds["scheduler_backlog_age"] == 60


def test_dashboard_notifications_are_written_locally(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_ALERT_ROOT", str(tmp_path))
    create_job(
        {
            "tenant_id": "tenant-alpha",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-dashboard-notify",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "dashboard-notify",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    alerts = evaluate_alerts(tenant_id="tenant-alpha")

    assert alerts
    assert alerts[0]["notification"]["delivered"] is True
    assert any(channel["channel"] == "dashboard" for channel in alerts[0]["notification"]["channels"])
    assert (tmp_path / "dashboard.jsonl").exists()


def test_webhook_notifications_use_tenant_override(monkeypatch) -> None:
    deliveries: list[tuple[str, dict[str, object], float]] = []

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, json: dict[str, object], timeout: float) -> DummyResponse:
        deliveries.append((url, json, timeout))
        return DummyResponse()

    monkeypatch.setattr("harness.alerts.notifier.httpx.post", fake_post)
    monkeypatch.setenv("CALLLOCK_ALERT_ROOT", "/tmp/calllock-alert-test")
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-webhook-notify-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "webhook-notify-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-webhook-notify-2",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "webhook-notify-2",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    alerts = evaluate_alerts(tenant_id="tenant-beta")

    assert alerts
    assert any(channel["channel"] == "webhook" and channel["delivered"] is True for channel in alerts[0]["notification"]["channels"])
    assert deliveries[0][0] == "https://tenant-beta.example.test/alerts"
    assert deliveries[0][2] == 5.0


def test_email_notifications_use_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_EMAIL_OUTBOX_ROOT", str(tmp_path))
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-email-notify-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "email-notify-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-email-notify-2",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "email-notify-2",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    alerts = evaluate_alerts(tenant_id="tenant-beta")

    assert alerts
    email_channel = next(channel for channel in alerts[0]["notification"]["channels"] if channel["channel"] == "email")
    assert email_channel["delivered"] is True
    assert email_channel["backend"] == "outbox"
    assert (tmp_path / "alerts.jsonl").exists()


def test_sms_notifications_use_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_SMS_OUTBOX_ROOT", str(tmp_path))
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-sms-notify-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "sms-notify-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-sms-notify-2",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "sms-notify-2",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    alerts = evaluate_alerts(tenant_id="tenant-beta")

    assert alerts
    sms_channel = next(channel for channel in alerts[0]["notification"]["channels"] if channel["channel"] == "sms")
    assert sms_channel["delivered"] is True
    assert sms_channel["backend"] == "outbox"
    assert (tmp_path / "alerts.jsonl").exists()


def test_pager_notifications_use_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_PAGER_OUTBOX_ROOT", str(tmp_path))
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-pager-notify-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "pager-notify-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )
    create_job(
        {
            "tenant_id": "tenant-beta",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-pager-notify-2",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "pager-notify-2",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    alerts = evaluate_alerts(tenant_id="tenant-beta")

    assert alerts
    pager_channel = next(channel for channel in alerts[0]["notification"]["channels"] if channel["channel"] == "pager")
    assert pager_channel["delivered"] is True
    assert pager_channel["backend"] == "outbox"
    assert (tmp_path / "alerts.jsonl").exists()


def test_incident_notifications_use_assignee_email_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_EMAIL_OUTBOX_ROOT", str(tmp_path))
    incident = {
        "id": "incident-email",
        "incident_revision": 3,
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "incident_key": "tenant-beta:job_failure_spike",
        "alert_type": "job_failure_spike",
        "incident_domain": "operations",
        "incident_category": "worker_reliability",
        "remediation_category": "worker_debugging",
        "incident_urgency": "high",
        "runbook_id": "rb-worker-reliability",
        "runbook_title": "Worker Reliability Response",
        "runbook_steps": [],
        "runbook_progress": [],
        "runbook_progress_summary": {},
        "runbook_execution_plan": {},
        "completion_policy": {},
        "status": "open",
        "workflow_status": "investigating",
        "assigned_to": "oncall-2",
        "current_episode": 1,
        "occurrence_count": 1,
    }
    tenant_config = {
        "incident_notification_channels": ["assignee_email"],
        "incident_assignees": {
            "oncall-2": {"email": "oncall-2@example.test"},
        },
    }

    notification = notify_incident(incident, tenant_config, reminder=True)

    email_channel = notification["channels"][0]
    assert email_channel["channel"] == "assignee_email"
    assert email_channel["delivered"] is True
    assert email_channel["backend"] == "outbox"
    assert (tmp_path / "incidents.jsonl").exists()


def test_incident_notifications_use_assignee_sms_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_SMS_OUTBOX_ROOT", str(tmp_path))
    incident = {
        "id": "incident-sms",
        "incident_revision": 4,
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "incident_key": "tenant-beta:scheduler_stale_claims",
        "alert_type": "scheduler_stale_claims",
        "incident_domain": "operations",
        "incident_category": "scheduler_health",
        "remediation_category": "scheduler_recovery",
        "incident_urgency": "medium",
        "runbook_id": "rb-scheduler-health",
        "runbook_title": "Scheduler Recovery Response",
        "runbook_steps": [],
        "runbook_progress": [],
        "runbook_progress_summary": {},
        "runbook_execution_plan": {},
        "completion_policy": {},
        "status": "open",
        "workflow_status": "investigating",
        "assigned_to": "oncall-1",
        "current_episode": 1,
        "occurrence_count": 1,
    }
    tenant_config = {
        "incident_notification_channels": ["assignee_sms"],
        "incident_assignees": {
            "oncall-1": {"phone": "+15550000011"},
        },
    }

    notification = notify_incident(incident, tenant_config, reminder=False)

    sms_channel = notification["channels"][0]
    assert sms_channel["channel"] == "assignee_sms"
    assert sms_channel["delivered"] is True
    assert sms_channel["backend"] == "outbox"
    assert (tmp_path / "incidents.jsonl").exists()


def test_incident_notifications_use_assignee_pager_outbox(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_PAGER_OUTBOX_ROOT", str(tmp_path))
    incident = {
        "id": "incident-pager",
        "incident_revision": 5,
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "incident_key": "tenant-beta:job_failure_spike",
        "alert_type": "job_failure_spike",
        "incident_domain": "operations",
        "incident_category": "worker_reliability",
        "remediation_category": "worker_debugging",
        "incident_urgency": "high",
        "runbook_id": "rb-worker-reliability",
        "runbook_title": "Worker Reliability Response",
        "runbook_steps": [],
        "runbook_progress": [],
        "runbook_progress_summary": {},
        "runbook_execution_plan": {},
        "completion_policy": {},
        "status": "open",
        "workflow_status": "acknowledged",
        "assigned_to": "oncall-2",
        "current_episode": 1,
        "occurrence_count": 1,
    }
    tenant_config = {
        "incident_notification_channels": ["assignee_pager"],
        "incident_assignees": {
            "oncall-2": {"pager_target": "ops-oncall-2"},
        },
    }

    notification = notify_incident(incident, tenant_config, reminder=True)

    pager_channel = notification["channels"][0]
    assert pager_channel["channel"] == "assignee_pager"
    assert pager_channel["delivered"] is True
    assert pager_channel["backend"] == "outbox"
    assert (tmp_path / "incidents.jsonl").exists()


def test_alert_lifecycle_transitions_and_metadata() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
        }
    )

    acknowledged = update_alert(
        alert["id"],
        {
            "status": "acknowledged",
            "acknowledged_at": "2026-03-13T10:00:00+00:00",
            "acknowledged_by": "operator-1",
            "resolution_notes": "Investigating",
        },
    )
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["acknowledged_by"] == "operator-1"

    escalated = update_alert(
        alert["id"],
        {
            "status": "escalated",
            "escalated_at": "2026-03-13T10:05:00+00:00",
            "escalated_by": "operator-2",
            "resolution_notes": "Paging on-call",
        },
    )
    assert escalated["status"] == "escalated"
    assert escalated["escalated_by"] == "operator-2"

    resolved = update_alert(
        alert["id"],
        {
            "status": "resolved",
            "resolved_at": "2026-03-13T10:15:00+00:00",
            "resolved_by": "operator-3",
            "resolution_notes": "Recovered",
        },
    )
    assert resolved["status"] == "resolved"
    assert resolved["resolved_by"] == "operator-3"


def test_invalid_alert_transition_is_rejected() -> None:
    validate_alert_transition("open", "acknowledged")
    try:
        validate_alert_transition("resolved", "acknowledged")
    except ValueError as exc:
        assert "Invalid alert transition" in str(exc)
    else:
        raise AssertionError("expected resolved -> acknowledged to fail")


def test_auto_escalation_applies_tenant_policy_and_logs_audit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_ALERT_ROOT", str(tmp_path))
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    escalated = auto_escalate_alerts(
        tenant_id="00000000-0000-0000-0000-000000000002",
        now_iso="2026-03-13T10:00:00+00:00",
    )

    assert len(escalated) == 1
    assert escalated[0]["id"] == alert["id"]
    assert escalated[0]["status"] == "escalated"
    assert escalated[0]["escalated_by"] == "system:auto-escalation"
    assert escalated[0]["notification"]["delivered"] is True
    assert any(log["action_type"] == "alert.auto_escalated" for log in list_audit_logs())


def test_invalid_escalation_policy_overrides_fall_back_to_defaults() -> None:
    policy = resolve_escalation_policy(
        {
            "alert_escalation_policy": {
                "open": {"high": -1, "medium": "soon"},
                "acknowledged": {"high": True},
            }
        }
    )

    assert policy["open"]["high"] == 30
    assert policy["open"]["medium"] == 60
    assert policy["acknowledged"]["high"] == 120


def test_duplicate_alerts_are_suppressed_and_occurrence_count_increments(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_ALERT_ROOT", str(tmp_path))
    create_job(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "dup-run-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "dup-job-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )
    create_job(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "dup-run-2",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "dup-job-2",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    first = evaluate_alerts(tenant_id="00000000-0000-0000-0000-000000000002")
    second = evaluate_alerts(tenant_id="00000000-0000-0000-0000-000000000002")

    assert first
    assert second
    duplicate = next(alert for alert in second if alert["alert_type"] == "job_failure_spike")
    assert duplicate["suppressed_duplicate"] is True
    assert duplicate["occurrence_count"] == 2
    assert duplicate["notification"]["delivered"] is False


def test_invalid_suppression_window_falls_back_to_default() -> None:
    assert resolve_suppression_window_minutes({"alert_suppression_window_minutes": -1}) == 60
    assert resolve_suppression_window_minutes({"alert_suppression_window_minutes": "soon"}) == 60


def test_auto_recovery_resolves_alert_after_cooldown() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "last_observed_at": "2026-03-13T09:50:00+00:00",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    resolved = auto_resolve_recovered_alerts(
        metrics={"job_failure_spike": 0},
        thresholds={"job_failure_spike": 2.0},
        tenant_id="00000000-0000-0000-0000-000000000002",
        now_iso="2026-03-13T10:00:00+00:00",
    )

    assert len(resolved) == 1
    assert resolved[0]["id"] == alert["id"]
    assert resolved[0]["status"] == "resolved"
    assert resolved[0]["resolved_by"] == "system:auto-recovery"
    assert any(log["action_type"] == "alert.auto_resolved" for log in list_audit_logs())


def test_invalid_recovery_cooldown_falls_back_to_default() -> None:
    assert resolve_recovery_cooldown_minutes({"alert_recovery_cooldown_minutes": -1}) == 15
    assert resolve_recovery_cooldown_minutes({"alert_recovery_cooldown_minutes": "later"}) == 15


def test_incident_records_follow_alert_lifecycle() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "occurrence_count": 1,
            "last_observed_at": "2026-03-13T09:45:00+00:00",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    assert incident["status"] == "open"
    assert incident["occurrence_count"] == 1

    resolved_alert = update_alert(
        alert["id"],
        {
            "status": "resolved",
            "resolved_at": "2026-03-13T10:00:00+00:00",
            "resolved_by": "system:auto-recovery",
            "occurrence_count": 2,
        },
    )
    incident = record_incident_from_alert(resolved_alert)
    assert incident["status"] == "resolved"
    assert incident["occurrence_count"] == 2
    assert list_incidents(status="resolved")[0]["incident_key"] == incident["incident_key"]


def test_incident_reopen_starts_new_episode() -> None:
    first_alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(first_alert)
    resolved_alert = update_alert(
        first_alert["id"],
        {
            "status": "resolved",
            "resolved_at": "2026-03-13T09:10:00+00:00",
            "resolved_by": "operator-1",
        },
    )
    incident = record_incident_from_alert(resolved_alert)
    assert incident["episode_count"] == 1

    reopened_alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached again",
            "created_at": "2026-03-13T10:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(reopened_alert)
    assert incident["status"] == "open"
    assert incident["current_episode"] == 2
    assert incident["episode_count"] == 2
    assert incident["episode_history"][0]["episode"] == 1


def test_incident_operator_workflow_fields_are_preserved_across_alert_sync() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    update_incident(
        incident["id"],
        {
            "workflow_status": "investigating",
            "assigned_to": "oncall-1",
            "operator_notes": "Working incident",
            "last_reviewed_by": "operator-1",
        },
    )

    synced = record_incident_from_alert(alert)
    assert synced["workflow_status"] == "investigating"
    assert synced["assigned_to"] == "oncall-1"
    assert synced["operator_notes"] == "Working incident"


def test_incident_reminders_are_sent_for_stale_assignments(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_INCIDENT_ROOT", str(tmp_path))
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    update_incident(
        incident["id"],
        {
            "workflow_status": "investigating",
            "assigned_to": "oncall-1",
            "last_reviewed_at": "2026-03-13T09:40:00+00:00",
        },
    )

    reminders = send_incident_reminders(
        tenant_id="00000000-0000-0000-0000-000000000002",
        now_iso="2026-03-13T10:00:00+00:00",
    )

    assert reminders
    assert reminders[0]["assigned_to"] == "oncall-2"
    assert reminders[0]["reminder_count"] == 1
    assert reminders[0]["notification"]["delivered"] is True


def test_incident_classification_uses_custom_rule_before_defaults() -> None:
    classification = classify_incident(
        {"alert_type": "job_failure_spike", "severity": "high"},
        {
            "incident_classification_rules": [
                {
                    "match": {"alert_type": "job_failure_spike"},
                    "incident_domain": "customer-ops",
                    "incident_category": "billing-review",
                    "remediation_category": "refund-review",
                    "urgency": "medium",
                }
            ]
        },
    )

    assert classification["incident_domain"] == "customer_ops"
    assert classification["incident_category"] == "billing_review"
    assert classification["remediation_category"] == "refund_review"
    assert classification["incident_urgency"] == "medium"


def test_recorded_incident_includes_normalized_classification() -> None:
    incident = record_incident_from_alert(
        create_alert(
            {
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "alert_type": "scheduler_backlog_age",
                "severity": "high",
                "message": "Scheduler backlog is too old",
                "created_at": "2026-03-13T09:00:00+00:00",
            }
        )
    )

    assert incident["incident_domain"] == "operations"
    assert incident["incident_category"] == "scheduler_health"
    assert incident["remediation_category"] == "scheduler_recovery"
    assert incident["incident_urgency"] == "medium"


def test_incident_runbook_binds_from_normalized_category() -> None:
    runbook = resolve_incident_runbook(
        {
            "alert_type": "job_failure_spike_custom_suffix",
            "incident_category": "worker_reliability",
            "remediation_category": "worker_debugging",
            "incident_domain": "operations",
        },
        {
            "incident_runbooks": {
                "worker_reliability": {
                    "runbook_id": "rb-worker-reliability",
                    "title": "Worker Reliability",
                    "steps": [
                        {"title": "Check recent failures", "required": True, "parallel_group": "triage"},
                        {"title": "Review verifier output", "required": False, "depends_on": [1]},
                    ],
                    "completion_policy": {"required_workflow_statuses": ["closed"]},
                    "approval_policy": {"required_workflow_statuses": ["closed"]},
                }
            }
        },
    )

    assert runbook["runbook_id"] == "rb-worker-reliability"
    assert runbook["runbook_steps"][0]["title"] == "Check recent failures"
    assert runbook["runbook_steps"][0]["parallel_group"] == "triage"
    assert runbook["runbook_steps"][1]["required"] is False
    assert runbook["runbook_steps"][1]["depends_on"] == [1]
    assert workflow_requires_completed_runbook(runbook, "closed") is True
    assert workflow_requires_approval(runbook, "closed") is True
    assert workflow_requires_approval(runbook, "investigating") is False


def test_pending_runbook_steps_reflect_completion_state() -> None:
    incident = {
        "runbook_progress": [
            {"step_index": 1, "title": "A", "status": "completed", "required": True},
            {"step_index": 2, "title": "B", "status": "pending", "required": False},
            {"step_index": 3, "title": "C", "status": "pending", "required": True},
        ]
    }
    pending = pending_runbook_steps(incident)
    assert len(pending) == 1
    assert pending[0]["step_index"] == 3


def test_runbook_progress_blocks_completion_until_dependencies_are_done() -> None:
    incident = {
        "runbook_progress": [
            {
                "step_id": "step-1",
                "step_index": 1,
                "title": "Inspect queue",
                "required": True,
                "depends_on": [],
                "parallel_group": None,
                "status": "pending",
                "blocked_by": [],
                "is_blocked": False,
            },
            {
                "step_id": "step-2",
                "step_index": 2,
                "title": "Release stuck claims",
                "required": True,
                "depends_on": [1],
                "parallel_group": None,
                "status": "pending",
                "blocked_by": [1],
                "is_blocked": True,
            },
        ]
    }
    try:
        apply_runbook_step_update(
            incident,
            step_index=2,
            status="completed",
            actor_id="operator-1",
            note="Tried to skip ahead",
        )
    except ValueError as exc:
        assert "blocked by dependencies" in str(exc)
    else:
        raise AssertionError("expected dependency-blocked step completion to fail")


def test_runbook_execution_plan_exposes_runnable_and_blocked_steps() -> None:
    plan = build_runbook_execution_plan(
        [
            {
                "step_index": 1,
                "title": "Review failures",
                "required": True,
                "parallel_group": "triage",
                "assigned_to": "oncall-1",
                "claimed_by": "operator-1",
                "status": "pending",
                "is_blocked": False,
            },
            {
                "step_index": 2,
                "title": "Confirm scope",
                "required": True,
                "parallel_group": "triage",
                "status": "completed",
                "is_blocked": False,
            },
            {
                "step_index": 3,
                "title": "Rollback decision",
                "required": False,
                "parallel_group": None,
                "status": "pending",
                "is_blocked": True,
                "blocked_by": [1],
            },
        ]
    )
    assert plan["next_runnable_steps"][0]["title"] == "Review failures"
    assert plan["next_runnable_steps"][0]["assigned_to"] == "oncall-1"
    assert plan["next_runnable_steps"][0]["claimed_by"] == "operator-1"
    assert plan["blocked_steps"][0]["waiting_on_titles"] == ["Review failures"]
    assert plan["parallel_groups"]["triage"][0]["step_index"] == 1


def test_runbook_step_assignment_updates_plan_ownership() -> None:
    incident = {
        "runbook_progress": [
            {
                "step_id": "step-1",
                "step_index": 1,
                "title": "Review failures",
                "required": True,
                "depends_on": [],
                "parallel_group": "triage",
                "status": "pending",
                "assigned_to": None,
                "claimed_by": None,
                "claimed_at": None,
                "blocked_by": [],
                "is_blocked": False,
            }
        ]
    }
    patch = apply_runbook_step_assignment(
        incident,
        step_index=1,
        actor_id="operator-1",
        action="claim",
        assigned_to="oncall-1",
        now_iso="2026-03-13T10:00:00+00:00",
    )
    assert patch["runbook_progress"][0]["assigned_to"] == "oncall-1"
    assert patch["runbook_progress"][0]["claimed_by"] == "operator-1"
    assert patch["runbook_progress"][0]["claim_expires_at"] == "2026-03-13T10:10:00+00:00"
    assert patch["runbook_progress"][0]["step_revision"] == 2
    assert patch["runbook_execution_plan"]["next_runnable_steps"][0]["assigned_to"] == "oncall-1"


def test_runbook_step_assignment_rejects_active_claim_conflict_and_allows_expired_reclaim() -> None:
    incident = {
        "runbook_progress": [
            {
                "step_id": "step-1",
                "step_index": 1,
                "title": "Review failures",
                "required": True,
                "depends_on": [],
                "parallel_group": "triage",
                "status": "pending",
                "assigned_to": "oncall-1",
                "claimed_by": "operator-1",
                "claimed_at": "2026-03-13T10:00:00+00:00",
                "claim_expires_at": "2026-03-13T10:10:00+00:00",
                "blocked_by": [],
                "is_blocked": False,
            }
        ]
    }
    try:
        apply_runbook_step_assignment(
            incident,
            step_index=1,
            actor_id="operator-2",
            action="claim",
            now_iso="2026-03-13T10:05:00+00:00",
        )
    except ValueError as exc:
        assert "already claimed" in str(exc)
    else:
        raise AssertionError("expected active claim conflict")

    patch = apply_runbook_step_assignment(
        incident,
        step_index=1,
        actor_id="operator-2",
        action="claim",
        now_iso="2026-03-13T10:11:00+00:00",
    )
    assert patch["runbook_progress"][0]["claimed_by"] == "operator-2"


def test_runbook_step_assignment_heartbeat_extends_claim() -> None:
    incident = {
        "runbook_progress": [
            {
                "step_id": "step-1",
                "step_index": 1,
                "title": "Review failures",
                "required": True,
                "depends_on": [],
                "parallel_group": "triage",
                "status": "pending",
                "assigned_to": "oncall-1",
                "claimed_by": "operator-1",
                "claimed_at": "2026-03-13T10:00:00+00:00",
                "claim_expires_at": "2026-03-13T10:10:00+00:00",
                "blocked_by": [],
                "is_blocked": False,
            }
        ]
    }
    patch = apply_runbook_step_assignment(
        incident,
        step_index=1,
        actor_id="operator-1",
        action="heartbeat",
        claim_ttl_seconds=300,
        now_iso="2026-03-13T10:04:00+00:00",
    )
    assert patch["runbook_progress"][0]["claim_expires_at"] == "2026-03-13T10:09:00+00:00"


def test_incident_update_rejects_stale_revision() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    starting_revision = incident["incident_revision"]
    first = update_incident(
        incident["id"],
        {"operator_notes": "first write"},
        expected_revision=starting_revision,
    )
    assert first["incident_revision"] == starting_revision + 1
    try:
        update_incident(
            incident["id"],
            {"operator_notes": "stale write"},
            expected_revision=starting_revision,
        )
    except ValueError as exc:
        assert "incident revision conflict" in str(exc)
    else:
        raise AssertionError("expected stale revision conflict")


def test_incident_runbook_progress_initializes_and_resets_on_reopen() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    assert incident["runbook_progress_summary"]["total_steps"] == len(incident["runbook_steps"])
    assert incident["runbook_progress_summary"]["completed_steps"] == 0
    assert incident["runbook_progress_summary"]["required_steps"] == 2
    assert incident["runbook_progress_summary"]["optional_steps"] == 1
    assert incident["runbook_execution_plan"]["next_runnable_steps"][0]["parallel_group"] == "triage"
    assert incident["runbook_execution_plan"]["blocked_steps"][0]["waiting_on_titles"] == [
        "Review the latest failed jobs and verification findings.",
        "Confirm whether the issue is isolated to one worker or cross-worker.",
    ]
    assert incident["runbook_progress"][2]["is_blocked"] is True
    assert incident["runbook_progress"][2]["parallel_group"] is None

    patch = apply_runbook_step_update(
        incident,
        step_index=1,
        status="completed",
        actor_id="operator-1",
        note="Checked failures",
        now_iso="2026-03-13T10:00:00+00:00",
    )
    updated = update_incident(incident["id"], patch)
    assert updated["runbook_progress_summary"]["completed_steps"] == 1
    assert updated["runbook_progress"][0]["completed_by"] == "operator-1"
    assert updated["runbook_progress"][2]["is_blocked"] is True

    resolved_alert = update_alert(
        alert["id"],
        {
            "status": "resolved",
            "resolved_at": "2026-03-13T11:00:00+00:00",
            "resolved_by": "operator-1",
        },
    )
    resolved_incident = record_incident_from_alert(resolved_alert)
    assert resolved_incident["status"] == "resolved"

    reopened_alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached again",
            "created_at": "2026-03-13T12:00:00+00:00",
            "last_observed_at": "2026-03-13T12:00:00+00:00",
        }
    )
    reopened_incident = record_incident_from_alert(reopened_alert)
    assert reopened_incident["episode_count"] == 2
    assert reopened_incident["runbook_progress_summary"]["completed_steps"] == 0
    assert reopened_incident["runbook_progress"][0]["status"] == "pending"


def test_assignee_routing_uses_fallback_when_preferred_unavailable() -> None:
    assignee, reason = resolve_assignee(
        "oncall-1",
        {
            "timezone": "UTC",
            "incident_default_assignee": "oncall-1",
            "incident_assignees": {
                "oncall-1": {"availability": {"days": ["mon"], "start_hour": 9, "end_hour": 17}, "fallback_assignee": "oncall-2"},
                "oncall-2": {"availability": {"days": ["mon"], "start_hour": 0, "end_hour": 24}},
            },
        },
        now_iso="2026-03-16T20:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "fallback_from:oncall-1"


def test_assignee_routing_uses_rotation_pool_when_no_preferred_available() -> None:
    assignee, reason = resolve_assignee(
        None,
        {
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_assignees": {
                "oncall-1": {"availability": {"days": ["mon"], "start_hour": 0, "end_hour": 24}},
                "oncall-2": {"availability": {"days": ["mon"], "start_hour": 0, "end_hour": 24}},
            },
        },
        now_iso="2026-03-16T01:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "rotation_primary"


def test_assignee_routing_prefers_least_loaded_rotation_candidate() -> None:
    for index in range(2):
        incident = record_incident_from_alert(
            create_alert(
                {
                    "tenant_id": "00000000-0000-0000-0000-000000000002",
                    "alert_type": f"job_failure_spike_{index}",
                    "severity": "high",
                    "message": "job_failure_spike threshold breached",
                    "created_at": "2026-03-13T09:00:00+00:00",
                }
            )
        )
        update_incident(
            incident["id"],
            {"workflow_status": "investigating", "assigned_to": "oncall-1"},
        )

    incident = record_incident_from_alert(
        create_alert(
            {
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "alert_type": "job_failure_spike_2",
                "severity": "high",
                "message": "job_failure_spike threshold breached",
                "created_at": "2026-03-13T09:00:00+00:00",
            }
        )
    )
    update_incident(
        incident["id"],
        {"workflow_status": "investigating", "assigned_to": "oncall-2"},
    )

    assignee, reason = resolve_assignee(
        None,
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_assignees": {
                "oncall-1": {"availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24}},
                "oncall-2": {"availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24}},
            },
        },
        now_iso="2026-03-13T01:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "rotation_primary"


def test_assignee_routing_prefers_higher_weight_when_load_is_equal() -> None:
    assignee, reason = resolve_assignee(
        None,
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_assignees": {
                "oncall-1": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 1.0,
                    "max_active_incidents": 2,
                },
                "oncall-2": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 2.0,
                    "max_active_incidents": 2,
                },
            },
        },
        now_iso="2026-03-13T01:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "rotation_primary"


def test_assignee_routing_prefers_skill_match_before_weight() -> None:
    assignee, reason = resolve_assignee(
        None,
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_skill_requirements": {"job_failure_spike": ["hvac"]},
            "incident_assignees": {
                "oncall-1": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 3.0,
                    "max_active_incidents": 2,
                    "skills": ["billing"],
                },
                "oncall-2": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 1.0,
                    "max_active_incidents": 2,
                    "skills": ["hvac"],
                },
            },
        },
        incident_type="job_failure_spike",
        now_iso="2026-03-13T01:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "rotation_primary"


def test_assignee_routing_prefers_normalized_incident_category_over_raw_alert_type() -> None:
    assignee, reason = resolve_assignee(
        None,
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_skill_requirements": {"worker_reliability": ["hvac"]},
            "incident_assignees": {
                "oncall-1": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 3.0,
                    "max_active_incidents": 2,
                    "skills": ["billing"],
                },
                "oncall-2": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 1.0,
                    "max_active_incidents": 2,
                    "skills": ["hvac"],
                },
            },
        },
        incident_type="job_failure_spike_custom_suffix",
        incident_category="worker_reliability",
        now_iso="2026-03-13T01:00:00+00:00",
    )
    assert assignee == "oncall-2"
    assert reason == "rotation_primary"


def test_assignee_routing_uses_capacity_adjusted_load() -> None:
    for index in range(2):
        incident = record_incident_from_alert(
            create_alert(
                {
                    "tenant_id": "00000000-0000-0000-0000-000000000002",
                    "alert_type": f"capacity_case_{index}",
                    "severity": "high",
                    "message": "capacity case",
                    "created_at": "2026-03-13T09:00:00+00:00",
                }
            )
        )
        update_incident(
            incident["id"],
            {"workflow_status": "investigating", "assigned_to": "oncall-1"},
        )

    incident = record_incident_from_alert(
        create_alert(
            {
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "alert_type": "capacity_case_2",
                "severity": "high",
                "message": "capacity case",
                "created_at": "2026-03-13T09:00:00+00:00",
            }
        )
    )
    update_incident(
        incident["id"],
        {"workflow_status": "investigating", "assigned_to": "oncall-2"},
    )

    assignee, reason = resolve_assignee(
        None,
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "timezone": "UTC",
            "incident_oncall_rotation": ["oncall-1", "oncall-2"],
            "incident_rotation_interval_hours": 1,
            "incident_assignees": {
                "oncall-1": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 1.0,
                    "max_active_incidents": 4,
                },
                "oncall-2": {
                    "availability": {"days": ["fri"], "start_hour": 0, "end_hour": 24},
                    "routing_weight": 1.0,
                    "max_active_incidents": 1,
                },
            },
        },
        now_iso="2026-03-13T01:00:00+00:00",
    )
    assert assignee == "oncall-1"
    assert reason == "rotation_primary"


def test_incident_reminders_reassign_after_threshold(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CALLLOCK_INCIDENT_ROOT", str(tmp_path))
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )
    incident = record_incident_from_alert(alert)
    update_incident(
        incident["id"],
        {
            "workflow_status": "investigating",
            "assigned_to": "oncall-1",
            "reminder_count": resolve_reassign_after_reminders({"incident_reassign_after_reminders": 2}) - 1,
            "last_reviewed_at": "2026-03-13T09:40:00+00:00",
        },
    )

    reminders = send_incident_reminders(
        tenant_id="00000000-0000-0000-0000-000000000002",
        now_iso="2026-03-13T18:00:00+00:00",
    )

    assert reminders
    assert reminders[0]["assigned_to"] == "oncall-2"
    assert reminders[0]["last_assignment_reason"] in {"fallback_from:oncall-1", "reminder_threshold"}
    assert reminders[0]["assignment_history"]

from __future__ import annotations

import re
import httpx
import pytest

from db import supabase_repository


def _http_error(message: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/rest/v1/rpc/mutate_incident_runbook_step")
    response = httpx.Response(400, request=request, json={"message": message})
    return httpx.HTTPStatusError(message, request=request, response=response)


def test_update_incident_runbook_progress_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "incident-1", "incident_revision": 4}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    result = supabase_repository.update_incident_runbook_progress(
        "incident-1",
        step_index=2,
        status="completed",
        actor_id="operator-1",
        note="Finished triage",
        expected_revision=3,
        expected_step_revision=5,
    )

    assert result["incident_revision"] == 4
    assert captured["function_name"] == "mutate_incident_runbook_step"
    assert captured["payload"] == {
        "p_incident_id": "incident-1",
        "p_step_index": 2,
        "p_actor_id": "operator-1",
        "p_operation": "progress",
        "p_status": "completed",
        "p_note": "Finished triage",
        "p_expected_revision": 3,
        "p_expected_step_revision": 5,
    }


def test_update_incident_runbook_assignment_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "incident-1", "incident_revision": 6}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    result = supabase_repository.update_incident_runbook_assignment(
        "incident-1",
        step_index=1,
        actor_id="operator-2",
        action="claim",
        assigned_to="oncall-1",
        claim_ttl_seconds=900,
        now_iso="2026-03-13T10:00:00+00:00",
        expected_revision=5,
        expected_step_revision=2,
    )

    assert result["incident_revision"] == 6
    assert captured["function_name"] == "mutate_incident_runbook_step"
    assert captured["payload"] == {
        "p_incident_id": "incident-1",
        "p_step_index": 1,
        "p_actor_id": "operator-2",
        "p_operation": "assignment",
        "p_action": "claim",
        "p_assigned_to": "oncall-1",
        "p_claim_ttl_seconds": 900,
        "p_expected_revision": 5,
        "p_expected_step_revision": 2,
        "p_now": "2026-03-13T10:00:00+00:00",
    }


def test_update_incident_runbook_assignment_translates_step_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        raise _http_error("CLLKRB_STEP_CONFLICT: expected 2, found 3")

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    with pytest.raises(ValueError, match="runbook step revision conflict: expected 2, found 3"):
        supabase_repository.update_incident_runbook_assignment(
            "incident-1",
            step_index=1,
            actor_id="operator-2",
            action="heartbeat",
            expected_revision=5,
            expected_step_revision=2,
        )


def test_update_incident_workflow_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "incident-2", "incident_revision": 8, "workflow_status": "investigating"}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    result = supabase_repository.update_incident_workflow(
        "incident-2",
        workflow_status="investigating",
        actor_id="operator-9",
        assigned_to="oncall-2",
        operator_notes="Triage started",
        last_assignment_reason="availability_fallback",
        assignment_history_entry={
            "at": "2026-03-13T10:00:00+00:00",
            "from": "oncall-1",
            "to": "oncall-2",
            "reason": "availability_fallback",
        },
        now_iso="2026-03-13T10:00:00+00:00",
        expected_revision=7,
    )

    assert result["incident_revision"] == 8
    assert captured["function_name"] == "mutate_incident_workflow"
    assert captured["payload"] == {
        "p_incident_id": "incident-2",
        "p_workflow_status": "investigating",
        "p_actor_id": "operator-9",
        "p_assigned_to": "oncall-2",
        "p_operator_notes": "Triage started",
        "p_last_assignment_reason": "availability_fallback",
        "p_assignment_history_entry": {
            "at": "2026-03-13T10:00:00+00:00",
            "from": "oncall-1",
            "to": "oncall-2",
            "reason": "availability_fallback",
        },
        "p_now": "2026-03-13T10:00:00+00:00",
        "p_expected_revision": 7,
    }


def test_update_incident_reminder_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "incident-3", "incident_revision": 9, "reminder_count": 2}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    result = supabase_repository.update_incident_reminder(
        "incident-3",
        actor_id="system:incident-reminder",
        reminder_count=2,
        last_reminded_at="2026-03-13T12:00:00+00:00",
        assigned_to="oncall-2",
        last_assignment_reason="reminder_threshold",
        assignment_history_entry={
            "at": "2026-03-13T12:00:00+00:00",
            "from": "oncall-1",
            "to": "oncall-2",
            "reason": "reminder_threshold",
        },
        expected_revision=8,
    )

    assert result["incident_revision"] == 9
    assert captured["function_name"] == "mutate_incident_reminder"
    assert captured["payload"] == {
        "p_incident_id": "incident-3",
        "p_actor_id": "system:incident-reminder",
        "p_reminder_count": 2,
        "p_last_reminded_at": "2026-03-13T12:00:00+00:00",
        "p_assigned_to": "oncall-2",
        "p_last_assignment_reason": "reminder_threshold",
        "p_assignment_history_entry": {
            "at": "2026-03-13T12:00:00+00:00",
            "from": "oncall-1",
            "to": "oncall-2",
            "reason": "reminder_threshold",
        },
        "p_expected_revision": 8,
    }


def test_sync_incident_from_alert_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "incident-4", "incident_revision": 2, "incident_key": "tenant:job_failure_spike"}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)

    result = supabase_repository.sync_incident_from_alert(
        {
            "incident_key": "tenant:job_failure_spike",
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_id": "00000000-0000-0000-0000-000000000099",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "alert_status": "open",
            "alert_created_at": "2026-03-13T09:00:00+00:00",
            "alert_last_observed_at": "2026-03-13T09:05:00+00:00",
            "alert_resolved_at": None,
            "alert_occurrence_count": 1,
            "incident_domain": "operations",
            "incident_category": "worker_reliability",
            "remediation_category": "manual_review",
            "incident_urgency": "high",
            "runbook_id": "worker_reliability",
            "runbook_title": "Worker Reliability",
            "runbook_steps": [{"step_id": "step-1", "title": "Review logs", "required": True, "depends_on": [], "parallel_group": None}],
            "completion_policy": {"required_workflow_statuses": ["closed"]},
            "approval_policy": {"required_workflow_statuses": ["closed"]},
            "initial_runbook_progress": [{"step_id": "step-1", "step_index": 1, "title": "Review logs", "required": True, "depends_on": [], "parallel_group": None, "step_revision": 1, "status": "pending", "assigned_to": None, "claimed_by": None, "claimed_at": None, "claim_expires_at": None, "completed_at": None, "completed_by": None, "notes": "", "blocked_by": [], "is_blocked": False}],
            "initial_runbook_progress_summary": {"total_steps": 1, "completed_steps": 0, "pending_steps": 1},
            "initial_runbook_execution_plan": {"next_runnable_steps": [{"step_index": 1, "title": "Review logs"}], "blocked_steps": [], "completed_steps": [], "parallel_groups": {}},
        }
    )

    assert result["incident_revision"] == 2
    assert captured["function_name"] == "sync_incident_from_alert"
    assert captured["payload"]["p_incident_key"] == "tenant:job_failure_spike"
    assert captured["payload"]["p_incident_category"] == "worker_reliability"
    assert captured["payload"]["p_initial_runbook_progress_summary"] == {"total_steps": 1, "completed_steps": 0, "pending_steps": 1}


def test_update_alert_and_sync_incident_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch_first(table: str, params: dict[str, str]) -> dict[str, object]:
        assert table == "alerts"
        assert params == {"id": "eq.alert-1"}
        return {
            "id": "alert-1",
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "status": "open",
            "created_at": "2026-03-13T09:00:00+00:00",
            "occurrence_count": 1,
        }

    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": "alert-1", "status": "resolved"}]

    monkeypatch.setattr(supabase_repository, "_fetch_first", fake_fetch_first)
    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)
    monkeypatch.setattr(
        supabase_repository,
        "get_tenant_config",
        lambda tenant_id: {"tenant_id": tenant_id, "incident_runbooks": {}, "incident_classification_rules": []},
    )

    result = supabase_repository.update_alert_and_sync_incident(
        "alert-1",
        {
            "status": "resolved",
            "resolved_at": "2026-03-13T09:15:00+00:00",
            "resolved_by": "operator-1",
            "resolution_notes": "Resolved",
        },
    )

    assert result["status"] == "resolved"
    assert captured["function_name"] == "mutate_alert_and_sync_incident"
    assert captured["payload"]["p_alert_id"] == "alert-1"
    assert captured["payload"]["p_updates"]["status"] == "resolved"
    assert captured["payload"]["p_incident_sync"]["incident_key"] == "00000000-0000-0000-0000-000000000002:job_failure_spike"
    assert captured["payload"]["p_incident_sync"]["alert_status"] == "resolved"


def test_create_alert_and_sync_incident_uses_atomic_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_rpc(function_name: str, payload: dict[str, object]) -> list[dict[str, object]]:
        captured["function_name"] = function_name
        captured["payload"] = payload
        return [{"id": payload["p_alert"]["id"], "status": "open"}]

    monkeypatch.setattr(supabase_repository, "_rpc", fake_rpc)
    monkeypatch.setattr(
        supabase_repository,
        "get_tenant_config",
        lambda tenant_id: {"tenant_id": tenant_id, "incident_runbooks": {}, "incident_classification_rules": []},
    )

    result = supabase_repository.create_alert_and_sync_incident(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job failure spike",
            "metrics": {"job_failure_spike": 5},
            "occurrence_count": 1,
            "last_observed_at": "2026-03-13T09:00:00+00:00",
            "created_at": "2026-03-13T09:00:00+00:00",
        }
    )

    assert result["status"] == "open"
    assert captured["function_name"] == "create_alert_and_sync_incident"
    assert re.fullmatch(r"[0-9a-f-]{36}", captured["payload"]["p_alert"]["id"])
    assert captured["payload"]["p_incident_sync"]["incident_key"] == "00000000-0000-0000-0000-000000000002:job_failure_spike"
    assert captured["payload"]["p_incident_sync"]["alert_status"] == "open"

from db.repository import create_alert, create_job
from fastapi.testclient import TestClient

from harness.server import app
import harness.server as server


def test_process_call_endpoint_executes_customer_analyst() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-1",
            "tenant_id": "tenant-alpha",
            "problem_description": "No heat and customer is upset.",
            "transcript": "Customer says there is no heat tonight and they are frustrated.",
            "tenant_config": {"allowed_tools": ["notify_dispatch"]},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow", "reason": "default"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_verdict"] == "allow"
    assert payload["verification_passed"] is True
    assert payload["verification_verdict"] == "pass"
    assert payload["output"]["lead_route"] == "dispatcher"


def test_process_call_endpoint_uses_local_seed_defaults() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-2",
            "tenant_id": "tenant-alpha",
            "problem_description": "AC not cooling",
            "transcript": "Customer says the AC is not cooling.",
        },
    )
    assert response.status_code == 200
    assert response.json()["policy_verdict"] == "allow"


def test_event_endpoint_accepts_inngest_style_envelope() -> None:
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-3",
                "tenant_id": "tenant-alpha",
                "problem_description": "No heat",
                "transcript": "Customer says there is no heat.",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["verification_passed"] is True


def test_event_endpoint_rejects_unknown_event_name() -> None:
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "unknown/event",
            "data": {
                "call_id": "call-4",
                "tenant_id": "tenant-alpha",
                "problem_description": "No heat",
            },
        },
    )
    assert response.status_code == 422


def test_event_endpoint_requires_secret_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-5",
                "tenant_id": "tenant-alpha",
                "problem_description": "No heat",
            },
        },
    )
    assert response.status_code == 401

    authorized = client.post(
        "/events/process-call",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-6",
                "tenant_id": "tenant-alpha",
                "problem_description": "No heat",
            },
        },
    )
    assert authorized.status_code == 200


def test_health_reports_litellm_configured_with_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    monkeypatch.setattr(server, "build_cache_client", lambda: type("Cache", (), {"ping": lambda self: True})())
    monkeypatch.setattr(server, "_check_external_connectivity", lambda url, timeout=3.0: {"reachable": True, "status": 200})

    health = server.health_dependencies()

    assert health["litellm"]["configured"] is True


def test_onboarding_and_control_plane_endpoints() -> None:
    client = TestClient(app)
    onboard = client.post("/onboard-tenant", json={"slug": "tenant-gamma", "name": "Tenant Gamma"})
    assert onboard.status_code == 200

    kill_switch = client.post("/control/kill-switch", json={"scope": "tenant", "scope_id": "tenant-alpha", "reason": "pause"})
    assert kill_switch.status_code == 200

    switches = client.get("/control/kill-switches")
    assert switches.status_code == 200
    assert len(switches.json()) >= 1


def test_alert_lifecycle_endpoints() -> None:
    create_job(
        {
            "tenant_id": "tenant-alpha",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "alert-run-1",
            "job_type": "harness_run",
            "status": "failed",
            "idempotency_key": "alert-job-1",
            "result": {"policy_verdict": "deny", "verification": {"passed": False}},
        }
    )

    client = TestClient(app)
    evaluated = client.post("/alerts/evaluate", json={"tenant_id": "tenant-alpha"})
    assert evaluated.status_code == 200
    alert_id = evaluated.json()[0]["id"]

    acknowledged = client.post(
        f"/alerts/{alert_id}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_by"] == "operator-1"

    filtered = client.get("/alerts", params={"tenant_id": "tenant-alpha", "status": "acknowledged"})
    assert filtered.status_code == 200
    assert any(alert["id"] == alert_id for alert in filtered.json())

    incidents = client.get("/incidents", params={"tenant_id": "tenant-alpha"})
    assert incidents.status_code == 200
    assert incidents.json()
    assert "current_episode" in incidents.json()[0]
    assert "incident_category" in incidents.json()[0]
    assert "incident_domain" in incidents.json()[0]

    workflow = client.post(
        f"/incidents/{incidents.json()[0]['id']}/workflow",
        headers={"x-actor-id": "operator-2"},
        json={"workflow_status": "investigating", "assigned_to": "oncall-1", "operator_notes": "Triage started"},
    )
    assert workflow.status_code == 200
    assert workflow.json()["workflow_status"] == "investigating"
    assert workflow.json()["assigned_to"] in {"oncall-1", "oncall-2"}
    assert workflow.json()["last_reviewed_by"] == "operator-2"
    assert workflow.json()["notification"]["delivered"] is True

    reminder = client.post(
        "/incidents/remind-stale",
        json={"tenant_id": "tenant-alpha", "now_iso": "2026-03-13T11:30:00+00:00"},
    )
    assert reminder.status_code == 200


def test_incident_workflow_can_require_approval_before_closing() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    assert incidents.status_code == 200
    incident = incidents.json()[0]
    assert incident["runbook_id"] == "rb-worker-reliability"

    blocked = client.post(
        f"/incidents/{incident['id']}/workflow",
        headers={"x-actor-id": "operator-2"},
        json={"workflow_status": "closed", "assigned_to": "oncall-1", "operator_notes": "Closing too early"},
    )
    assert blocked.status_code == 400
    assert "pending_steps" in blocked.json()["detail"]

    required_steps = [step for step in incident["runbook_progress"] if step["required"]]
    for step in required_steps:
        progressed = client.post(
            f"/incidents/{incident['id']}/runbook-progress",
            headers={"x-actor-id": "operator-2"},
            json={"step_index": step['step_index'], "status": "completed", "note": f"Completed step {step['step_index']}"},
        )
        assert progressed.status_code == 200

    requested = client.post(
        f"/incidents/{incident['id']}/workflow",
        headers={"x-actor-id": "operator-2"},
        json={"workflow_status": "closed", "assigned_to": "oncall-1", "operator_notes": "Closing after mitigation"},
    )
    assert requested.status_code == 200
    assert requested.json()["approval_required"] is True
    approval_id = requested.json()["approval_request"]["id"]

    approvals = client.get("/approvals", params={"tenant_id": "tenant-beta", "status": "pending"})
    assert approvals.status_code == 200
    assert any(approval["id"] == approval_id for approval in approvals.json())

    approved = client.post(
        f"/approvals/{approval_id}",
        headers={"x-actor-id": "operator-3"},
        json={"status": "approved", "resolution_notes": "Approved closure"},
    )
    assert approved.status_code == 200
    assert approved.json()["continuation"]["mode"] == "incident_workflow_resume"
    assert approved.json()["continuation"]["incident"]["workflow_status"] == "closed"


def test_incident_runbook_progress_endpoint_updates_step_state() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]
    assert incident["runbook_progress_summary"]["completed_steps"] == 0

    response = client.post(
        f"/incidents/{incident['id']}/runbook-progress",
        headers={"x-actor-id": "operator-2"},
        json={"step_index": 1, "status": "completed", "note": "Validated worker failures"},
    )
    assert response.status_code == 200
    assert response.json()["runbook_progress_summary"]["completed_steps"] == 1
    assert response.json()["runbook_progress"][0]["status"] == "completed"
    assert response.json()["runbook_progress"][0]["completed_by"] == "operator-2"
    assert response.json()["runbook_execution_plan"]["next_runnable_steps"][0]["step_index"] == 2


def test_incident_runbook_progress_endpoint_rejects_dependency_blocked_step() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]

    response = client.post(
        f"/incidents/{incident['id']}/runbook-progress",
        headers={"x-actor-id": "operator-2"},
        json={"step_index": 3, "status": "completed", "note": "Tried to skip dependencies"},
    )
    assert response.status_code == 400
    assert "blocked by dependencies" in response.json()["detail"]


def test_incident_runbook_plan_endpoint_returns_guidance_view() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]

    response = client.get(f"/incidents/{incident['id']}/runbook-plan")
    assert response.status_code == 200
    assert response.json()["runbook_execution_plan"]["next_runnable_steps"][0]["parallel_group"] == "triage"
    assert response.json()["runbook_execution_plan"]["blocked_steps"][0]["waiting_on_titles"]


def test_incident_runbook_assignment_endpoint_updates_owner_and_claim() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]

    assigned = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-2"},
        json={"step_index": 1, "action": "assign", "assigned_to": "oncall-1"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["runbook_progress"][0]["assigned_to"] == "oncall-1"

    claimed = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-2"},
        json={"step_index": 1, "action": "claim", "now_iso": "2026-03-13T10:00:00+00:00"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["runbook_progress"][0]["claimed_by"] == "operator-2"
    assert claimed.json()["runbook_progress"][0]["claim_expires_at"] == "2026-03-13T10:10:00+00:00"
    assert claimed.json()["runbook_execution_plan"]["next_runnable_steps"][0]["assigned_to"] == "oncall-1"
    assert claimed.json()["runbook_execution_plan"]["next_runnable_steps"][0]["claimed_by"] == "operator-2"


def test_incident_runbook_assignment_endpoint_rejects_active_claim_conflict() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]

    first_claim = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-1"},
        json={"step_index": 1, "action": "claim", "now_iso": "2026-03-13T10:00:00+00:00"},
    )
    assert first_claim.status_code == 200

    conflict = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-2"},
        json={"step_index": 1, "action": "claim", "now_iso": "2026-03-13T10:05:00+00:00"},
    )
    assert conflict.status_code == 400
    assert "already claimed" in conflict.json()["detail"]


def test_incident_runbook_assignment_endpoint_rejects_stale_revision() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]
    stale_revision = incident["incident_revision"]

    first = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-1"},
        json={
            "step_index": 1,
            "action": "claim",
            "expected_revision": stale_revision,
            "expected_step_revision": incident["runbook_progress"][0]["step_revision"],
            "now_iso": "2026-03-13T10:00:00+00:00",
        },
    )
    assert first.status_code == 200

    stale = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-1"},
        json={
            "step_index": 1,
            "action": "heartbeat",
            "expected_revision": stale_revision,
            "expected_step_revision": incident["runbook_progress"][0]["step_revision"],
            "now_iso": "2026-03-13T10:01:00+00:00",
        },
    )
    assert stale.status_code == 409
    assert "runbook step revision conflict" in stale.json()["detail"]


def test_incident_runbook_assignment_endpoint_allows_independent_step_update_with_stale_incident_revision() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]
    stale_incident_revision = incident["incident_revision"]
    step_two_revision = incident["runbook_progress"][1]["step_revision"]

    first = client.post(
        f"/incidents/{incident['id']}/runbook-progress",
        headers={"x-actor-id": "operator-1"},
        json={
            "step_index": 1,
            "status": "completed",
            "note": "Completed step 1",
            "expected_revision": stale_incident_revision,
            "expected_step_revision": incident["runbook_progress"][0]["step_revision"],
        },
    )
    assert first.status_code == 200

    second = client.post(
        f"/incidents/{incident['id']}/runbook-progress",
        headers={"x-actor-id": "operator-2"},
        json={
            "step_index": 2,
            "status": "completed",
            "note": "Completed step 2 with stale incident rev",
            "expected_revision": stale_incident_revision,
            "expected_step_revision": step_two_revision,
        },
    )
    assert second.status_code == 200
    assert second.json()["runbook_progress"][1]["status"] == "completed"


def test_incident_runbook_assignment_endpoint_heartbeat_extends_lease() -> None:
    alert = create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    client.post(
        f"/alerts/{alert['id']}/status",
        headers={"x-actor-id": "operator-1"},
        json={"status": "acknowledged", "resolution_notes": "Investigating"},
    )

    incidents = client.get("/incidents", params={"tenant_id": "tenant-beta"})
    incident = incidents.json()[0]

    claimed = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-1"},
        json={"step_index": 1, "action": "claim", "now_iso": "2026-03-13T10:00:00+00:00"},
    )
    assert claimed.status_code == 200

    heartbeat = client.post(
        f"/incidents/{incident['id']}/runbook-assignment",
        headers={"x-actor-id": "operator-1"},
        json={"step_index": 1, "action": "heartbeat", "claim_ttl_seconds": 300, "now_iso": "2026-03-13T10:04:00+00:00"},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["runbook_progress"][0]["claim_expires_at"] == "2026-03-13T10:09:00+00:00"


def test_alert_auto_escalation_endpoint() -> None:
    create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    response = client.post(
        "/alerts/escalate-stale",
        json={"tenant_id": "00000000-0000-0000-0000-000000000002", "now_iso": "2026-03-13T10:00:00+00:00"},
    )
    assert response.status_code == 200
    assert response.json()[0]["status"] == "escalated"


def test_alert_auto_recovery_endpoint() -> None:
    create_alert(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "alert_type": "job_failure_spike",
            "severity": "high",
            "message": "job_failure_spike threshold breached",
            "last_observed_at": "2026-03-13T09:50:00+00:00",
            "created_at": "2026-03-13T09:45:00+00:00",
        }
    )

    client = TestClient(app)
    response = client.post(
        "/alerts/resolve-recovered",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000002",
            "now_iso": "2026-03-13T10:00:00+00:00",
            "metrics": {"job_failure_spike": 0},
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["status"] == "resolved"


def test_jobs_artifacts_and_lifecycle_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_ARTIFACT_ROOT", str(tmp_path))
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-artifact",
            "tenant_id": "tenant-alpha",
            "problem_description": "No heat and customer is upset.",
            "transcript": "Customer says there is no heat tonight and they are frustrated.",
            "tenant_config": {"allowed_tools": ["notify_dispatch"], "tone_profile": {"formality": "direct", "banned_words": []}},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow", "reason": "default"}],
        },
    )
    assert response.status_code == 200

    jobs = client.get("/jobs", params={"tenant_id": "tenant-alpha"})
    assert jobs.status_code == 200
    assert len(jobs.json()) >= 1

    artifacts = client.get("/artifacts", params={"tenant_id": "tenant-alpha"})
    assert artifacts.status_code == 200
    artifact = artifacts.json()[0]

    transition = client.post(
        f"/artifacts/{artifact['id']}/lifecycle",
        json={"tenant_id": "tenant-alpha", "target_state": "active"},
    )
    assert transition.status_code == 200
    assert transition.json()["lifecycle_state"] == "active"


def test_job_complete_event_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    process_response = client.post(
        "/process-call",
        json={
            "call_id": "call-job-complete",
            "tenant_id": "tenant-alpha",
            "problem_description": "No heat",
            "transcript": "Customer says there is no heat.",
            "tenant_config": {"allowed_tools": ["notify_dispatch"], "tone_profile": {"formality": "direct", "banned_words": []}},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow"}],
            "job_requests": [{"idempotency_key": "async-1", "job_type": "follow_up"}],
        },
    )
    assert process_response.status_code == 200

    jobs = client.get("/jobs", params={"tenant_id": "tenant-alpha"}).json()
    async_job = next(job for job in jobs if job["idempotency_key"] == "async-1")
    completion = client.post(
        "/events/job-complete",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "name": "harness/job-complete",
            "data": {
                "job_id": async_job["id"],
                "tenant_id": "tenant-alpha",
                "status": "completed",
                "result": {"ok": True},
            },
        },
    )
    assert completion.status_code == 200
    assert completion.json()["status"] == "completed"


def test_process_call_requires_transcript_or_problem_description() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-invalid",
            "tenant_id": "tenant-alpha",
        },
    )
    assert response.status_code == 422


def test_improvement_content_and_cockpit_endpoints() -> None:
    client = TestClient(app)
    experiment = client.post(
        "/improvement/run-experiment",
        json={
            "mutation_surface": "prompt:customer-analyst",
            "proposal": "tighten routing prompt",
            "baseline_score": 0.7,
            "candidate_score": 0.8,
        },
    )
    assert experiment.status_code == 200
    assert experiment.json()["outcome"] == "keep"

    content = client.post(
        "/content/process",
        json={
            "tenant_id": "tenant-alpha",
            "call_id": "call-content",
            "transcript": "Call me at 313-555-1212",
            "consent_granted": True,
        },
    )
    assert content.status_code == 200
    assert "[REDACTED_PHONE]" in content.json()["sanitized_transcript"]

    cockpit = client.get("/cockpit/overview")
    assert cockpit.status_code == 200
    assert "portfolio_kpis" in cockpit.json()
    assert "recovery_entry_count" in cockpit.json()["portfolio_kpis"]

    scheduler = client.get("/cockpit/scheduler", params={"now_iso": "2026-01-15T08:21:00+00:00"})
    assert scheduler.status_code == 200
    assert "counts" in scheduler.json()
    assert "oldest_pending" in scheduler.json()


def test_eval_endpoints() -> None:
    client = TestClient(app)
    run = client.post("/evals/run", json={"level": "core"})
    assert run.status_code == 200
    assert run.json()["level"] == "core"

    listed = client.get("/evals/results", params={"level": "core"})
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_recovery_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path))
    monkeypatch.setattr("harness.nodes.persist.persist_run_record", lambda record: (_ for _ in ()).throw(RuntimeError("supabase down")))
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-recovery",
            "tenant_id": "tenant-alpha",
            "problem_description": "No heat",
            "transcript": "Customer says there is no heat.",
            "tenant_config": {"allowed_tools": ["notify_dispatch"], "tone_profile": {"formality": "direct", "banned_words": []}},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow"}],
        },
    )
    assert response.status_code == 200

    entries = client.get("/recovery/entries", params={"entry_type": "persist-failure"})
    assert entries.status_code == 200
    assert len(entries.json()) >= 1

    replay = client.post("/recovery/replay", json={"entry_id": entries.json()[0]["id"]})
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True


def test_audit_log_endpoint() -> None:
    client = TestClient(app)
    onboard = client.post("/onboard-tenant", headers={"X-Actor-Id": "operator-7"}, json={"slug": "tenant-epsilon", "name": "Tenant Epsilon"})
    assert onboard.status_code == 200

    logs = client.get("/audit-logs")
    assert logs.status_code == 200
    assert len(logs.json()) >= 1

    filtered = client.get("/audit-logs", params={"action_type": "tenant.onboard.completed"})
    assert filtered.status_code == 200
    assert any(log["actor_id"] == "operator-7" for log in filtered.json())


def test_approval_endpoints() -> None:
    from db.repository import create_approval_request

    approval = create_approval_request(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-approval",
            "worker_id": "engineer",
            "status": "pending",
            "reason": "Schema change requires approval",
            "requested_by": "harness",
            "request_type": "verification",
            "payload": {
                "worker_output": {"code": "alter table jobs add column flag boolean"},
                "resume_state": {
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "run_id": "run-approval",
                    "worker_id": "engineer",
                    "task": {"worker_spec": {"approval_boundaries": ["schema changes"]}},
                    "policy_decision": {"verdict": "allow", "reasons": []},
                    "worker_output": {"code": "alter table jobs add column flag boolean"},
                    "verification": {"passed": False, "verdict": "escalate", "reasons": ["Schema change requires approval"]},
                    "jobs": [],
                },
            },
        }
    )
    client = TestClient(app)
    listed = client.get("/approvals", params={"tenant_id": "tenant-alpha", "status": "pending"})
    assert listed.status_code == 200
    assert any(item["id"] == approval["id"] for item in listed.json())

    decision = client.post(
        f"/approvals/{approval['id']}",
        headers={"X-Actor-Id": "operator-9"},
        json={"status": "approved", "resolution_notes": "Approved for staging only"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert decision.json()["continuation"]["mode"] == "verification_resume"


def test_policy_approval_endpoint_continues_work() -> None:
    from db.repository import create_approval_request

    approval = create_approval_request(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-policy-approval",
            "worker_id": "customer-analyst",
            "status": "pending",
            "reason": "No allow rule matched",
            "requested_by": "harness",
            "request_type": "policy",
            "payload": {
                "resume_state": {
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "run_id": "run-policy-approval",
                    "worker_id": "customer-analyst",
                    "task": {
                        "problem_description": "No heat",
                        "transcript": "Customer says there is no heat tonight.",
                        "worker_spec": {
                            "mission": "Analyze post-call outcomes.",
                            "tools_allowed": ["notify_dispatch"],
                            "outputs": ["lead routing decisions", "summary", "sentiment", "churn risk"],
                        },
                        "tenant_config": {
                            "allowed_tools": ["notify_dispatch"],
                            "tone_profile": {"formality": "direct", "banned_words": []},
                            "escalate_policy_violations": True,
                        },
                        "industry_pack": {"summary": "HVAC pack"},
                        "knowledge_nodes": [{"summary": "Emergency no-heat calls should route to dispatch."}],
                        "feature_flags": {"harness_enabled": True, "llm_workers_enabled": False},
                        "compliance_rules": [],
                    },
                    "policy_decision": {"verdict": "escalate", "reasons": ["No allow rule matched"]},
                    "worker_output": {"status": "blocked"},
                    "verification": {"passed": False, "verdict": "block", "reasons": ["Awaiting approval"]},
                    "jobs": [],
                }
            },
        }
    )
    client = TestClient(app)
    decision = client.post(
        f"/approvals/{approval['id']}",
        headers={"X-Actor-Id": "operator-10"},
        json={"status": "approved", "resolution_notes": "Approved to continue policy-blocked run"},
    )
    assert decision.status_code == 200
    assert decision.json()["continuation"]["mode"] == "policy_resume"
    assert decision.json()["continuation"]["state"]["worker_output"]["lead_route"] == "dispatcher"


def test_retention_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_TRACE_ROOT", str(tmp_path / "traces"))
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path / "recovery"))
    client = TestClient(app)
    response = client.post("/retention/run", headers={"X-Actor-Id": "operator-11"}, json={"dry_run": True})
    assert response.status_code == 200
    assert "tenants" in response.json()


def test_due_tenant_schedule_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        "/schedules/due-tenants",
        json={"job_type": "tenant_eval", "utc_iso": "2026-01-15T09:20:00+00:00", "max_tenants": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert {item["tenant_slug"] for item in payload} == {"tenant-alpha"}
    assert payload[0]["scheduled_minute"] == 15
    assert payload[0]["capacity_remaining"] >= 0
    assert payload[0]["scheduled_start_at"]

    backlog = client.get(
        "/schedules/backlog",
        params={"job_type": "tenant_eval", "status": "pending"},
    )
    assert backlog.status_code == 200
    assert any(item["tenant_slug"] == "tenant-alpha" for item in backlog.json())

    claimed = client.post(
        "/schedules/claim",
        json={
            "job_type": "tenant_eval",
            "utc_iso": "2026-01-15T09:20:00+00:00",
            "max_tenants": 1,
            "claimer_id": "scheduler-api-test",
            "claim_ttl_seconds": 120,
        },
    )
    assert claimed.status_code == 200
    assert claimed.json()[0]["status"] == "claimed"
    assert claimed.json()[0]["claimed_by"] == "scheduler-api-test"

    finalized = client.post(
        "/schedules/finalize",
        json={
            "entry_id": claimed.json()[0]["id"],
            "action": "complete",
            "actor_id": "scheduler-api-test",
            "utc_iso": "2026-01-15T09:25:00+00:00",
            "note": "complete via api test",
        },
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "completed"


def test_schedule_heartbeat_endpoint() -> None:
    client = TestClient(app)
    claimed = client.post(
        "/schedules/claim",
        json={
            "job_type": "retention",
            "utc_iso": "2026-01-15T08:20:00+00:00",
            "max_tenants": 1,
            "claimer_id": "scheduler-api-test",
            "claim_ttl_seconds": 30,
        },
    )
    assert claimed.status_code == 200

    heartbeat = client.post(
        "/schedules/heartbeat",
        json={
            "entry_id": claimed.json()[0]["id"],
            "actor_id": "scheduler-api-test",
            "utc_iso": "2026-01-15T08:20:20+00:00",
            "claim_ttl_seconds": 120,
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["claim_expires_at"] == "2026-01-15T08:22:20+00:00"


def test_schedule_sweep_endpoint() -> None:
    client = TestClient(app)
    claimed = client.post(
        "/schedules/claim",
        json={
            "job_type": "retention",
            "utc_iso": "2026-01-15T08:20:00+00:00",
            "max_tenants": 1,
            "claimer_id": "scheduler-api-test",
            "claim_ttl_seconds": 30,
        },
    )
    assert claimed.status_code == 200

    sweep = client.post(
        "/schedules/sweep",
        json={"utc_iso": "2026-01-15T08:21:00+00:00", "dry_run": False},
    )
    assert sweep.status_code == 200
    assert sweep.json()["released_count"] == 1
    assert sweep.json()["released"][0]["id"] == claimed.json()[0]["id"]


def test_schedule_override_endpoint() -> None:
    client = TestClient(app)
    claimed = client.post(
        "/schedules/claim",
        json={
            "job_type": "retention",
            "utc_iso": "2026-01-15T08:20:00+00:00",
            "max_tenants": 1,
            "claimer_id": "scheduler-api-test",
            "claim_ttl_seconds": 120,
        },
    )
    assert claimed.status_code == 200

    released = client.post(
        "/schedules/override",
        json={
            "entry_id": claimed.json()[0]["id"],
            "action": "force_release",
            "actor_id": "operator-override",
            "note": "manual intervention",
        },
    )
    assert released.status_code == 200
    assert released.json()["status"] == "pending"

    reclaimed = client.post(
        "/schedules/override",
        json={
            "entry_id": claimed.json()[0]["id"],
            "action": "force_claim",
            "actor_id": "operator-override",
            "new_claimer_id": "operator-handoff",
            "utc_iso": "2026-01-15T08:20:10+00:00",
            "claim_ttl_seconds": 90,
            "note": "take over",
        },
    )
    assert reclaimed.status_code == 200
    assert reclaimed.json()["status"] == "claimed"
    assert reclaimed.json()["claimed_by"] == "operator-handoff"

    scheduler = client.get("/cockpit/scheduler", params={"now_iso": "2026-01-15T08:20:15+00:00"})
    assert scheduler.status_code == 200
    assert scheduler.json()["counts"]["claimed"] >= 1

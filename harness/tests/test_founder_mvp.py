from __future__ import annotations

from db.repository import (
    create_alert_and_sync_incident,
    create_approval_request,
    create_artifact,
    create_job,
    upsert_agent_report,
)
from harness.founder_mvp import (
    build_founder_approvals,
    build_founder_blocked_work,
    build_founder_home,
    build_voice_truth_summary,
    load_active_priority,
)


def test_voice_truth_summary_prefers_truth_artifact_over_agent_report() -> None:
    create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-voice-truth",
            "created_by": "voice-truth",
            "artifact_type": "voice_truth_eval",
            "payload": {
                "state": "block",
                "top_reason": "customer_phone_exact regressed",
                "failed_metric_count": 2,
                "baseline_version": "prod-v1",
                "candidate_version": "candidate-v2",
            },
            "lineage": {"worker_id": "voice-truth"},
        }
    )
    upsert_agent_report(
        {
            "agent_id": "voice-truth",
            "report_type": "voice-eval",
            "report_date": "2026-03-24",
            "status": "green",
            "payload": {"summary": "stale advisory report"},
            "tenant_id": "tenant-alpha",
        }
    )

    summary = build_voice_truth_summary(tenant_id="tenant-alpha")

    assert summary["state"] == "block"
    assert summary["top_reason"] == "customer_phone_exact regressed"
    assert summary["failed_metric_count"] == 2
    assert summary["baseline_version"] == "prod-v1"
    assert summary["candidate_version"] == "candidate-v2"
    assert len(summary["artifact_refs"]) == 1


def test_founder_home_contains_contract_fields_not_just_keys() -> None:
    create_alert_and_sync_incident(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_route_missing_spike",
            "severity": "high",
            "message": "Route missing spike",
            "metrics": {"detection": {"notification_outcome": "founder_notify"}},
        }
    )
    approval = create_approval_request(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-approval",
            "worker_id": "voice-builder",
            "status": "pending",
            "reason": "Truth escalation requires review",
            "requested_by": "harness",
            "request_type": "verification",
            "payload": {"verification": {"verdict": "escalate", "reasons": ["Boundary call"]}},
        }
    )

    payload = build_founder_home(tenant_id="tenant-alpha")

    assert payload["briefing"]["generated_at"]
    assert payload["briefing"]["top_pending_approval"]["id"] == approval["id"]
    assert payload["briefing"]["top_pending_approval"]["reason"] == "Truth escalation requires review"
    assert payload["briefing"]["top_issue_thread"]["alert_type"] == "voice_route_missing_spike"
    assert payload["briefing"]["recommended_action"] is not None
    assert payload["voice_truth"]["state"] in {"pass", "block", "escalate", "not_active"}
    assert payload["issue_posture"]["counts"]["founder_visible_threads"] == 1
    assert payload["active_priority"]["source"] == "AGENT.md"


def test_load_active_priority_returns_null_projection_when_agent_file_has_no_priority(tmp_path) -> None:
    agent_path = tmp_path / "AGENT.md"
    agent_path.write_text("# Instructions\n\nNo explicit active priority here.\n")

    priority = load_active_priority(path=agent_path)

    assert priority["label"] is None
    assert priority["constraints"] == []
    assert priority["source"] == "AGENT.md"


def test_founder_approvals_uses_real_approval_requests_only() -> None:
    create_approval_request(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-approval",
            "worker_id": "voice-builder",
            "status": "pending",
            "reason": "Truth escalation requires review",
            "requested_by": "harness",
            "request_type": "verification",
            "payload": {"verification": {"verdict": "escalate", "reasons": ["Boundary call"]}},
        }
    )

    approvals = build_founder_approvals(tenant_id="tenant-alpha")

    assert approvals["items"][0]["source"] == "approval_requests"
    assert approvals["items"][0]["reason"] == "Truth escalation requires review"
    assert approvals["items"][0]["requested_action"] in {"approve", "deny", "defer"}


def test_blocked_work_derives_reason_next_step_and_artifacts_from_jobs() -> None:
    job = create_job(
        {
            "tenant_id": "tenant-alpha",
            "origin_worker_id": "voice-builder",
            "origin_run_id": "run-blocked",
            "job_type": "voice-change",
            "status": "failed",
            "idempotency_key": "voice-builder:run-blocked",
            "payload": {"target_worker_id": "voice-builder"},
            "result": {
                "status": "block",
                "verification": {"passed": False, "verdict": "block", "reasons": ["route_no_regression failed"]},
            },
            "created_by": "harness",
        }
    )
    create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-blocked",
            "created_by": "voice-truth",
            "artifact_type": "run_record",
            "source_job_id": job["id"],
            "payload": {"summary": "blocked run artifact"},
            "lineage": {"worker_id": "voice-truth"},
        }
    )

    blocked = build_founder_blocked_work(tenant_id="tenant-alpha")
    item = blocked["items"][0]

    assert item["blocked_reason"] == "route_no_regression failed"
    assert item["recommended_next_step"] == "Revise candidate and rerun truth gate"
    assert len(item["artifact_refs"]) == 1

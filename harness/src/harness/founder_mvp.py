from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from db.repository import (
    list_agent_reports,
    list_alerts,
    list_approval_requests,
    list_artifacts,
    list_incidents,
    list_jobs,
)

try:
    from harness.detection.posture import build_detection_posture
except ModuleNotFoundError:
    def build_detection_posture(*, tenant_id: str | None = None) -> dict[str, Any]:
        alerts = {
            alert.get("id"): alert
            for alert in list_alerts(tenant_id=tenant_id, status="open")
        }
        incidents = [
            incident
            for incident in list_incidents(tenant_id=tenant_id, status="open")
            if incident.get("workflow_status") != "closed"
        ]

        active_threads = []
        for incident in incidents:
            alert = alerts.get(incident.get("current_alert_id"))
            notification_outcome = (
                alert.get("metrics", {})
                .get("detection", {})
                .get("notification_outcome")
                if isinstance(alert, dict)
                else None
            ) or "internal_only"
            active_threads.append(
                {
                    "incident_id": incident.get("id"),
                    "incident_key": incident.get("incident_key"),
                    "workflow_status": incident.get("workflow_status"),
                    "severity": incident.get("severity"),
                    "current_alert_id": incident.get("current_alert_id"),
                    "alert_type": incident.get("alert_type"),
                    "incident_domain": incident.get("incident_domain"),
                    "incident_category": incident.get("incident_category"),
                    "notification_outcome": notification_outcome,
                }
            )

        return {
            "counts": {
                "open_threads": len(active_threads),
                "founder_visible_threads": sum(
                    1
                    for thread in active_threads
                    if thread.get("notification_outcome") == "founder_notify"
                ),
            },
            "active_threads": active_threads,
        }

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_MD_PATH = REPO_ROOT / "AGENT.md"
VOICE_TRUTH_STATES = {"pass", "block", "escalate", "not_active"}
VOICE_TRUTH_ARTIFACT_PREFIXES = ("voice_truth",)


def build_founder_home(*, tenant_id: str | None = None) -> dict[str, Any]:
    return {
        "briefing": build_founder_briefing(tenant_id=tenant_id),
        "voice_truth": build_voice_truth_summary(tenant_id=tenant_id),
        "issue_posture": build_detection_posture(tenant_id=tenant_id),
        "active_priority": load_active_priority(),
    }


def build_founder_briefing(*, tenant_id: str | None = None) -> dict[str, Any]:
    approvals = build_founder_approvals(tenant_id=tenant_id)["items"]
    blocked_work = build_founder_blocked_work(tenant_id=tenant_id)["items"]
    issue_posture = build_detection_posture(tenant_id=tenant_id)
    voice_truth = build_voice_truth_summary(tenant_id=tenant_id)
    active_priority = load_active_priority()

    top_pending_approval = approvals[0] if approvals else None
    top_issue_thread = _select_top_issue_thread(issue_posture.get("active_threads", []))
    top_blocked_work = blocked_work[0] if blocked_work else None
    top_regression = voice_truth if voice_truth.get("state") in {"block", "escalate"} else None
    top_change_kind, top_change = _select_briefing_focus(
        top_pending_approval=top_pending_approval,
        top_regression=top_regression,
        top_blocked_work=top_blocked_work,
        top_issue_thread=top_issue_thread,
    )
    recommended_action = _briefing_recommended_action(top_change_kind, top_change)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_change": top_change,
        "top_regression": top_regression,
        "top_issue_thread": top_issue_thread,
        "top_blocked_work": top_blocked_work,
        "top_pending_approval": top_pending_approval,
        "recommended_action": recommended_action,
        "active_priority": active_priority,
    }


def build_voice_truth_summary(*, tenant_id: str | None = None) -> dict[str, Any]:
    artifacts = [
        artifact
        for artifact in list_artifacts(tenant_id)
        if _is_voice_truth_artifact(artifact)
    ]
    if artifacts:
        artifact = _latest_by_timestamp(artifacts)
        payload = artifact.get("payload", {})
        return {
            "state": _coerce_truth_state(payload.get("state")),
            "top_reason": payload.get("top_reason") or "Voice truth artifact recorded without summary reason",
            "last_evaluated_at": artifact.get("created_at"),
            "failed_metric_count": payload.get("failed_metric_count", 0),
            "baseline_version": payload.get("baseline_version"),
            "candidate_version": payload.get("candidate_version"),
            "artifact_refs": [_artifact_ref(artifact)],
        }

    reports = [
        report
        for report in list_agent_reports(tenant_id=tenant_id)
        if _is_voice_related_report(report)
    ]
    if reports:
        report = _latest_by_report_date(reports)
        payload = report.get("payload", {})
        return {
            "state": _state_from_report_status(report.get("status")),
            "top_reason": payload.get("summary") or payload.get("top_reason") or "Voice truth reported without summary detail",
            "last_evaluated_at": report.get("created_at") or report.get("report_date"),
            "failed_metric_count": payload.get("failed_metric_count", 0),
            "baseline_version": payload.get("baseline_version"),
            "candidate_version": payload.get("candidate_version"),
            "artifact_refs": [],
        }

    return {
        "state": "not_active",
        "top_reason": "Voice truth has no persisted evaluation yet",
        "last_evaluated_at": None,
        "failed_metric_count": 0,
        "baseline_version": None,
        "candidate_version": None,
        "artifact_refs": [],
    }


def build_founder_approvals(*, tenant_id: str | None = None) -> dict[str, Any]:
    requests = list_approval_requests(tenant_id=tenant_id, status="pending")
    items = [_approval_item(request) for request in sorted(requests, key=lambda request: request.get("created_at", ""), reverse=True)]
    return {"items": items}


def build_founder_blocked_work(*, tenant_id: str | None = None) -> dict[str, Any]:
    jobs = list_jobs(tenant_id=tenant_id)
    approvals = list_approval_requests(tenant_id=tenant_id, status="pending")
    items = []
    for job in sorted(jobs, key=lambda candidate: candidate.get("updated_at", candidate.get("created_at", "")), reverse=True):
        verdict = _job_exception_state(job)
        if verdict is None:
            continue
        items.append(_blocked_work_item(job, verdict=verdict, approvals=approvals))
    return {"items": items}


def load_active_priority(*, path: Path | None = None) -> dict[str, Any]:
    target = path or AGENT_MD_PATH
    if not target.exists():
        return {"label": None, "constraints": [], "source": target.name}

    content = target.read_text()
    section_match = re.search(
        r"^## Active Priority\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if section_match:
        lines = [line.strip() for line in section_match.group("body").splitlines() if line.strip()]
        if lines:
            label = _strip_list_prefix(lines[0])
            constraints = [_strip_list_prefix(line) for line in lines[1:]]
            return {"label": label or None, "constraints": constraints, "source": target.name}

    for line in content.splitlines():
        if line.startswith("Active Priority:"):
            label = line.split(":", 1)[1].strip()
            return {"label": label or None, "constraints": [], "source": target.name}

    return {"label": None, "constraints": [], "source": target.name}


def _approval_item(request: dict[str, Any]) -> dict[str, Any]:
    payload = request.get("payload", {})
    verification = payload.get("verification", {})
    verdict = verification.get("verdict")
    reason = request.get("reason", "")
    return {
        "id": request.get("id"),
        "title": f"{request.get('worker_id') or 'worker'} approval",
        "affected_surface": _surface_from_worker(request.get("worker_id")),
        "risk_level": "high" if verdict == "escalate" else "medium",
        "reason": reason,
        "requested_action": "approve",
        "age": _age_string(request.get("created_at")),
        "evidence_summary": "; ".join(verification.get("reasons", [])) or reason,
        "recommended_action": "Review approval request",
        "source": "approval_requests",
        "run_id": request.get("run_id"),
    }


def _blocked_work_item(job: dict[str, Any], *, verdict: str, approvals: list[dict[str, Any]]) -> dict[str, Any]:
    run_id = job.get("origin_run_id")
    artifacts = list_artifacts(job["tenant_id"], run_id=run_id) if run_id else []
    sorted_artifacts = sorted(
        artifacts,
        key=lambda artifact: (
            0 if artifact.get("source_job_id") == job.get("id") else 1,
            str(artifact.get("created_at", "")),
        ),
    )
    return {
        "id": job.get("id"),
        "worker_id": job.get("payload", {}).get("target_worker_id") or job.get("origin_worker_id"),
        "task_type": job.get("job_type"),
        "state": verdict,
        "blocked_reason": _blocked_reason(job),
        "recommended_next_step": _recommended_next_step(job, verdict=verdict, approvals=approvals),
        "artifact_refs": [_artifact_ref(artifact) for artifact in sorted_artifacts],
    }


def _job_exception_state(job: dict[str, Any]) -> str | None:
    result = job.get("result", {})
    verification = result.get("verification", {})
    verdict = verification.get("verdict") or result.get("status")
    if verdict in {"block", "retry", "escalate"}:
        return verdict
    return None


def _blocked_reason(job: dict[str, Any]) -> str:
    result = job.get("result", {})
    verification = result.get("verification", {})
    reasons = verification.get("reasons", [])
    if reasons:
        return reasons[0]
    if result.get("status"):
        return str(result["status"])
    return "Blocked"


def _recommended_next_step(job: dict[str, Any], *, verdict: str, approvals: list[dict[str, Any]]) -> str | None:
    if verdict == "escalate" and any(
        approval.get("status") == "pending" and approval.get("run_id") == job.get("origin_run_id")
        for approval in approvals
    ):
        return "Review approval request"
    if verdict == "block":
        return "Revise candidate and rerun truth gate"
    if verdict == "retry":
        return "Retry after fixing verification findings"
    return None


def _select_top_issue_thread(threads: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not threads:
        return None
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        threads,
        key=lambda thread: (
            0 if thread.get("notification_outcome") == "founder_notify" else 1,
            severity_rank.get(str(thread.get("severity")), 9),
            str(thread.get("incident_id", "")),
        ),
    )[0]


def _select_briefing_focus(
    *,
    top_pending_approval: dict[str, Any] | None,
    top_regression: dict[str, Any] | None,
    top_blocked_work: dict[str, Any] | None,
    top_issue_thread: dict[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    priority_order = (
        ("pending_approval", top_pending_approval),
        ("regression", top_regression),
        ("blocked_work", top_blocked_work),
        ("issue_thread", top_issue_thread),
    )
    for kind, item in priority_order:
        if item is not None:
            return kind, item
    return "idle", None


def _briefing_recommended_action(top_change_kind: str, top_change: dict[str, Any] | None) -> str:
    if top_change_kind == "pending_approval":
        return "Review pending approval"
    if top_change_kind == "regression":
        return "Inspect latest voice truth regression"
    if top_change_kind == "blocked_work":
        return str(top_change.get("recommended_next_step") or "Review blocked work")
    if top_change_kind == "issue_thread":
        return "Review active issue thread"
    return "No urgent founder action"


def _is_voice_truth_artifact(artifact: dict[str, Any]) -> bool:
    artifact_type = str(artifact.get("artifact_type", ""))
    return artifact_type.startswith(VOICE_TRUTH_ARTIFACT_PREFIXES)


def _is_voice_related_report(report: dict[str, Any]) -> bool:
    agent_id = str(report.get("agent_id", ""))
    report_type = str(report.get("report_type", ""))
    return "voice" in agent_id or "voice" in report_type


def _state_from_report_status(status: Any) -> str:
    if status == "green":
        return "pass"
    if status == "yellow":
        return "escalate"
    if status == "red":
        return "block"
    return "not_active"


def _coerce_truth_state(value: Any) -> str:
    if value in VOICE_TRUTH_STATES:
        return str(value)
    return "not_active"


def _artifact_ref(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact.get("id"),
        "artifact_type": artifact.get("artifact_type"),
        "run_id": artifact.get("run_id"),
        "created_at": artifact.get("created_at"),
    }


def _latest_by_timestamp(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(records, key=lambda record: str(record.get("created_at", "")))


def _latest_by_report_date(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        records,
        key=lambda record: (
            str(record.get("report_date", "")),
            str(record.get("created_at", "")),
        ),
    )


def _age_string(created_at: Any) -> str:
    if not created_at:
        return "unknown"
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - created.astimezone(timezone.utc)
        minutes = max(int(delta.total_seconds() // 60), 0)
        return f"{minutes}m"
    except ValueError:
        return str(created_at)


def _surface_from_worker(worker_id: Any) -> str:
    worker = str(worker_id or "")
    if "voice" in worker:
        return "voice"
    if "app" in worker:
        return "app"
    if "growth" in worker:
        return "growth"
    return "operations"


def _strip_list_prefix(line: str) -> str:
    return re.sub(r"^[-*]\s+", "", line).strip()

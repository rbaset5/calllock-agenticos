"""CEO Agent MCP tools.

10 tools giving the founder full control over the AgentOS.
Each wraps existing repository/harness calls with a clean interface.
Designed to be exposed as MCP tools to the CEO agent's Hermes instance.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from db import repository


def _queue_ceo_job(
    *,
    tenant_id: str,
    worker_id: str,
    task_type: str,
    problem_description: str,
    feature_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = f"ceo-{uuid4()}"
    return repository.create_job(
        {
            "tenant_id": tenant_id,
            "origin_worker_id": "ceo-agent",
            "origin_run_id": run_id,
            "job_type": task_type,
            "status": "queued",
            "idempotency_key": f"{worker_id}:{task_type}:{run_id}",
            "payload": {
                "target_worker_id": worker_id,
                "problem_description": problem_description,
                "feature_flags": feature_flags or {},
                "source": "ceo_agent",
            },
            "created_by": "ceo-agent",
        }
    )


def dispatch_worker(
    *,
    worker_id: str,
    tenant_id: str,
    task_type: str,
    problem_description: str = "",
    feature_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a task to any worker in the agent roster."""
    job = _queue_ceo_job(
        tenant_id=tenant_id,
        worker_id=worker_id,
        task_type=task_type,
        problem_description=problem_description,
        feature_flags=feature_flags,
    )
    return {"job_id": job.get("id"), "status": "dispatched", "worker_id": worker_id}


def check_quest_log(
    *,
    tenant_id: str | None = None,
    status: str = "pending",
) -> list[dict[str, Any]]:
    """Read pending approval requests."""
    return repository.list_approval_requests(tenant_id=tenant_id, status=status)


def approve_quest(
    *,
    approval_id: str,
    approved_by: str = "founder",
) -> dict[str, Any]:
    """Approve a blocked dispatch or quest."""
    return repository.update_approval_request(
        approval_id,
        {
            "status": "approved",
            "approved_by": approved_by,
        },
    )


def promote_skill(
    *,
    candidate_id: str,
    skill_title: str,
    skill_body: str,
    universal: bool = True,
    promoted_by: str = "founder",
) -> dict[str, Any]:
    """Extract and save a skill from a completed run."""
    from harness.skill_promotion import promote_skill as _promote

    candidates = repository.list_skill_candidates(status="pending")
    candidate = next((candidate for candidate in candidates if candidate.get("id") == candidate_id), None)
    if not candidate:
        return {"error": f"Candidate {candidate_id} not found or not pending"}
    result = _promote(
        candidate=candidate,
        skill_title=skill_title,
        skill_body=skill_body,
        promoted_by=promoted_by,
        universal=universal,
    )
    return {"status": "promoted", "path": result["path"]}


def dismiss_skill_candidate(
    *,
    candidate_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Mark a skill candidate as reviewed and dismissed."""
    from harness.skill_promotion import dismiss_skill_candidate as _dismiss

    return _dismiss(candidate_id, reason=reason)


def read_daily_memo(*, tenant_id: str) -> dict[str, Any]:
    """Get aggregated status across all agents."""
    skill_candidates = repository.list_skill_candidates(tenant_id=tenant_id) or []
    agent_reports_raw: list[dict[str, Any]] = []
    try:
        from db import supabase_repository

        request = getattr(supabase_repository, "_request", None)
        if callable(request):
            today = __import__("datetime").datetime.utcnow().date().isoformat()
            agent_reports_raw = request(
                "GET",
                "agent_reports",
                params={"tenant_id": f"eq.{tenant_id}", "report_date": f"eq.{today}"},
            )
    except Exception:
        pass
    return {
        "agent_reports": agent_reports_raw,
        "pending_skills": len([candidate for candidate in skill_candidates if candidate.get("status") == "pending"]),
        "pending_approvals": len(repository.list_approval_requests(tenant_id=tenant_id, status="pending")),
    }


def query_knowledge(*, path: str) -> dict[str, Any]:
    """Read from the knowledge graph."""
    from pathlib import Path

    knowledge_path = Path(__file__).resolve().parents[3] / "knowledge" / path
    if not knowledge_path.exists():
        return {"error": f"Knowledge node not found: {path}"}
    return {"path": path, "content": knowledge_path.read_text()[:4000]}


def check_agent_status(*, worker_id: str | None = None) -> list[dict[str, Any]]:
    """Check current state of agents (idle/active/queued)."""
    jobs = repository.list_jobs()
    normalized = [
        {
            "worker_id": job.get("payload", {}).get("target_worker_id") or job.get("origin_worker_id"),
            "status": job.get("status"),
            "task_type": job.get("job_type"),
        }
        for job in jobs
    ]
    if worker_id:
        normalized = [job for job in normalized if job.get("worker_id") == worker_id]
    return normalized[:20]


def read_audit_log(
    *,
    tenant_id: str | None = None,
    action_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read recent command audit log entries."""
    logs = repository.list_audit_logs(tenant_id=tenant_id, action_type=action_type)
    return logs[:limit]


def trigger_voice_eval(*, tenant_id: str) -> dict[str, Any]:
    """Kick off a voice pipeline evaluation run."""
    job = _queue_ceo_job(
        tenant_id=tenant_id,
        worker_id="eng-ai-voice",
        task_type="voice-eval",
        problem_description="CEO-triggered voice evaluation",
    )
    return {"job_id": job.get("id"), "status": "dispatched"}

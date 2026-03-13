from __future__ import annotations

from harness.graphs.workers.base import run_worker


def _deterministic_designer(task: dict) -> dict:
    idea = task.get("problem_description") or "Design requested workflow"
    return {
        "design_specs": f"Design a clear operator workflow for: {idea}",
        "content_patterns": ["Status-first summaries", "Escalation copy with explicit approvals"],
        "interaction_flows": ["Intake -> review -> approval", "Failure state -> cockpit escalation"],
    }


def run_designer(task: dict) -> dict:
    return run_worker(task, worker_id="designer", deterministic_builder=_deterministic_designer)

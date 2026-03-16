from __future__ import annotations

from harness.graphs.workers.base import run_worker


def _deterministic_engineer(task: dict) -> dict:
    idea = task.get("problem_description") or "Implement requested change"
    return {
        "code": f"Implement a bounded change for: {idea}",
        "tests": "Add unit coverage for the happy path, failure path, and tenant isolation behavior.",
        "migration_plans": "Avoid schema changes unless an approval boundary is explicitly cleared.",
    }


def run_engineer(task: dict) -> dict:
    return run_worker(task, worker_id="engineer", deterministic_builder=_deterministic_engineer)

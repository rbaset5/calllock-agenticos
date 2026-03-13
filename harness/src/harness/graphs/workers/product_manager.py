from __future__ import annotations

from harness.graphs.workers.base import run_worker


def _deterministic_product_manager(task: dict) -> dict:
    idea = task.get("problem_description") or "Review roadmap input"
    return {
        "plans": f"Plan the next increment for: {idea}",
        "prioritized_requirements": [
            "Define the user problem",
            "Sequence implementation behind safety checks",
            "Confirm rollout metrics and approval gates",
        ],
        "decision_memos": "Prefer the smallest scoped delivery that preserves tenant isolation and operational control.",
    }


def run_product_manager(task: dict) -> dict:
    return run_worker(task, worker_id="product-manager", deterministic_builder=_deterministic_product_manager)

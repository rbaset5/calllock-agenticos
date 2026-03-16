from __future__ import annotations

from harness.graphs.workers.base import run_worker


def _deterministic_product_marketer(task: dict) -> dict:
    idea = task.get("problem_description") or "Summarize product change"
    return {
        "messaging": f"Position the update around measurable operator value for: {idea}",
        "release_notes": "Describe the operational improvement, affected workflows, and rollout constraints.",
        "campaign_drafts": "Draft internal launch copy first, then hold public claims for approval.",
    }


def run_product_marketer(task: dict) -> dict:
    return run_worker(task, worker_id="product-marketer", deterministic_builder=_deterministic_product_marketer)

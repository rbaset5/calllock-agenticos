from __future__ import annotations

from db.repository import save_experiment
from harness.improvement.locks import lock_surface, unlock_surface


def run_experiment(payload: dict) -> dict:
    lock = lock_surface(payload["mutation_surface"], payload.get("ttl_seconds", 900))
    try:
        outcome = "keep" if payload["candidate_score"] >= payload["baseline_score"] else "discard"
        experiment = save_experiment(
            {
                "tenant_id": payload.get("tenant_id"),
                "mutation_surface": payload["mutation_surface"],
                "proposal": payload["proposal"],
                "baseline_score": payload["baseline_score"],
                "candidate_score": payload["candidate_score"],
                "outcome": outcome,
                "lock_id": lock["id"],
            }
        )
        return experiment
    finally:
        unlock_surface(payload["mutation_surface"])

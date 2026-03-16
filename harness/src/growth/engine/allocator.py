from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any


@dataclass
class AllocationResult:
    experiment_id: str
    chosen_arm_id: str
    scores: dict[str, float]
    mode: str


def allocate_experiment(experiment: dict[str, Any], *, seed: int | None = None) -> AllocationResult:
    arms = experiment.get("arms") or []
    experiment_id = str(experiment["experiment_id"])
    if not arms:
        raise ValueError("experiment has no arms")
    if len(arms) == 1:
        arm_id = str(arms[0]["arm_id"])
        return AllocationResult(experiment_id=experiment_id, chosen_arm_id=arm_id, scores={arm_id: 1.0}, mode="single_arm")

    rng = random.Random(seed if seed is not None else experiment_id)
    scores: dict[str, float] = {}
    for arm in arms:
        arm_id = str(arm["arm_id"])
        alpha = max(float(arm.get("alpha", 1)), 1)
        beta = max(float(arm.get("beta", 1)), 1)
        cost_weight = float(arm.get("cost_weight", 1)) or 1.0
        score = rng.betavariate(alpha, beta) / max(cost_weight, 0.0001)
        scores[arm_id] = score
    chosen_arm_id = max(scores, key=scores.get)
    return AllocationResult(experiment_id=experiment_id, chosen_arm_id=chosen_arm_id, scores=scores, mode="thompson_sampling")

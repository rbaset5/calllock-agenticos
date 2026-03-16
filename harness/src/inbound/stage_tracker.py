from __future__ import annotations

import logging

from inbound.types import StageTransition


logger = logging.getLogger(__name__)

VALID_STAGES = ["new", "qualified", "engaged", "negotiation", "won", "lost", "archived"]

TRANSITIONS: dict[str, list[str]] = {
    "new": ["qualified", "archived"],
    "qualified": ["engaged", "lost", "archived"],
    "engaged": ["negotiation", "lost", "archived"],
    "negotiation": ["won", "lost", "archived"],
    "won": [],
    "lost": ["new"],
    "archived": ["new"],
}


def is_valid_stage(stage: str) -> bool:
    return stage in VALID_STAGES


def is_valid_transition(from_stage: str, to_stage: str) -> bool:
    if not is_valid_stage(from_stage) or not is_valid_stage(to_stage):
        return False
    return to_stage in TRANSITIONS[from_stage]


def assign_initial_stage(action: str) -> str:
    if action in {"exceptional", "high"}:
        return "qualified"
    if action in {"medium", "low"}:
        return "new"
    if action in {"spam", "non-lead"}:
        return "archived"
    raise ValueError(f"Unknown action tier: {action}")


def detect_drift(current_stage: str, inferred_stage: str) -> bool:
    if current_stage == inferred_stage:
        return False
    return not is_valid_transition(current_stage, inferred_stage)


def transition_stage(current_stage: str, inferred_stage: str) -> StageTransition | None:
    if current_stage == inferred_stage:
        return None
    if not is_valid_transition(current_stage, inferred_stage):
        logger.info(
            "stage_drift",
            extra={"current_stage": current_stage, "inferred_stage": inferred_stage},
        )
        return None
    return StageTransition(
        from_stage=current_stage,
        to_stage=inferred_stage,
        changed_by="inbound_pipeline",
        reason="inferred stage transition",
    )

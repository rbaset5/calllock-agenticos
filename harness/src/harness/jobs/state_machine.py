from __future__ import annotations


VALID_JOB_STATUSES = {"queued", "running", "completed", "failed", "cancelled", "superseded"}
VALID_TRANSITIONS = {
    "queued": {"running", "cancelled", "superseded", "completed", "failed"},
    "running": {"completed", "failed", "cancelled", "superseded"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "superseded": set(),
}


def validate_transition(current: str, target: str) -> None:
    if target not in VALID_JOB_STATUSES:
        raise ValueError(f"Invalid job status: {target}")
    if current == target:
        return
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid job transition: {current} -> {target}")

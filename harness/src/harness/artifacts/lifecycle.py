from __future__ import annotations


VALID_TRANSITIONS = {
    "created": {"active"},
    "active": {"archived"},
    "archived": {"deleted"},
    "deleted": set(),
}


def validate_transition(current: str, target: str) -> None:
    if current == target:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid artifact lifecycle transition: {current} -> {target}")

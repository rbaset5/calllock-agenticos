"""Urgency inference helpers for post-call extraction."""

from __future__ import annotations

import re
from typing import Literal

LegacyUrgency = Literal["Emergency", "Urgent", "Routine", "Estimate"]


def infer_urgency_from_context(
    problem_description: str | None = None,
    transcript: str | None = None,
) -> LegacyUrgency | None:
    """Infer urgency from the available conversation context."""

    text = " ".join(part for part in (problem_description, transcript) if part).lower()
    if not text:
        return None

    if re.search(r"gas\s*leak|carbon\s*monoxide|smoke|fire|sparking|flood", text, re.I):
        return "Emergency"
    if re.search(r"water\s*leak|leak.*inside|puddle|no\s*(heat|cool|ac|air)|emergency|asap|today|right\s*away", text, re.I):
        return "Urgent"
    if re.search(r"estimate|quote|how\s*much|whenever|no\s*rush|flexible", text, re.I):
        return "Estimate"
    if re.search(r"maintenance|tune.?up|this\s*week", text, re.I):
        return "Routine"

    return "Routine"


__all__ = ["LegacyUrgency", "infer_urgency_from_context"]

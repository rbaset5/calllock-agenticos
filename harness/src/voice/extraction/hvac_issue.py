"""HVAC issue type inference helpers."""

from __future__ import annotations

import re
from typing import Literal

HVACIssueType = Literal[
    "Leaking",
    "No Cool",
    "No Heat",
    "Noisy System",
    "Odor",
    "Not Running",
    "Thermostat",
    "Maintenance",
]


def infer_hvac_issue_type(
    problem_description: str | None = None, transcript: str | None = None
) -> HVACIssueType | None:
    text = " ".join(part for part in (problem_description, transcript) if part).lower()
    if not text:
        return None

    if re.search(r"water\s*(leak|puddle|drip|pool)|leak.*unit|puddle.*inside|dripping", text, re.I):
        return "Leaking"
    if re.search(r"not?\s*cool|ac\s*(not|isn|won)|no\s*(cold|cool)|warm\s*air|won.t\s*cool", text, re.I):
        return "No Cool"
    if re.search(r"not?\s*heat|no\s*heat|furnace\s*(not|won|isn)|cold\s*air.*heat|won.t\s*heat", text, re.I):
        return "No Heat"
    if re.search(r"noise|loud|bang|rattle|squeal|grind|vibrat", text, re.I):
        return "Noisy System"
    if re.search(r"smell|odor|musty|mold", text, re.I):
        return "Odor"
    if re.search(r"won.t\s*(start|turn|run)|not\s*(start|turn|run)|dead|no\s*power", text, re.I):
        return "Not Running"
    if re.search(r"thermostat|temperature.*wrong|temp.*off", text, re.I):
        return "Thermostat"
    if re.search(r"maintenance|tune.?up|check.?up|seasonal|filter", text, re.I):
        return "Maintenance"
    return None


__all__ = ["HVACIssueType", "infer_hvac_issue_type"]

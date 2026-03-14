from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


class GrowthDuplicateError(Exception):
    """Raised when a growth write hits its natural-key uniqueness constraint."""


class InvalidAttributionTokenError(Exception):
    """Raised when an attribution token fails validation."""


@dataclass
class AttributionTokenPayload:
    version: int
    tenant_id: str
    prospect_id: str
    experiment_id: str | None
    arm_id: str | None
    issued_at: int
    key_id: str


@dataclass
class WedgeFitnessResult:
    wedge: str
    snapshot_week: date
    score: float
    component_scores: dict[str, Any] = field(default_factory=dict)
    gates_status: dict[str, bool] = field(default_factory=dict)
    blocking_gaps: list[str] = field(default_factory=list)
    launch_recommendation: str | None = None

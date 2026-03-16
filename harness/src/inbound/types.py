from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ParsedMessage:
    rfc_message_id: str
    thread_id: str
    imap_uid: int
    from_addr: str
    from_domain: str
    to_addr: str
    subject: str
    received_at: datetime
    body_html: str
    body_text: str


@dataclass(slots=True)
class QuarantineResult:
    status: str
    flags: list[str]
    reason: str | None
    sanitized_text: str


@dataclass(slots=True)
class ScoringResult:
    action: str
    total_score: int
    dimensions: dict[str, Any]
    bonuses: list[dict[str, Any]]
    disqualifier: str | None
    reasoning: str
    rubric_hash: str


@dataclass(slots=True)
class DraftResult:
    draft_text: str
    template_used: str
    source: str
    content_gate_status: str
    content_gate_flags: list[str]


@dataclass(slots=True)
class StageTransition:
    from_stage: str | None
    to_stage: str
    changed_by: str
    reason: str

"""Post-call transcript extraction utilities."""

from __future__ import annotations

import re
from typing import Literal, TypedDict

LegacyUrgency = Literal["Emergency", "Urgent", "Routine", "Estimate"]
DurationCategory = Literal["acute", "recent", "ongoing"]


class DurationResult(TypedDict):
    raw: str
    category: DurationCategory


_DURATION_PATTERNS: tuple[tuple[re.Pattern[str], int, DurationCategory], ...] = (
    (re.compile(r"\b(this morning|this afternoon|this evening|tonight|today)\b", re.I), 1, "acute"),
    (re.compile(r"\b(just started|just happened|just now|just began)\b", re.I), 1, "acute"),
    (re.compile(r"\b(an? (?:few |couple )?hours?(?: ago)?)\b", re.I), 1, "acute"),
    (re.compile(r"\b((?:about |like )?an? hour(?: ago)?)\b", re.I), 1, "acute"),
    (re.compile(r"\b(yesterday|last night)\b", re.I), 1, "recent"),
    (
        re.compile(r"\b(since (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b", re.I),
        1,
        "recent",
    ),
    (
        re.compile(r"\b((?:about |like )?(?:\d|a few|a couple|couple|several) days?(?: ago| now)?)\b", re.I),
        1,
        "recent",
    ),
    (re.compile(r"\b(this week|earlier this week)\b", re.I), 1, "recent"),
    (re.compile(r"\b((?:a |the )?(?:day|night) before yesterday)\b", re.I), 1, "recent"),
    (
        re.compile(r"\b((?:about |like )?(?:\d|a few|a couple|couple|several) weeks?(?: ago| now)?)\b", re.I),
        1,
        "ongoing",
    ),
    (
        re.compile(r"\b((?:about |like )?(?:\d|a few|a couple|couple|several) months?(?: ago| now)?)\b", re.I),
        1,
        "ongoing",
    ),
    (
        re.compile(r"\b((?:about |like )?(?:\d|a few|a couple|couple|several) years?(?: ago| now)?)\b", re.I),
        1,
        "ongoing",
    ),
    (re.compile(r"\b((?:for )?(?:a while|some time|a long time|ages|years))\b", re.I), 1, "ongoing"),
    (re.compile(r"\b((?:about |like )?a (?:month|year)(?: ago)?)\b", re.I), 1, "ongoing"),
    (re.compile(r"\b(last (?:week|month|year))\b", re.I), 1, "ongoing"),
)


def _user_utterances(transcript: str | None) -> str:
    if not transcript:
        return ""
    return " ".join(
        line.removeprefix("User:").strip()
        for line in transcript.splitlines()
        if line.startswith("User:")
    )


def extract_customer_name(transcript: str | None) -> str | None:
    user_lines = _user_utterances(transcript)
    if not user_lines:
        return None

    match = re.search(
        r"(?:my name is|this is|it's|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        user_lines,
        re.I,
    )
    return match.group(1) if match else None


def extract_safety_emergency(transcript: str | None) -> bool:
    if not transcript:
        return False
    text = transcript.lower()
    return bool(
        re.search(
            r"gas\s*leak|smell\s*gas|carbon\s*monoxide|co\s*detector|smoke\s*from|electrical\s*fire|sparking|flooding",
            text,
        )
    )


def map_urgency_level_from_analysis(urgency_level: str | None = None) -> LegacyUrgency | None:
    if not urgency_level:
        return None
    normalized = urgency_level.lower()
    if "emergency" in normalized:
        return "Emergency"
    if "urgent" in normalized:
        return "Urgent"
    if "routine" in normalized:
        return "Routine"
    if "estimate" in normalized:
        return "Estimate"
    return None


def extract_address_from_transcript(transcript: str | None = None) -> str | None:
    if not transcript:
        return None
    match = re.search(
        r"(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Court|Ct|Lane|Ln|Way|Boulevard|Blvd)[,\s]+[\w\s]+,?\s*(?:Texas|TX)?\s*\d{5})",
        transcript,
        re.I,
    )
    return match.group(1).strip() if match else None


def map_disconnection_reason(reason: str | None = None) -> str | None:
    if not reason:
        return None

    lowered = reason.lower()
    if "user_hangup" in lowered or "customer_hangup" in lowered or lowered == "hangup":
        return "customer_hangup"
    if "voicemail" in lowered:
        return "callback_later"
    return None


def extract_problem_duration(transcript: str | None) -> DurationResult | None:
    user_lines = _user_utterances(transcript)
    if not user_lines:
        return None

    for pattern, group_index, category in _DURATION_PATTERNS:
        match = pattern.search(user_lines)
        if match and match.group(group_index):
            return {"raw": match.group(group_index).strip(), "category": category}
    return None


__all__ = [
    "DurationCategory",
    "DurationResult",
    "LegacyUrgency",
    "extract_address_from_transcript",
    "extract_customer_name",
    "extract_problem_duration",
    "extract_safety_emergency",
    "map_disconnection_reason",
    "map_urgency_level_from_analysis",
]

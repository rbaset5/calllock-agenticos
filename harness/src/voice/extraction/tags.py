"""HVAC taxonomy tag classifier backed by the knowledge-pack YAML."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

NEGATION_PATTERN = re.compile(
    r"\b(no|not|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|never|deny|denied|any)\b",
    re.IGNORECASE,
)

_DURATION_PATTERNS: tuple[tuple[re.Pattern[str], int, str], ...] = (
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


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[4] / "knowledge" / "industry-packs" / "hvac"


def _load_taxonomy() -> dict[str, list[dict[str, Any]]]:
    taxonomy_path = _knowledge_root() / "taxonomy.yaml"
    try:
        text = taxonomy_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ImportError(f"Unable to read taxonomy file at {taxonomy_path}") from exc

    parts = text.split("---\n", 2)
    if len(parts) != 3:
        raise ImportError(f"Malformed taxonomy frontmatter in {taxonomy_path}")

    try:
        payload = yaml.safe_load(parts[2])
    except yaml.YAMLError as exc:
        raise ImportError(f"Invalid YAML in taxonomy file {taxonomy_path}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), dict):
        raise ImportError(f"taxonomy file {taxonomy_path} is missing a categories mapping")

    categories = payload["categories"]
    for category_name, tags in categories.items():
        if not isinstance(tags, list):
            raise ImportError(f"taxonomy category {category_name} must be a list")
        for tag in tags:
            if not isinstance(tag, dict) or "name" not in tag or "patterns" not in tag:
                raise ImportError(f"taxonomy tag entry in {category_name} is malformed")
    return categories


try:
    _CATEGORY_PATTERNS = _load_taxonomy()
except Exception as exc:  # pragma: no cover - exercised by import failure semantics
    raise ImportError(str(exc)) from exc

TAXONOMY_CATEGORIES = tuple(_CATEGORY_PATTERNS)


def _get_value(state: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in state:
            return state[key]
    return None


def _append_unique(values: list[str], tag: str) -> None:
    if tag not in values:
        values.append(tag)


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase or len(phrase) > 5:
        index = text.find(phrase)
        if index == -1:
            return False
        prefix = text[max(0, index - 40) : index]
        return NEGATION_PATTERN.search(prefix) is None

    match = re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE)
    if match is None:
        return False
    prefix = text[max(0, match.start() - 40) : match.start()]
    return NEGATION_PATTERN.search(prefix) is None


def _extract_problem_duration(transcript: str | None) -> dict[str, str] | None:
    if not transcript:
        return None

    user_lines = " ".join(
        line.removeprefix("User:").strip()
        for line in transcript.splitlines()
        if line.startswith("User:")
    )
    if not user_lines:
        return None

    for pattern, group_index, category in _DURATION_PATTERNS:
        match = pattern.search(user_lines)
        if match and match.group(group_index):
            return {"raw": match.group(group_index).strip(), "category": category}
    return None


def _call_datetime(call_start_timestamp: int | None) -> datetime:
    tz = ZoneInfo("America/Chicago")
    if call_start_timestamp is None:
        return datetime.now(tz)
    return datetime.fromtimestamp(call_start_timestamp / 1000, tz=tz)


def classify_call(
    state: Mapping[str, Any], transcript: str | None = None, call_start_timestamp: int | None = None
) -> dict[str, list[str]]:
    """Classify a call into the HVAC taxonomy."""

    tags = {category: [] for category in _CATEGORY_PATTERNS}

    text_to_analyze = " ".join(
        str(value)
        for value in (
            transcript or "",
            _get_value(state, "problem_description", "problemDescription") or "",
            _get_value(state, "hvac_issue_type", "hvacIssueType") or "",
            _get_value(state, "sales_lead_notes", "salesLeadNotes") or "",
        )
        if value
    ).lower()

    for category_name, category_tags in _CATEGORY_PATTERNS.items():
        for tag in category_tags:
            patterns = tag.get("patterns", [])
            if any(_contains_phrase(text_to_analyze, pattern.lower()) for pattern in patterns):
                tags[category_name].append(tag["name"])

    if tags["HAZARD"] and "CRITICAL_EVACUATE" not in tags["URGENCY"]:
        if {"GAS_LEAK", "CO_EVENT", "ELECTRICAL_FIRE"} & set(tags["HAZARD"]):
            _append_unique(tags["URGENCY"], "CRITICAL_EVACUATE")
        else:
            _append_unique(tags["URGENCY"], "EMERGENCY_SAMEDAY")

    end_call_reason = (_get_value(state, "end_call_reason", "endCallReason") or "").lower()
    if end_call_reason == "sales_lead":
        _append_unique(tags["REVENUE"], "HOT_LEAD")

    equipment_age = _get_value(state, "equipment_age", "equipmentAge")
    if equipment_age is not None:
        match = re.search(r"\d+", str(equipment_age))
        if match and int(match.group(0)) > 15:
            _append_unique(tags["REVENUE"], "R22_RETROFIT")

    property_type = (_get_value(state, "property_type", "propertyType") or "").lower()
    if property_type == "commercial":
        _append_unique(tags["CUSTOMER"], "COMMERCIAL_ACCT")
    elif property_type in {"house", "condo"}:
        _append_unique(tags["CUSTOMER"], "OWNER_OCCUPIED")

    is_decision_maker = _get_value(state, "is_decision_maker", "isDecisionMaker")
    if is_decision_maker is True:
        _append_unique(tags["CUSTOMER"], "DECISION_MAKER")
    elif is_decision_maker is False:
        _append_unique(tags["CUSTOMER"], "NEEDS_APPROVAL")

    if end_call_reason == "wrong_number":
        _append_unique(tags["NON_CUSTOMER"], "WRONG_NUMBER")

    duration_category = _get_value(state, "problem_duration_category", "problemDurationCategory")
    if duration_category is None:
        duration_result = _extract_problem_duration(transcript)
        duration_category = duration_result["category"] if duration_result else None
    if duration_category == "acute":
        _append_unique(tags["CONTEXT"], "DURATION_ACUTE")
    elif duration_category == "recent":
        _append_unique(tags["CONTEXT"], "DURATION_RECENT")
    elif duration_category == "ongoing":
        _append_unique(tags["CONTEXT"], "DURATION_ONGOING")

    call_dt = _call_datetime(call_start_timestamp)
    if call_dt.month in {6, 7, 8}:
        _append_unique(tags["CONTEXT"], "PEAK_SUMMER")
    elif call_dt.month in {12, 1, 2}:
        _append_unique(tags["CONTEXT"], "PEAK_WINTER")

    if call_dt.hour < 8 or call_dt.hour >= 17:
        _append_unique(tags["CONTEXT"], "AFTER_HOURS")

    if call_dt.weekday() in {5, 6}:
        _append_unique(tags["CONTEXT"], "WEEKEND")

    if not tags["URGENCY"]:
        urgency = (_get_value(state, "urgency") or "").lower()
        if urgency in {"emergency", "lifesafety"}:
            _append_unique(tags["URGENCY"], "EMERGENCY_SAMEDAY")
        elif urgency in {"urgent", "high"}:
            _append_unique(tags["URGENCY"], "URGENT_24HR")

    return tags


__all__ = ["TAXONOMY_CATEGORIES", "classify_call"]

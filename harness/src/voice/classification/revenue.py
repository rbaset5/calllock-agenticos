"""Revenue tier classification from call context."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_TIER_CONFIG = {
    "replacement": {
        "tier_label": "$$$$",
        "tier_description": "Potential Replacement",
        "estimated_range": "$5,000-$15,000+",
    },
    "major_repair": {
        "tier_label": "$$$",
        "tier_description": "Major Repair",
        "estimated_range": "$800-$3,000",
    },
    "standard_repair": {
        "tier_label": "$$",
        "tier_description": "Standard Repair",
        "estimated_range": "$200-$800",
    },
    "minor": {
        "tier_label": "$",
        "tier_description": "Maintenance/Minor",
        "estimated_range": "$75-$250",
    },
    "diagnostic": {
        "tier_label": "$$?",
        "tier_description": "Diagnostic Needed",
        "estimated_range": "$99 Diagnostic",
    },
}

_REPLACEMENT_REFRIGERANT = ["r-22", "r22", "freon", "old refrigerant"]
_REPLACEMENT_INTENT = [
    "new unit",
    "new system",
    "replace",
    "replacement",
    "upgrade",
    "quote for new",
    "time to replace",
    "need a new",
    "want a new",
]
_MAJOR_REPAIR_COMPONENTS = [
    "compressor",
    "heat exchanger",
    "coil",
    "evaporator coil",
    "condenser coil",
    "evaporator",
    "condenser",
]
_MAJOR_REPAIR_SEVERITY = [
    "completely dead",
    "won't turn on at all",
    "totally dead",
    "smoke",
    "burning smell",
    "burning",
]
_STANDARD_REPAIR_COMPONENTS = [
    "motor",
    "fan",
    "blower",
    "capacitor",
    "leak",
    "leaking",
    "recharge",
    "refrigerant",
]
_STANDARD_REPAIR_SCOPE = ["ductwork", "duct", "ducts", "adding zone", "zone", "vent"]
_MAINTENANCE_SERVICE = [
    "tune-up",
    "tune up",
    "tuneup",
    "maintenance",
    "cleaning",
    "filter",
    "check-up",
    "checkup",
    "inspection",
    "annual",
]
_MAINTENANCE_SIMPLE = ["thermostat", "weird noise", "running loud", "making noise", "strange sound"]


def _get_value(state: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in state:
            return state[key]
    return None


def _parse_equipment_age(age_text: str | None) -> int | None:
    if not age_text:
        return None
    match = re.search(r"(\d+)\s*(?:year|yr|years|yrs)", age_text, re.I)
    if match:
        age = int(match.group(1))
        return age if 0 <= age <= 50 else None
    match = re.fullmatch(r"(\d{1,2})", age_text.strip())
    if match:
        age = int(match.group(1))
        return age if 0 <= age <= 50 else None
    return None


def _contains_any(text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if keyword.lower() in text:
            return keyword
    return None


def _confidence(state: Mapping[str, Any], signal_count: int) -> str:
    if signal_count >= 2:
        return "high"
    context_values = (
        _get_value(state, "problem_description", "problemDescription"),
        _get_value(state, "equipment_age", "equipmentAge"),
        _get_value(state, "equipment_type", "equipmentType"),
    )
    if signal_count >= 1 and any(context_values):
        return "medium"
    return "low"


def _build_result(tier: str, signals: list[str], confidence: str) -> dict[str, Any]:
    config = _TIER_CONFIG[tier]
    return {
        "tier": tier,
        "tier_label": config["tier_label"],
        "tier_description": config["tier_description"],
        "estimated_range": config["estimated_range"],
        "confidence": confidence,
        "signals": signals,
        "potential_replacement": tier == "replacement",
    }


def estimate_revenue(state: Mapping[str, Any], transcript: str | None = None) -> dict[str, Any]:
    signals: list[str] = []
    all_text = " ".join(
        str(value)
        for value in (
            _get_value(state, "problem_description", "problemDescription") or "",
            _get_value(state, "equipment_type", "equipmentType") or "",
            _get_value(state, "sales_lead_notes", "salesLeadNotes") or "",
            transcript or "",
        )
        if value
    ).lower()

    equipment_age = _parse_equipment_age(_get_value(state, "equipment_age", "equipmentAge"))

    refrigerant_signal = _contains_any(all_text, _REPLACEMENT_REFRIGERANT)
    if refrigerant_signal:
        signals.append("R-22/Freon system")

    if equipment_age is not None and equipment_age >= 15:
        signals.append(f"{equipment_age}+ years old")

    intent_signal = _contains_any(all_text, _REPLACEMENT_INTENT)
    if intent_signal:
        signals.append("Replacement inquiry")

    has_recharge = _contains_any(all_text, ["recharge", "freon fill", "refrigerant"])
    if has_recharge and refrigerant_signal:
        signals.append("R-22 recharge (obsolete)")

    if refrigerant_signal or (equipment_age is not None and equipment_age >= 15) or intent_signal:
        return _build_result("replacement", signals, _confidence(state, len(signals)))

    major_component = _contains_any(all_text, _MAJOR_REPAIR_COMPONENTS)
    if major_component:
        signals.append(f"Major component: {major_component}")

    severity_signal = _contains_any(all_text, _MAJOR_REPAIR_SEVERITY)
    if severity_signal:
        signals.append(f"Severity: {severity_signal}")

    if major_component or severity_signal:
        return _build_result("major_repair", signals, _confidence(state, len(signals)))

    standard_component = _contains_any(all_text, _STANDARD_REPAIR_COMPONENTS)
    if standard_component:
        signals.append(f"Component: {standard_component}")

    scope_signal = _contains_any(all_text, _STANDARD_REPAIR_SCOPE)
    if scope_signal:
        signals.append(f"Scope: {scope_signal}")

    if standard_component or scope_signal:
        return _build_result("standard_repair", signals, _confidence(state, len(signals)))

    maintenance_signal = _contains_any(all_text, _MAINTENANCE_SERVICE)
    if maintenance_signal:
        signals.append(f"Service: {maintenance_signal}")

    simple_signal = _contains_any(all_text, _MAINTENANCE_SIMPLE)
    if simple_signal:
        signals.append(f"Issue: {simple_signal}")

    if maintenance_signal or simple_signal:
        return _build_result("minor", signals, _confidence(state, len(signals)))

    return _build_result("diagnostic", ["Insufficient signal"], "low")


__all__ = ["estimate_revenue"]

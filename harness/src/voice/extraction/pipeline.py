"""Extraction pipeline runner with per-step failure isolation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from voice.classification.call_type import map_urgency_to_dashboard
from voice.classification.revenue import estimate_revenue
from voice.classification.traffic import derive_caller_type, derive_primary_intent, route_call
from voice.extraction.call_scorecard import build_call_scorecard
from voice.extraction.hvac_issue import infer_hvac_issue_type
from voice.extraction.post_call import (
    extract_address_from_transcript,
    extract_customer_name,
    extract_problem_duration,
    extract_safety_emergency,
    map_disconnection_reason,
    map_urgency_level_from_analysis,
)
from voice.extraction.tags import TAXONOMY_CATEGORIES, classify_call
from voice.extraction.urgency import infer_urgency_from_context


def _get_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _map_legacy_urgency_to_tier(urgency_level: str) -> str:
    return {
        "Emergency": "emergency",
        "Urgent": "urgent",
        "Routine": "routine",
        "Estimate": "estimate",
    }[urgency_level]


def _empty_tag_categories() -> dict[str, list[str]]:
    return {category: [] for category in TAXONOMY_CATEGORIES}


def _flatten_tags(tag_categories: Mapping[str, list[str]]) -> list[str]:
    return [tag for tags in tag_categories.values() for tag in tags]


def _minimal_scorecard() -> dict[str, Any]:
    return {
        "score": 0,
        "warnings": ["zero-tags", "callback-gap"],
    }


def _build_state(transcript: str, raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    dynamic_variables = _get_value(
        raw_payload,
        "retell_llm_dynamic_variables",
        "dynamic_variables",
    ) or {}

    return {
        "call_id": _get_value(raw_payload, "call_id", "callId"),
        "customer_phone": _get_value(raw_payload, "from_number", "phone_number", "customer_phone"),
        "customer_name": _get_value(dynamic_variables, "customer_name"),
        "service_address": _get_value(dynamic_variables, "service_address"),
        "problem_description": _get_value(dynamic_variables, "problem_description")
        or _get_value(raw_payload, "call_summary"),
        "urgency": _get_value(dynamic_variables, "urgency", "urgency_level", "urgency_tier"),
        "appointment_booked": _to_bool(_get_value(dynamic_variables, "booking_confirmed", "appointment_booked")),
        "callback_type": _get_value(dynamic_variables, "callback_type"),
        "property_type": _get_value(dynamic_variables, "property_type"),
        "equipment_age": _get_value(dynamic_variables, "equipment_age"),
        "equipment_type": _get_value(dynamic_variables, "equipment_type"),
        "sales_lead_notes": _get_value(dynamic_variables, "sales_lead_notes"),
        "transcript": transcript,
    }


def run_extraction(transcript: str | None, raw_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Run the extraction/classification pipeline with per-step failure isolation."""

    payload = dict(raw_payload or {})
    transcript_text = transcript if transcript is not None else str(_get_value(payload, "transcript") or "")
    state = _build_state(transcript_text, payload)
    tag_categories = _empty_tag_categories()
    failed_steps: list[str] = []
    minimal_transcript = len(transcript_text.strip()) < 20

    result: dict[str, Any] = {
        "customer_name": state.get("customer_name"),
        "customer_phone": state.get("customer_phone"),
        "service_address": state.get("service_address"),
        "problem_description": state.get("problem_description"),
        "safety_emergency": False,
        "urgency_level": "Routine",
        "urgency_tier": "routine",
        "dashboard_urgency": "medium",
        "hvac_issue_type": None,
        "tag_categories": tag_categories,
        "tags": [],
        "quality_score": 0,
        "scorecard_warnings": [],
        "caller_type": "unknown",
        "primary_intent": "unknown",
        "revenue_tier": "diagnostic",
        "revenue_estimate": estimate_revenue({}, ""),
        "route": "legitimate",
        "end_call_reason": map_disconnection_reason(_get_value(payload, "disconnection_reason")),
        "extracted_fields": {},
        "failed_steps": failed_steps,
        "extraction_status": "complete",
    }

    state["end_call_reason"] = result["end_call_reason"]

    def run_step(step_name: str, func: Any, on_success: Any) -> None:
        try:
            value = func()
        except Exception:
            failed_steps.append(step_name)
            result["extraction_status"] = "partial"
            return
        on_success(value)

    run_step(
        "customer_name",
        lambda: extract_customer_name(transcript_text),
        lambda value: (
            result.__setitem__("customer_name", value or result["customer_name"]),
            state.__setitem__("customer_name", value or state.get("customer_name")),
        ),
    )
    run_step(
        "service_address",
        lambda: extract_address_from_transcript(transcript_text),
        lambda value: (
            result.__setitem__("service_address", value or result["service_address"]),
            state.__setitem__("service_address", value or state.get("service_address")),
        ),
    )
    run_step(
        "safety_emergency",
        lambda: extract_safety_emergency(transcript_text),
        lambda value: result.__setitem__("safety_emergency", value),
    )
    run_step(
        "problem_duration",
        lambda: extract_problem_duration(transcript_text),
        lambda value: result["extracted_fields"].__setitem__("problem_duration", value),
    )

    def _set_urgency(_: Any) -> None:
        analysis_urgency = map_urgency_level_from_analysis(state.get("urgency"))
        inferred = analysis_urgency or infer_urgency_from_context(result["problem_description"], transcript_text) or "Routine"
        result["urgency_level"] = inferred
        result["urgency_tier"] = _map_legacy_urgency_to_tier(inferred)
        state["urgency"] = inferred

    run_step("urgency", lambda: None, _set_urgency)

    run_step(
        "hvac_issue_type",
        lambda: infer_hvac_issue_type(result["problem_description"], transcript_text),
        lambda value: (
            result.__setitem__("hvac_issue_type", value),
            state.__setitem__("hvac_issue_type", value),
        ),
    )
    run_step(
        "tags",
        lambda: _empty_tag_categories()
        if minimal_transcript
        else classify_call(state, transcript_text, _get_value(payload, "start_timestamp")),
        lambda value: (
            result.__setitem__("tag_categories", value),
            result.__setitem__("tags", _flatten_tags(value)),
        ),
    )
    run_step(
        "revenue",
        lambda: estimate_revenue(state, transcript_text),
        lambda value: (
            result.__setitem__("revenue_estimate", value),
            result.__setitem__("revenue_tier", value["tier"]),
        ),
    )
    run_step(
        "caller_type",
        lambda: derive_caller_type(state, result["tag_categories"]),
        lambda value: result.__setitem__("caller_type", value),
    )
    run_step(
        "primary_intent",
        lambda: derive_primary_intent(state, result["tag_categories"]),
        lambda value: result.__setitem__("primary_intent", value),
    )
    run_step(
        "route",
        lambda: route_call(result["caller_type"], result["primary_intent"]),
        lambda value: result.__setitem__("route", value),
    )
    run_step(
        "scorecard",
        lambda: _minimal_scorecard() if minimal_transcript else build_call_scorecard(state, result["tag_categories"]),
        lambda value: (
            result.__setitem__("quality_score", value["score"]),
            result.__setitem__("scorecard_warnings", value["warnings"]),
        ),
    )
    run_step(
        "dashboard_urgency",
        lambda: map_urgency_to_dashboard(
            urgency_level=result["urgency_level"],
            end_call_reason="safety_emergency" if result["safety_emergency"] else result["end_call_reason"],
        ),
        lambda value: result.__setitem__("dashboard_urgency", value),
    )

    if "problem_duration" not in result["extracted_fields"]:
        result["extracted_fields"]["problem_duration"] = None

    return result


__all__ = ["run_extraction"]

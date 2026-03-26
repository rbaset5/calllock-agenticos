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


def _extract_from_tool_calls(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract structured data from Retell tool call arguments.

    The Retell agent collects customer_name, service_address, etc. during
    conversation and passes them as arguments to tools like book_service,
    check_availability, and create_callback_request. When dynamic_variables
    are not configured, this is the only source of structured data.
    """
    extracted: dict[str, Any] = {}
    import json as _json
    # Primary source: transcript_with_tool_calls (has full args as JSON strings)
    # Fallback: tool_call_results / tool_calls (often has empty args in Retell v2)
    tool_calls = raw_payload.get("transcript_with_tool_calls") or []
    if not any(
        tc.get("role") in ("tool_call_invocation", "tool_call_result")
        for tc in tool_calls
    ):
        tool_calls = raw_payload.get("tool_call_results") or raw_payload.get("tool_calls") or []
    for tc in tool_calls:
        # Skip transcript entries (only process tool calls)
        role = tc.get("role", "")
        if role and role not in ("tool_call_invocation", "tool_call_result"):
            continue
        args = tc.get("arguments") or tc.get("args") or tc.get("input") or {}
        if isinstance(args, str):
            try:
                args = _json.loads(args)
            except Exception:
                continue
        # Also check result content for booking confirmations
        content = tc.get("content") or tc.get("result") or {}
        if isinstance(content, str):
            try:
                content = _json.loads(content)
            except Exception:
                content = {}
        if not isinstance(args, dict):
            continue
        # Merge — later tool calls overwrite earlier ones (more refined data)
        for key in ("customer_name", "service_address", "issue_description", "problem_summary", "problem_description", "preferred_time",
                     "problem_description", "urgency_tier", "customer_phone",
                     "callback_type", "preferred_time", "lead_type",
                     "current_equipment", "equipment_type", "equipment_age", "notes"):
            val = args.get(key)
            if val and isinstance(val, str) and val.strip():
                extracted[key] = val.strip()
        # book_service confirmation means appointment was booked
        tool_name = tc.get("tool_name") or tc.get("name", "")
        if tool_name == "book_service":
            extracted["appointment_booked"] = True
        # Check result content for booking confirmation
        if isinstance(content, dict) and content.get("booking_confirmed"):
            extracted["appointment_booked"] = True
    # Map issue_description → problem_description
    if "issue_description" in extracted and "problem_description" not in extracted:
        extracted["problem_description"] = extracted.pop("issue_description")
    # Map problem_summary → problem_description (Retell uses this in transition_to_lookup)
    if "problem_summary" in extracted and "problem_description" not in extracted:
        extracted["problem_description"] = extracted.pop("problem_summary")
    extracted.pop("problem_summary", None)
    return extracted


def _build_state(transcript: str, raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    dynamic_variables = _get_value(
        raw_payload,
        "retell_llm_dynamic_variables",
        "dynamic_variables",
    ) or {}

    # Also extract from tool call arguments (fallback when dynamic_variables empty)
    tool_data = _extract_from_tool_calls(raw_payload)

    def _first(*values: Any) -> Any:
        for v in values:
            if v:
                return v
        return None

    return {
        "call_id": _get_value(raw_payload, "call_id", "callId"),
        "customer_phone": _first(
            _get_value(raw_payload, "from_number", "phone_number", "customer_phone"),
            tool_data.get("customer_phone"),
        ),
        "customer_name": _first(
            _get_value(dynamic_variables, "customer_name"),
            tool_data.get("customer_name"),
        ),
        "service_address": _first(
            _get_value(dynamic_variables, "service_address"),
            tool_data.get("service_address"),
        ),
        "problem_description": _first(
            _get_value(dynamic_variables, "problem_description"),
            tool_data.get("problem_description"),
            _get_value(raw_payload, "call_summary"),
        ),
        "urgency": _first(
            _get_value(dynamic_variables, "urgency", "urgency_level", "urgency_tier"),
            tool_data.get("urgency_tier"),
        ),
        "appointment_booked": _to_bool(
            _get_value(dynamic_variables, "booking_confirmed", "appointment_booked")
            or tool_data.get("appointment_booked", False)
        ),
        "callback_type": _first(
            _get_value(dynamic_variables, "callback_type"),
            tool_data.get("callback_type"),
        ),
        "property_type": _get_value(dynamic_variables, "property_type"),
        "equipment_age": _first(
            _get_value(dynamic_variables, "equipment_age"),
            tool_data.get("equipment_age"),
        ),
        "equipment_type": _first(
            _get_value(dynamic_variables, "equipment_type"),
            tool_data.get("current_equipment"),
        ),
        "sales_lead_notes": _first(
            _get_value(dynamic_variables, "sales_lead_notes"),
            tool_data.get("notes"),
        ),
        "transcript": transcript,
    }


def run_extraction(transcript: str | None, raw_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Run the extraction/classification pipeline with per-step failure isolation."""

    payload = dict(raw_payload or {})
    transcript_text = transcript if transcript is not None else str(_get_value(payload, "transcript") or "")
    state = _build_state(transcript_text, payload)
    tool_data = _extract_from_tool_calls(payload)
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

    # Only run transcript NER if tool_data didn't provide a customer_name.
    # Tool call args (from the agent's state machine) are more reliable than
    # transcript parsing, which often picks up garbled speech fragments.
    if not tool_data.get("customer_name"):
        run_step(
            "customer_name",
            lambda: extract_customer_name(transcript_text),
            lambda value: (
                result.__setitem__("customer_name", value or result["customer_name"]),
                state.__setitem__("customer_name", value or state.get("customer_name")),
            ),
        )
    # Same for service_address — prefer tool_data over transcript parsing
    if not tool_data.get("service_address"):
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

    # Promote state-only fields to result so they persist in extracted_fields
    result["equipment_type"] = state.get("equipment_type")
    result["equipment_brand"] = state.get("equipment_brand")
    result["equipment_age"] = state.get("equipment_age")
    result["appointment_booked"] = state.get("appointment_booked", False)
    result["callback_type"] = state.get("callback_type")

    return result


__all__ = ["run_extraction"]

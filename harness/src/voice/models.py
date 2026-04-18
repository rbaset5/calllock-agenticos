"""Pydantic models for the voice agent module."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


class UrgencyTier(StrEnum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"
    ESTIMATE = "estimate"


class CallerType(StrEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    PROPERTY_MANAGER = "property_manager"
    THIRD_PARTY = "third_party"
    JOB_APPLICANT = "job_applicant"
    VENDOR = "vendor"
    SPAM = "spam"
    UNKNOWN = "unknown"


class PrimaryIntent(StrEnum):
    SERVICE = "service"
    MAINTENANCE = "maintenance"
    INSTALLATION = "installation"
    ESTIMATE = "estimate"
    COMPLAINT = "complaint"
    FOLLOWUP = "followup"
    SALES = "sales"
    UNKNOWN = "unknown"


class RevenueTier(StrEnum):
    REPLACEMENT = "replacement"
    MAJOR_REPAIR = "major_repair"
    STANDARD_REPAIR = "standard_repair"
    MINOR = "minor"
    DIAGNOSTIC = "diagnostic"
    UNKNOWN = "unknown"


class EndCallReason(StrEnum):
    CUSTOMER_HANGUP = "customer_hangup"
    AGENT_HANGUP = "agent_hangup"
    BOOKING_CONFIRMED = "booking_confirmed"
    CALLBACK_SCHEDULED = "callback_scheduled"
    CALLBACK_LATER = "callback_later"
    SALES_LEAD = "sales_lead"
    OUT_OF_AREA = "out_of_area"
    SAFETY_EXIT = "safety_exit"
    SAFETY_EMERGENCY = "safety_emergency"
    URGENT_ESCALATION = "urgent_escalation"
    WRONG_NUMBER = "wrong_number"
    VOICEMAIL = "voicemail"
    TRANSFER = "transfer"
    ERROR = "error"


class LooseModel(BaseModel):
    """Base model that allows extra fields but logs them for auditability."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def log_unexpected_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        allowed_names = set(cls.model_fields)
        allowed_aliases = {field.alias for field in cls.model_fields.values() if field.alias}
        unexpected = sorted(set(data) - allowed_names - allowed_aliases)
        if unexpected:
            logger.warning("%s received unexpected fields: %s", cls.__name__, ", ".join(unexpected))
        return data


class VoiceConfig(BaseModel):
    """Per-tenant voice agent configuration."""

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_owner_phone: str
    service_area_zips: list[str]
    business_name: str
    business_phone: str


class CalcomConfig(BaseModel):
    """Per-tenant Cal.com configuration."""

    calcom_api_key: str
    calcom_event_type_id: int
    calcom_username: str
    calcom_timezone: str


class TranscriptMessage(BaseModel):
    role: Literal["agent", "user"]
    content: str


class RetellToolCallRequest(LooseModel):
    """Incoming Retell tool call webhook payload."""

    call_id: str
    tool_name: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_retell_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        call = normalized.get("call")
        if isinstance(call, dict):
            if "call_id" not in normalized and call.get("call_id"):
                normalized["call_id"] = call["call_id"]
            if ("metadata" not in normalized or not isinstance(normalized.get("metadata"), dict)) and isinstance(
                call.get("metadata"), dict
            ):
                normalized["metadata"] = call["metadata"]

        if "tool_name" not in normalized and isinstance(normalized.get("name"), str):
            normalized["tool_name"] = normalized["name"]

        return normalized


class RetellCallEndedPayload(LooseModel):
    """Incoming Retell call-ended webhook payload."""

    event: str | None = None
    call_id: str
    transcript: str = ""
    transcript_object: list[TranscriptMessage] = Field(default_factory=list)
    call_summary: str | None = None
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    call_analysis: dict[str, Any] = Field(default_factory=dict)
    from_number: str | None = None
    to_number: str | None = None
    direction: str | None = None
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    duration_ms: int | None = None
    recording_url: str | None = None
    disconnection_reason: str | None = None
    dynamic_variables: dict[str, str] = Field(default_factory=dict, alias="retell_llm_dynamic_variables")
    tool_call_results: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_retell_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        call = data.get("call")
        if not isinstance(call, dict):
            return data

        normalized = dict(call)
        normalized["event"] = data.get("event")
        if "custom_metadata" not in normalized and isinstance(call.get("metadata"), dict):
            normalized["custom_metadata"] = call["metadata"]
        normalized.pop("metadata", None)
        if "call_summary" not in normalized and isinstance(call.get("call_analysis"), dict):
            summary = call["call_analysis"].get("call_summary")
            if isinstance(summary, str):
                normalized["call_summary"] = summary
        return normalized


class CallEndedEvent(BaseModel):
    """Inngest event payload for calllock/call.ended."""

    tenant_id: str
    call_id: str
    call_source: Literal["retell"] = "retell"
    phone_number: str
    transcript: str
    customer_name: str | None = None
    service_address: str | None = None
    problem_description: str | None = None
    urgency_tier: UrgencyTier
    caller_type: CallerType
    primary_intent: PrimaryIntent
    revenue_tier: RevenueTier
    tags: list[str]
    quality_score: float
    scorecard_warnings: list[str]
    route: Literal["legitimate", "spam", "vendor", "recruiter"]
    booking_id: str | None = None
    callback_scheduled: bool = False
    extraction_status: Literal["complete", "partial"]
    retell_call_id: str
    call_duration_seconds: int
    end_call_reason: EndCallReason
    call_recording_url: str | None = None


class DashboardPayload(BaseModel):
    """CallLock App dashboard sync payload."""

    customer_name: str
    customer_phone: str
    customer_address: str
    service_type: Literal["hvac", "plumbing", "electrical", "general"]
    urgency: Literal["low", "medium", "high", "emergency"]
    ai_summary: str | None = None
    scheduled_at: str | None = None
    call_transcript: str | None = None
    transcript_object: list[TranscriptMessage] | None = None
    user_email: str
    revenue_tier: RevenueTier | None = None
    revenue_tier_label: str | None = None
    revenue_tier_description: str | None = None
    revenue_tier_range: str | None = None
    revenue_tier_signals: list[str] | None = None
    revenue_confidence: Literal["low", "medium", "high"] | None = None
    potential_replacement: bool | None = None
    estimated_value: int | None = None
    end_call_reason: EndCallReason | None = None
    issue_description: str | None = None
    equipment_type: str | None = None
    equipment_age: str | None = None
    sales_lead_notes: str | None = None
    problem_duration: str | None = None
    problem_duration_category: Literal["acute", "recent", "ongoing"] | None = None
    problem_onset: str | None = None
    problem_pattern: str | None = None
    customer_attempted_fixes: str | None = None
    call_id: str | None = None
    priority_color: Literal["red", "green", "blue", "gray"] | None = None
    priority_reason: str | None = None
    property_type: Literal["house", "condo", "apartment", "commercial"] | None = None
    system_status: Literal["completely_down", "partially_working", "running_but_ineffective"] | None = None
    equipment_age_bracket: Literal["under_10", "10_to_15", "over_15", "unknown"] | None = None
    is_decision_maker: bool | None = None
    decision_maker_contact: str | None = None
    tags: dict[str, list[str]] | None = None
    site_contact_name: str | None = None
    site_contact_phone: str | None = None
    is_third_party: bool | None = None
    third_party_type: str | None = None
    call_type: str | None = None
    call_subtype: str | None = None
    call_type_confidence: Literal["low", "medium", "high"] | None = None
    is_commercial: bool | None = None
    sentiment_score: float | None = None
    work_type: Literal["service", "maintenance", "install", "admin"] | None = None
    caller_type: str | None = None
    primary_intent: str | None = None
    card_headline: str | None = None
    card_summary: str | None = None
    booking_status: Literal["confirmed", "attempted_failed", "not_requested"] | None = None
    slot_changed: bool | None = None
    urgency_mismatch: bool | None = None
    booking_requested_time: str | None = None
    booking_booked_slot: str | None = None
    booking_urgency_transition: str | None = None


__all__ = [
    "CalcomConfig",
    "CallEndedEvent",
    "CallerType",
    "DashboardPayload",
    "EndCallReason",
    "LooseModel",
    "PrimaryIntent",
    "RetellCallEndedPayload",
    "RetellToolCallRequest",
    "RevenueTier",
    "TranscriptMessage",
    "UrgencyTier",
    "VoiceConfig",
]

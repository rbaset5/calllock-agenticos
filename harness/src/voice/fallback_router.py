"""Deterministic fallback routing for live voice calls.

Retell may collect the caller's intent, but the backend owns the final fallback
decision so the agent cannot improvise transfers, callbacks, or voicemail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FallbackAction = Literal["transfer", "callback_task", "voicemail", "safe_hangup"]
FallbackPriority = Literal["emergency", "urgent", "standard"]


@dataclass(frozen=True)
class FallbackContext:
    urgency_tier: str
    route: str
    business_open: bool
    caller_requested_human: bool
    booking_failed: bool
    confidence: float


@dataclass(frozen=True)
class FallbackPolicy:
    live_transfer_enabled: bool = False
    callback_tasks_enabled: bool = True
    voicemail_enabled: bool = False
    default_transfer_number: str | None = None
    emergency_transfer_number: str | None = None
    voicemail_number: str | None = None
    low_confidence_threshold: float = 0.65


@dataclass(frozen=True)
class FallbackDecision:
    action: FallbackAction
    reason: str
    priority: FallbackPriority
    target_number: str | None = None
    backup_action: FallbackAction | None = None


def route_call_fallback(
    context: FallbackContext,
    policy: FallbackPolicy,
) -> FallbackDecision:
    """Choose the allowed fallback action for a call.

    The order is intentionally conservative: non-customer traffic exits first,
    emergencies try a live transfer first, durable callback tasks beat voicemail,
    and voicemail is only used when configured as an allowed fallback.
    """

    urgency = context.urgency_tier.lower()
    priority = _priority_for_urgency(urgency)

    if context.route in {"spam", "vendor", "recruiter"}:
        return FallbackDecision(
            action="safe_hangup",
            reason="non_customer_route",
            priority="standard",
        )

    if urgency == "emergency":
        target = policy.emergency_transfer_number or policy.default_transfer_number
        if policy.live_transfer_enabled and target:
            return FallbackDecision(
                action="transfer",
                reason="emergency",
                priority="emergency",
                target_number=target,
                backup_action=_backup_action(policy),
            )
        return _durable_fallback("emergency", "emergency", policy)

    if context.caller_requested_human and policy.live_transfer_enabled and policy.default_transfer_number:
        return FallbackDecision(
            action="transfer",
            reason="caller_requested_human",
            priority=priority,
            target_number=policy.default_transfer_number,
            backup_action=_backup_action(policy),
        )

    if context.confidence < policy.low_confidence_threshold:
        return _durable_fallback("low_confidence", priority, policy)

    if context.booking_failed:
        return _durable_fallback("booking_failed", priority, policy)

    if not context.business_open:
        return _durable_fallback("after_hours", priority, policy)

    return _durable_fallback("fallback_required", priority, policy)


def _priority_for_urgency(urgency: str) -> FallbackPriority:
    if urgency == "emergency":
        return "emergency"
    if urgency == "urgent":
        return "urgent"
    return "standard"


def _backup_action(policy: FallbackPolicy) -> FallbackAction | None:
    if policy.callback_tasks_enabled:
        return "callback_task"
    if policy.voicemail_enabled and policy.voicemail_number:
        return "voicemail"
    return None


def _durable_fallback(
    reason: str,
    priority: FallbackPriority,
    policy: FallbackPolicy,
) -> FallbackDecision:
    if policy.callback_tasks_enabled:
        return FallbackDecision(
            action="callback_task",
            reason=reason,
            priority=priority,
        )
    if policy.voicemail_enabled and policy.voicemail_number:
        return FallbackDecision(
            action="voicemail",
            reason=reason,
            priority=priority,
            target_number=policy.voicemail_number,
        )
    return FallbackDecision(
        action="safe_hangup",
        reason=f"{reason}_no_available_fallback",
        priority=priority,
    )


__all__ = [
    "FallbackContext",
    "FallbackDecision",
    "FallbackPolicy",
    "route_call_fallback",
]

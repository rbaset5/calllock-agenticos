"""Tests for deterministic voice fallback routing."""

from __future__ import annotations

from voice.fallback_router import FallbackContext, FallbackPolicy, route_call_fallback


def test_emergency_prefers_live_transfer_with_callback_backup() -> None:
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier="emergency",
            route="legitimate",
            business_open=False,
            caller_requested_human=False,
            booking_failed=False,
            confidence=0.95,
        ),
        FallbackPolicy(
            live_transfer_enabled=True,
            callback_tasks_enabled=True,
            voicemail_enabled=True,
            default_transfer_number="+15125550001",
            emergency_transfer_number="+15125559111",
            voicemail_number="+15125559999",
        ),
    )

    assert decision.action == "transfer"
    assert decision.target_number == "+15125559111"
    assert decision.priority == "emergency"
    assert decision.backup_action == "callback_task"


def test_after_hours_booking_failure_creates_callback_task() -> None:
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier="routine",
            route="legitimate",
            business_open=False,
            caller_requested_human=False,
            booking_failed=True,
            confidence=0.8,
        ),
        FallbackPolicy(
            live_transfer_enabled=True,
            callback_tasks_enabled=True,
            voicemail_enabled=True,
            default_transfer_number="+15125550001",
            voicemail_number="+15125559999",
        ),
    )

    assert decision.action == "callback_task"
    assert decision.priority == "standard"
    assert decision.target_number is None
    assert decision.reason == "booking_failed"


def test_voicemail_used_only_when_callback_disabled() -> None:
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier="routine",
            route="legitimate",
            business_open=False,
            caller_requested_human=False,
            booking_failed=True,
            confidence=0.8,
        ),
        FallbackPolicy(
            live_transfer_enabled=False,
            callback_tasks_enabled=False,
            voicemail_enabled=True,
            voicemail_number="+15125559999",
        ),
    )

    assert decision.action == "voicemail"
    assert decision.target_number == "+15125559999"
    assert decision.backup_action is None


def test_spam_vendor_routes_to_safe_hangup() -> None:
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier="routine",
            route="vendor",
            business_open=True,
            caller_requested_human=True,
            booking_failed=False,
            confidence=0.9,
        ),
        FallbackPolicy(
            live_transfer_enabled=True,
            callback_tasks_enabled=True,
            voicemail_enabled=True,
            default_transfer_number="+15125550001",
            voicemail_number="+15125559999",
        ),
    )

    assert decision.action == "safe_hangup"
    assert decision.reason == "non_customer_route"

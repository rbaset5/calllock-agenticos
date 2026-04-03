from harness.detection.triage import assess_detection_event, build_detection_event, decide_notification
from harness.incident_classification import classify_incident


def test_build_detection_event_normalizes_voice_signal_shape() -> None:
    event = build_detection_event(
        monitor_id="voice_warning_rate_spike",
        tenant_id="tenant-1",
        severity="high",
        raw_context={"warning_rate": 0.42},
    )

    assert event == {
        "source": "alerts",
        "surface": "voice",
        "signal_type": "voice_warning_rate_spike",
        "severity": "high",
        "tenant_id": "tenant-1",
        "dedupe_key": "tenant-1:voice_warning_rate_spike",
        "raw_context": {"warning_rate": 0.42},
    }


def test_duplicate_open_issue_stands_down() -> None:
    event = {
        "signal_type": "voice_warning_rate_spike",
        "severity": "high",
        "dedupe_key": "tenant-1:voice_warning_rate_spike",
    }

    assessment = assess_detection_event(event, has_open_issue=True, in_flight_fix=False)

    assert assessment["outcome"] == "stand_down"
    assert assessment["reason"] == "matching_issue_already_active"


def test_in_flight_fix_stands_down() -> None:
    event = {
        "signal_type": "voice_route_missing_spike",
        "severity": "high",
        "dedupe_key": "tenant-1:voice_route_missing_spike",
    }

    assessment = assess_detection_event(event, has_open_issue=False, in_flight_fix=True)

    assert assessment["outcome"] == "stand_down"
    assert assessment["reason"] == "matching_issue_already_active"


def test_critical_safety_signal_escalates() -> None:
    event = {
        "signal_type": "voice_safety_emergency_mismatch_signal",
        "severity": "critical",
        "dedupe_key": "tenant-1:voice_safety_emergency_mismatch_signal",
    }

    assessment = assess_detection_event(event, has_open_issue=False, in_flight_fix=False)

    assert assessment["outcome"] == "escalate"
    assert assessment["reason"] == "safety_signal"


def test_low_severity_signal_is_suppressed() -> None:
    event = {
        "signal_type": "voice_warning_rate_spike",
        "severity": "low",
        "dedupe_key": "tenant-1:voice_warning_rate_spike",
    }

    assessment = assess_detection_event(event, has_open_issue=False, in_flight_fix=False)

    assert assessment["outcome"] == "suppress"
    assert assessment["reason"] == "below_operational_threshold"


def test_high_severity_new_signal_investigates() -> None:
    event = {
        "signal_type": "voice_empty_structured_output_spike",
        "severity": "high",
        "dedupe_key": "tenant-1:voice_empty_structured_output_spike",
    }

    assessment = assess_detection_event(event, has_open_issue=False, in_flight_fix=False)

    assert assessment["outcome"] == "investigate"
    assert assessment["reason"] == "new_meaningful_signal"


def test_notification_for_investigation_stays_internal() -> None:
    event = {
        "surface": "voice",
        "severity": "high",
    }

    decision = decide_notification(event, {"outcome": "investigate", "reason": "new_meaningful_signal"})

    assert decision["notification_outcome"] == "internal_only"
    assert decision["channels"] == ["dashboard"]


def test_notification_for_escalation_notifies_founder_on_critical() -> None:
    event = {
        "surface": "voice",
        "severity": "critical",
    }

    decision = decide_notification(event, {"outcome": "escalate", "reason": "safety_signal"})

    assert decision["notification_outcome"] == "founder_notify"
    assert decision["channels"] == ["dashboard", "email"]


def test_notification_for_stand_down_is_silent() -> None:
    event = {
        "surface": "voice",
        "severity": "high",
    }

    decision = decide_notification(event, {"outcome": "stand_down", "reason": "matching_issue_already_active"})

    assert decision["notification_outcome"] == "silent_stand_down"
    assert decision["channels"] == []


def test_voice_detection_alerts_classify_into_voice_domain() -> None:
    classification = classify_incident(
        {"alert_type": "voice_route_missing_spike", "severity": "high"},
    )

    assert classification["incident_domain"] == "voice"
    assert classification["incident_category"] == "voice_quality_regression"
    assert classification["remediation_category"] == "voice_investigation"
    assert classification["incident_urgency"] == "high"


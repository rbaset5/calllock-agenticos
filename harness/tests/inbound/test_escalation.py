from inbound.escalation import (
    build_escalation_payload,
    build_system_alert_payload,
    check_consecutive_poll_failures,
    check_quarantine_rate,
    should_auto_archive,
    should_escalate,
)


def test_should_escalate_exceptional() -> None:
    assert should_escalate("exceptional", 95) is True


def test_should_escalate_high() -> None:
    assert should_escalate("high", 90) is False


def test_should_auto_archive_spam() -> None:
    assert should_auto_archive("spam") is True


def test_should_auto_archive_medium() -> None:
    assert should_auto_archive("medium") is False


def test_build_escalation_payload() -> None:
    payload = build_escalation_payload("tenant-1", "msg-1", "owner@example.com", "Need help", 95, "Strong fit", "exceptional")

    assert payload["priority"] == "high"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["channel"] == "founder_review"


def test_build_system_alert_payload() -> None:
    payload = build_system_alert_payload("tenant-1", "poll_failure", {"count": 3})

    assert payload["alert_type"] == "poll_failure"
    assert payload["details"] == {"count": 3}


def test_quarantine_rate_above_threshold() -> None:
    assert check_quarantine_rate(10, 6, threshold=0.5) is True


def test_quarantine_rate_below_threshold() -> None:
    assert check_quarantine_rate(10, 5, threshold=0.5) is False


def test_quarantine_rate_zero_messages() -> None:
    assert check_quarantine_rate(0, 0) is False


def test_consecutive_poll_failures() -> None:
    assert check_consecutive_poll_failures(3, threshold=3) is True
    assert check_consecutive_poll_failures(2, threshold=3) is False

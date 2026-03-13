from harness.verification.outcomes import resolve_verification_outcome


def test_verification_outcome_prioritizes_block() -> None:
    outcome = resolve_verification_outcome(
        [{"severity": "retry", "reason": "retry"}, {"severity": "block", "reason": "block"}],
        retry_count=0,
        max_retries=1,
    )
    assert outcome["verdict"] == "block"


def test_verification_outcome_escalates_after_retry_budget() -> None:
    outcome = resolve_verification_outcome([{"severity": "retry", "reason": "retry"}], retry_count=1, max_retries=1)
    assert outcome["verdict"] == "escalate"

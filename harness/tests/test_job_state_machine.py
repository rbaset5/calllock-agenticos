import pytest

from harness.jobs.state_machine import validate_transition


def test_job_state_machine_accepts_valid_transition() -> None:
    validate_transition("queued", "running")


def test_job_state_machine_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError):
        validate_transition("completed", "running")

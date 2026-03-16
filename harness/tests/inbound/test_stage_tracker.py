import logging

from inbound.stage_tracker import (
    TRANSITIONS,
    VALID_STAGES,
    assign_initial_stage,
    detect_drift,
    is_valid_stage,
    is_valid_transition,
    transition_stage,
)


def test_is_valid_stage_and_valid_transitions() -> None:
    for stage in VALID_STAGES:
        assert is_valid_stage(stage) is True
    assert is_valid_stage("unknown") is False

    for from_stage, targets in TRANSITIONS.items():
        for to_stage in targets:
            assert is_valid_transition(from_stage, to_stage) is True


def test_invalid_transitions_are_rejected() -> None:
    assert is_valid_transition("new", "won") is False
    assert is_valid_transition("won", "new") is False
    assert is_valid_transition("archived", "qualified") is False
    assert is_valid_transition("unknown", "new") is False


def test_assign_initial_stage_maps_every_action_tier() -> None:
    assert assign_initial_stage("exceptional") == "qualified"
    assert assign_initial_stage("high") == "qualified"
    assert assign_initial_stage("medium") == "new"
    assert assign_initial_stage("low") == "new"
    assert assign_initial_stage("spam") == "archived"
    assert assign_initial_stage("non-lead") == "archived"


def test_transition_stage_returns_transition_for_valid_move() -> None:
    transition = transition_stage("qualified", "engaged")

    assert transition is not None
    assert transition.from_stage == "qualified"
    assert transition.to_stage == "engaged"
    assert transition.changed_by == "inbound_pipeline"


def test_transition_stage_logs_and_rejects_drift(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="inbound.stage_tracker"):
        transition = transition_stage("new", "won")

    assert transition is None
    assert detect_drift("new", "won") is True
    assert detect_drift("qualified", "qualified") is False
    assert "stage_drift" in caplog.text

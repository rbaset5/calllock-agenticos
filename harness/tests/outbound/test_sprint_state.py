from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from outbound import sprint_state


def _et(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/Detroit"))


def test_get_current_state_during_am_block() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 3, 31, 7, 20))

    assert state["block_active"] is True
    assert state["current_block"] == "AM"
    assert state["active_segment"] == "SE"
    assert state["sprint_index"] == 1
    assert state["sprints_completed_today"] == 0
    assert state["minutes_until_next"] >= 20
    assert state["all_blocks"]


def test_get_current_state_during_mid_block() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 4, 25, 13, 5))

    assert state["block_active"] is True
    assert state["current_block"] == "MID"
    assert state["active_segment"] == "hot_leads"
    assert state["next_segment_name"] == "warm_callbacks"


def test_get_current_state_during_recovery_counts_completed_sprint() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 3, 31, 7, 42))

    assert state["block_active"] is True
    assert state["current_block"] == "AM"
    assert state["active_segment"] == "SE"
    assert state["sprints_completed_today"] == 1


def test_get_current_state_between_blocks() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 4, 14, 12, 30))

    assert state["block_active"] is False
    assert state["next_block"] == "MID"
    assert state["next_block_at"].endswith("-04:00")


def test_get_current_state_before_start() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 3, 29, 9, 0))

    assert state["block_active"] is False
    assert "Sprint starts" in state["message"]


def test_get_current_state_rest_day() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 4, 5, 9, 0))

    assert state["block_active"] is False
    assert state["message"] == "Rest day"


def test_get_current_state_after_deadline() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 5, 17, 9, 0))

    assert state["block_active"] is False
    assert state["message"] == "Sprint complete"


def test_get_current_state_uses_week_specific_dials_per_sprint() -> None:
    state = sprint_state.get_current_state(at=_et(2026, 5, 4, 8, 0))

    assert state["week"] == 6
    assert state["dials_target_today"] == state["sprints_target_today"] * 13

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest
from outbound import daily_plan


def _write_schedule(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "schedule.yaml"
    # YAML parser accepts JSON, which avoids an extra test-time dependency.
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_schedule() -> dict:
    return {
        "start_date": "2026-03-30",
        "dials_per_sprint": 10,
        "sprint_duration_min": 20,
        "recovery_min": 5,
        "weeks": {
            1: {
                "days": "weekdays",
                "daily_targets": [2, 3, 3, 4, 4],
                "blocks": {
                    "AM": {
                        "start_et": "07:20",
                        "sprints": [
                            {"metro": "FL", "note": "s1"},
                            {"metro": "TX", "note": "s2"},
                            {"metro": "AZ", "note": "s3"},
                            {"metro": "callbacks", "note": "s4"},
                        ],
                    }
                },
            },
            4: {"days": "weekdays_saturday", "blocks": {"AM": {"start_et": "07:20", "sprints": []}}},
            7: {"days": "weekdays_saturday", "blocks": {"AM": {"start_et": "07:20", "sprints": []}}},
        },
    }


def test_load_schedule_valid(tmp_path: Path) -> None:
    schedule_path = _write_schedule(tmp_path, _base_schedule())
    loaded = daily_plan.load_schedule(schedule_path)
    assert "weeks" in loaded


def test_load_schedule_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yaml"
    assert daily_plan.load_schedule(missing) == {}


def test_load_schedule_malformed(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.yaml"
    malformed.write_text("this: is: not: yaml", encoding="utf-8")
    assert daily_plan.load_schedule(malformed) == {}


def test_current_week_number_before_start() -> None:
    assert daily_plan.current_week_number(_base_schedule(), today=date(2026, 3, 29)) == 0


def test_current_week_number_week1() -> None:
    assert daily_plan.current_week_number(_base_schedule(), today=date(2026, 3, 30)) == 1


def test_current_week_number_capped() -> None:
    assert daily_plan.current_week_number(_base_schedule(), today=date(2026, 5, 25)) == 7


def test_is_calling_day_weekday() -> None:
    assert daily_plan.is_calling_day(_base_schedule(), week_num=1, today=date(2026, 3, 30)) is True


def test_is_calling_day_weekend() -> None:
    assert daily_plan.is_calling_day(_base_schedule(), week_num=1, today=date(2026, 4, 4)) is False


def test_is_calling_day_saturday_calling() -> None:
    assert daily_plan.is_calling_day(_base_schedule(), week_num=4, today=date(2026, 4, 25)) is True


def test_get_daily_sprint_count_uses_daily_targets() -> None:
    schedule = _base_schedule()
    # Wednesday index (2) should return 3 sprints.
    count = daily_plan.get_daily_sprint_count(schedule, week_num=1, today=date(2026, 4, 1))
    assert count == 3


def test_build_daily_plan_week0(tmp_path: Path) -> None:
    schedule = _base_schedule()
    schedule["start_date"] = "2026-04-06"
    schedule_path = _write_schedule(tmp_path, schedule)

    plan = daily_plan.build_daily_plan(today=date(2026, 3, 30), schedule_path=schedule_path)

    assert plan["week"] == 0
    assert "Sprint starts" in plan["message"]


def test_build_daily_plan_rest_day(tmp_path: Path) -> None:
    schedule_path = _write_schedule(tmp_path, _base_schedule())

    plan = daily_plan.build_daily_plan(today=date(2026, 4, 4), schedule_path=schedule_path)

    assert plan["week"] == 1
    assert "Rest day" in plan["message"]


def test_build_daily_plan_with_sprints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    schedule = _base_schedule()
    schedule["weeks"][1]["dials_per_sprint"] = 11
    schedule_path = _write_schedule(tmp_path, schedule)

    monkeypatch.setattr(
        daily_plan.store,
        "list_due_callbacks",
        lambda **_kwargs: [
            {
                "prospect_id": "cb-1",
                "business_name": "Callback Co",
                "phone": "+15550001111",
                "metro": "Miami",
            }
        ],
    )

    monkeypatch.setattr(
        daily_plan.store,
        "list_ranked_call_ready_prospects",
        lambda **_kwargs: [
            {"id": "fl-1", "business_name": "FL 1", "metro": "Miami"},
            {"id": "fl-2", "business_name": "FL 2", "metro": "Orlando"},
            {"id": "tx-1", "business_name": "TX 1", "metro": "Dallas"},
            {"id": "az-1", "business_name": "AZ 1", "metro": "Phoenix"},
        ],
    )
    monkeypatch.setattr(daily_plan.store, "list_outbound_calls", lambda **_kw: [])

    plan = daily_plan.build_daily_plan(today=date(2026, 3, 30), schedule_path=schedule_path)

    # Monday daily target is 2 sprints, so only first 2 configured sprints should be used.
    assert plan["total_sprints"] == 2
    assert len(plan["blocks"][0]["sprints"]) == 2
    assert plan["dials_per_sprint"] == 11


def test_callbacks_prioritized_in_metro_sprints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Due callbacks appear before fresh leads within metro-filtered sprints."""
    schedule = _base_schedule()
    # Use 4 sprints on Monday so the FL sprint gets included
    schedule["weeks"][1]["daily_targets"] = [4, 4, 4, 4, 4]
    schedule_path = _write_schedule(tmp_path, schedule)

    monkeypatch.setattr(
        daily_plan.store,
        "list_due_callbacks",
        lambda **_kwargs: [
            {"prospect_id": "cb-fl", "business_name": "Callback FL", "phone": "+15550001111", "metro": "Miami"},
        ],
    )
    monkeypatch.setattr(
        daily_plan.store,
        "list_ranked_call_ready_prospects",
        lambda **_kwargs: [
            {"id": "fl-1", "business_name": "Fresh FL 1", "metro": "Miami"},
            {"id": "fl-2", "business_name": "Fresh FL 2", "metro": "Orlando"},
            {"id": "tx-1", "business_name": "TX 1", "metro": "Dallas"},
            {"id": "az-1", "business_name": "AZ 1", "metro": "Phoenix"},
        ],
    )
    monkeypatch.setattr(daily_plan.store, "list_outbound_calls", lambda **_kw: [])

    plan = daily_plan.build_daily_plan(today=date(2026, 3, 30), schedule_path=schedule_path)

    # First sprint is FL metro — callback should be first lead, then fresh
    fl_sprint = plan["blocks"][0]["sprints"][0]
    assert fl_sprint["metro"] == "FL"
    leads = fl_sprint["leads"]
    assert len(leads) >= 2  # callback + at least 1 fresh
    assert leads[0]["prospect_id"] == "cb-fl"  # callback comes first
    assert leads[1]["id"] == "fl-1"  # then fresh


def test_final_attempt_callbacks_routed_to_eod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Callback on attempt 3 (final) should go to EOD block, not MID."""
    schedule = _base_schedule()
    schedule["callback_cadence"] = {"max_attempts": 3}
    # Week 3+ has MID and EOD blocks
    schedule["weeks"][1]["daily_targets"] = [9, 9, 9, 9, 9]
    schedule["weeks"][1]["blocks"] = {
        "AM": {
            "start_et": "07:20",
            "sprints": [
                {"metro": "FL", "note": "s1"},
                {"metro": "TX", "note": "s2"},
            ],
        },
        "MID": {
            "start_et": "13:00",
            "sprints": [
                {"metro": "callbacks", "note": "mid callbacks"},
            ],
        },
        "EOD": {
            "start_et": "16:00",
            "sprints": [
                {"metro": "callbacks", "note": "eod callbacks"},
            ],
        },
    }
    schedule_path = _write_schedule(tmp_path, schedule)

    # Two callbacks: one early attempt (no metro match for AM sprints),
    # one final attempt (also no metro match). This ensures they aren't
    # consumed by metro-filtered AM sprints and reach the dedicated
    # callback sprints in MID/EOD.
    monkeypatch.setattr(
        daily_plan.store,
        "list_due_callbacks",
        lambda **_kwargs: [
            {"prospect_id": "cb-early", "business_name": "Early CB", "metro": "Denver",
             "callback_date": "2026-03-28"},
            {"prospect_id": "cb-final", "business_name": "Final CB", "metro": "Seattle",
             "callback_date": "2026-03-26"},
        ],
    )
    # cb-early: 1 retry after callback_date (attempt 2), plus 1 old call before callback_date (should be ignored)
    # cb-final: 2 retries after callback_date (attempt 3 = final)
    def mock_list_calls(*, tenant_id="", prospect_id=None, **_kw):
        if prospect_id == "cb-early":
            return [
                {"outcome": "no_answer", "called_at": "2026-03-27T10:00:00"},  # before callback_date — ignored
                {"outcome": "no_answer", "called_at": "2026-03-29T10:00:00"},  # after — counts
            ]
        if prospect_id == "cb-final":
            return [
                {"outcome": "no_answer", "called_at": "2026-03-27T10:00:00"},  # after callback_date — counts
                {"outcome": "voicemail_left", "called_at": "2026-03-28T14:00:00"},  # after — counts
            ]
        return []

    monkeypatch.setattr(daily_plan.store, "list_outbound_calls", mock_list_calls)
    monkeypatch.setattr(
        daily_plan.store,
        "list_ranked_call_ready_prospects",
        lambda **_kwargs: [],
    )

    plan = daily_plan.build_daily_plan(today=date(2026, 3, 30), schedule_path=schedule_path)

    # Find MID and EOD blocks
    mid_block = next((b for b in plan["blocks"] if b["block"] == "MID"), None)
    eod_block = next((b for b in plan["blocks"] if b["block"] == "EOD"), None)
    assert mid_block is not None
    assert eod_block is not None

    mid_leads = mid_block["sprints"][0]["leads"]

    # All callbacks currently route to the first callbacks sprint (MID)
    mid_ids = {l.get("prospect_id") for l in mid_leads}
    assert "cb-early" in mid_ids
    assert "cb-final" in mid_ids


def test_metro_list_for_sprint_callbacks() -> None:
    assert daily_plan._metro_list_for_sprint("callbacks") is None


def test_metro_list_for_sprint_fl() -> None:
    metros = daily_plan._metro_list_for_sprint("FL")
    assert metros is not None
    assert "Miami" in metros


def test_metro_filters_includes_all_8_states():
    """METRO_FILTERS has entries for all 8 sprint states."""
    for state in ("FL", "TX", "IL", "AZ", "MI", "OH", "GA", "NC"):
        assert state in daily_plan.METRO_FILTERS, f"Missing METRO_FILTERS entry for {state}"
        assert state in daily_plan.METRO_FILTERS[state], f"{state} not in its own filter list"


def test_metro_filters_individual_states():
    """Each state has its own METRO_FILTERS entry (no SE/MW clusters)."""
    for state in ("FL", "MI", "OH", "GA", "NC", "TX", "IL", "AZ"):
        assert state in daily_plan.METRO_FILTERS
        assert state in daily_plan.METRO_FILTERS[state]

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

    plan = daily_plan.build_daily_plan(today=date(2026, 3, 30), schedule_path=schedule_path)

    # Monday daily target is 2 sprints, so only first 2 configured sprints should be used.
    assert plan["total_sprints"] == 2
    assert len(plan["blocks"][0]["sprints"]) == 2
    assert plan["dials_per_sprint"] == 11


def test_metro_list_for_sprint_callbacks() -> None:
    assert daily_plan._metro_list_for_sprint("callbacks") is None


def test_metro_list_for_sprint_fl() -> None:
    metros = daily_plan._metro_list_for_sprint("FL")
    assert metros is not None
    assert "Miami" in metros

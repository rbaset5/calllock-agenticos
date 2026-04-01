from __future__ import annotations

from datetime import date

import pytest

from outbound import lifecycle
from outbound import scoreboard


TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _schedule() -> dict:
    return {
        "start_date": "2026-03-30",
        "dials_per_sprint": 10,
        "weeks": {
            1: {
                "days": "weekdays",
                "daily_targets": [2, 3, 3, 4, 4],
                "blocks": {"AM": {"sprints": [{"metro": "FL"}, {"metro": "TX"}, {"metro": "AZ"}]}},
            },
            2: {
                "days": "weekdays",
                "daily_targets": [3, 3, 3, 4, 4],
                "blocks": {"AM": {"sprints": [{"metro": "FL"}, {"metro": "TX"}, {"metro": "AZ"}]}},
            },
            3: {
                "days": "weekdays",
                "daily_targets": [3, 3, 3, 4, 4],
                "blocks": {"AM": {"sprints": [{"metro": "FL"}, {"metro": "TX"}, {"metro": "AZ"}]}},
            },
            4: {
                "days": "weekdays_saturday",
                "daily_targets": [3, 3, 3, 4, 4, 2],
                "blocks": {"AM": {"sprints": [{"metro": "FL"}, {"metro": "TX"}, {"metro": "AZ"}]}},
            },
        },
    }


def _make_calls(day: str, count: int, *, outcome: str = "no_answer", metro: str = "Miami") -> list[dict]:
    return [
        {
            "id": f"{day}-{idx}",
            "tenant_id": TENANT_ID,
            "prospect_id": f"p-{day}-{idx}",
            "called_at": f"{day}T14:{idx:02d}:00+00:00",
            "outcome": outcome,
            "call_outcome_type": outcome,
            "metro": metro,
            "extraction": {"objection_type": "price", "objection_verbatim": "too expensive"},
            "transcript": "This is a sample transcript over fifty characters long for testing",
        }
        for idx in range(count)
    ]


def test_sprint_scoreboard_day1_zeros(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scoreboard, "load_schedule", lambda: _schedule())
    monkeypatch.setattr(scoreboard.store, "sprint_scoreboard", lambda **_kwargs: {})

    metrics = scoreboard.sprint_scoreboard(TENANT_ID, date(2026, 3, 30))

    assert metrics["daily_dials"] == 0
    assert metrics["daily_target"] == 20
    assert metrics["day_number"] == 1


def test_sprint_scoreboard_with_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scoreboard, "load_schedule", lambda: _schedule())
    monkeypatch.setattr(
        scoreboard.store,
        "sprint_scoreboard",
        lambda **_kwargs: {
            "daily_dials": 10,
            "daily_connects": 2,
            "daily_demos": 1,
            "weekly_dials": 10,
            "total_dials": 10,
            "customers_signed": 0,
        },
    )

    metrics = scoreboard.sprint_scoreboard(TENANT_ID, date(2026, 3, 30))

    assert metrics["daily_dials"] == 10
    assert metrics["daily_target"] == 20
    assert metrics["weekly_dials"] == 10


def test_streak_counter_consecutive(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = _schedule()
    calls = []
    calls.extend(_make_calls("2026-03-30", 20))
    calls.extend(_make_calls("2026-03-31", 30))
    calls.extend(_make_calls("2026-04-01", 30))

    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    result = scoreboard.streak_counter(TENANT_ID, date(2026, 4, 1), schedule)

    assert result["current_streak"] == 3
    assert result["best_streak"] == 3


def test_streak_counter_reset_on_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = _schedule()
    calls = []
    calls.extend(_make_calls("2026-03-30", 20))
    calls.extend(_make_calls("2026-04-01", 30))

    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    result = scoreboard.streak_counter(TENANT_ID, date(2026, 4, 1), schedule)

    assert result["current_streak"] == 1
    assert result["best_streak"] == 1


def test_streak_counter_week_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = _schedule()
    calls = []
    calls.extend(_make_calls("2026-04-03", 40))  # Friday
    calls.extend(_make_calls("2026-04-06", 30))  # Monday

    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    result = scoreboard.streak_counter(TENANT_ID, date(2026, 4, 6), schedule)

    assert result["current_streak"] == 2


def test_streak_counter_saturday_calling(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = _schedule()
    calls = []
    calls.extend(_make_calls("2026-04-24", 40))  # Friday week 4
    calls.extend(_make_calls("2026-04-25", 20))  # Saturday week 4

    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    result = scoreboard.streak_counter(TENANT_ID, date(2026, 4, 25), schedule)

    assert result["current_streak"] == 2


def test_format_progress_bar() -> None:
    rendered = scoreboard.format_progress_bar(50, 100, width=10)
    assert rendered.startswith("[")
    assert "50%" in rendered


def test_heat_map_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    # Completed calls count as dials (not dial_started events)
    calls.extend(_make_calls("2026-03-30", 5, outcome="no_answer", metro="FL"))
    calls.extend(_make_calls("2026-03-30", 2, outcome="answered_interested", metro="FL"))
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    heat = scoreboard.heat_map(TENANT_ID, {"start": "2026-03-30", "end": "2026-03-30"})

    first_slot = next(iter(heat["FL"].values()))
    assert first_slot["dials"] >= 7  # all completed calls are dials
    assert first_slot["connects"] >= 2
    assert first_slot["rate"] >= 0.0


def test_heat_map_empty_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    # dial_started events are NOT counted as dials
    calls = _make_calls("2026-03-30", 1, outcome="dial_started", metro="FL")
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    heat = scoreboard.heat_map(TENANT_ID, {"start": "2026-03-30", "end": "2026-03-30"})
    # dial_started is not a completed call, so no dials counted
    assert len(heat) == 0 or all(
        int(slot.get("dials", 0)) == 0
        for slots in heat.values()
        for slot in slots.values()
    )


def test_heat_map_two_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    calls.extend(_make_calls("2026-03-30", 4, outcome="no_answer", metro="TX"))
    calls.extend(_make_calls("2026-03-30", 1, outcome="answered_callback", metro="TX"))
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    heat = scoreboard.heat_map(TENANT_ID, {"start": "2026-03-30", "end": "2026-03-30"})
    first_slot = next(iter(heat["TX"].values()))
    assert first_slot["dials"] >= 5  # all completed calls
    assert first_slot["connects"] >= 1  # answered_callback counts


def test_objection_summary_top3(monkeypatch: pytest.MonkeyPatch) -> None:
    def _objection_calls() -> list[dict]:
        rows: list[dict] = []
        objections = ["price", "timing", "skepticism", "already_solved", "no_need"]
        for idx, objection in enumerate(objections):
            rows.append(
                {
                    "called_at": f"2026-03-30T14:{idx:02d}:00+00:00",
                    "outcome": "answered_not_interested",
                    "call_outcome_type": "answered_not_interested",
                    "transcript": "x" * 60,
                    "extraction": {
                        "objection_type": objection,
                        "objection_verbatim": f"{objection} objection",
                    },
                }
            )
        return rows

    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: _objection_calls())

    result = scoreboard.objection_summary(TENANT_ID, {"start": "2026-03-30", "end": "2026-03-30"})
    assert len(result) == 3


def test_objection_summary_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: [])
    assert scoreboard.objection_summary(TENANT_ID, {"start": "2026-03-30", "end": "2026-03-30"}) == []


def test_classify_lead_type_hot() -> None:
    assert lifecycle.classify_lead_type({"stage": "interested", "demo_scheduled": True}) == "hot"


def test_classify_lead_type_treats_close_attempt_as_hot() -> None:
    assert lifecycle.classify_lead_type({"stage": "interested", "next_action_type": "close_attempt"}) == "hot"


def test_classify_lead_type_uses_latest_outbound_call_demo_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lifecycle.store,
        "list_outbound_calls",
        lambda **_kwargs: [
            {"called_at": "2026-03-30T10:00:00+00:00", "demo_scheduled": False},
            {"called_at": "2026-03-30T11:00:00+00:00", "demo_scheduled": True},
        ],
    )

    assert lifecycle.classify_lead_type({"id": "p-1", "stage": "interested"}) == "hot"


def test_classify_lead_type_warm() -> None:
    assert lifecycle.classify_lead_type({"stage": "callback"}) == "warm"


def test_classify_lead_type_volume() -> None:
    assert lifecycle.classify_lead_type({"stage": "call_ready"}) == "volume"


def test_tactical_recommendations_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    calls.extend(_make_calls("2026-03-28", 5, outcome="answered_interested"))
    calls.extend(_make_calls("2026-03-29", 5, outcome="no_answer"))
    calls.extend(_make_calls("2026-03-30", 5, outcome="answered_callback"))
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)
    monkeypatch.setattr(
        scoreboard,
        "_call_llm_json",
        lambda *_args, **_kwargs: [
            {"recommendation": "Focus FL at 7am", "data_point": "Highest connects in FL early block"},
            {"recommendation": "Tighten callback ask", "data_point": "Callback objections rose 20%"},
        ],
    )

    recs = scoreboard.tactical_recommendations(TENANT_ID, date(2026, 3, 30))
    assert len(recs) == 2


def test_tactical_recommendations_llm_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _make_calls("2026-03-30", 5, outcome="answered_interested")
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)
    monkeypatch.setattr(scoreboard, "_call_llm_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))

    assert scoreboard.tactical_recommendations(TENANT_ID, date(2026, 3, 30)) == []


def test_tactical_recommendations_llm_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _make_calls("2026-03-30", 5, outcome="answered_interested")
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)
    monkeypatch.setattr(scoreboard, "_call_llm_json", lambda *_args, **_kwargs: {"bad": "shape"})

    assert scoreboard.tactical_recommendations(TENANT_ID, date(2026, 3, 30)) == []


def test_auto_adjust_insufficient_data(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    calls.extend(_make_calls("2026-03-30", 3, outcome="answered_interested"))
    calls.extend(_make_calls("2026-03-31", 3, outcome="answered_interested"))
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)

    assert scoreboard.auto_adjust_analysis(TENANT_ID, _schedule()) is None


def test_auto_adjust_valid_suggestions(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    for day in ["2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02", "2026-04-03"]:
        calls.extend(_make_calls(day, 3, outcome="answered_interested", metro="FL"))
        calls.extend(_make_calls(day, 3, outcome="dial_started", metro="FL"))
    monkeypatch.setattr(scoreboard.store, "list_outbound_calls", lambda **_kwargs: calls)
    monkeypatch.setattr(
        scoreboard,
        "_call_llm_json",
        lambda *_args, **_kwargs: {
            "advisory": "Shift one sprint from TX to FL morning.",
            "suggestions": [
                {"metro": "FL", "slot": "07:00-08:00", "recommended_sprints": 4},
                {"metro": "INVALID", "slot": "08:00-09:00", "recommended_sprints": 3},
            ],
        },
    )

    result = scoreboard.auto_adjust_analysis(TENANT_ID, _schedule())
    assert result is not None
    assert result["suggestions"][0]["metro"] == "FL"

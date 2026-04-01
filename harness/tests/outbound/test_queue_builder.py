from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from outbound import queue_builder


def _prospect(
    prospect_id: str,
    *,
    stage: str,
    metro: str,
    next_action_type: str | None = None,
    next_action_date: str | None = None,
    last_touched_hours_ago: int | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": prospect_id,
        "business_name": prospect_id,
        "stage": stage,
        "metro": metro,
        "phone": "+15550000000",
        "prospect_signals": [],
        "call_tests": [],
    }
    if next_action_type is not None:
        row["next_action_type"] = next_action_type
    if next_action_date is not None:
        row["next_action_date"] = next_action_date
    if last_touched_hours_ago is not None:
        row["last_touched_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=last_touched_hours_ago)
        ).isoformat()
    return row


def test_build_queue_prioritizes_callbacks_then_interested_then_follow_up_then_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        queue_builder.store,
        "list_due_callbacks",
        lambda **_kwargs: [{"prospect_id": "cb-1", "business_name": "Callback One", "stage": "callback"}],
    )
    monkeypatch.setattr(
        queue_builder.store,
        "list_prospects_by_stages",
        lambda **_kwargs: [
            _prospect("int-1", stage="interested", metro="Dallas", next_action_type="close_attempt"),
            _prospect("follow-1", stage="callback", metro="Dallas", next_action_date="2026-04-14"),
            _prospect("fresh-1", stage="call_ready", metro="Dallas"),
        ],
    )
    monkeypatch.setattr(queue_builder.store, "list_today_dial_prospect_ids", lambda **_kwargs: set())

    queue = queue_builder.build_queue(block="AM", segment="TX")

    assert [prospect["id"] for prospect in queue["prospects"]] == [
        "cb-1",
        "int-1",
        "follow-1",
        "fresh-1",
    ]
    assert queue["breakdown"] == {
        "callbacks_due": 1,
        "interested": 1,
        "callback_stage": 1,
        "fresh": 1,
    }


def test_build_queue_filters_fresh_leads_to_active_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(queue_builder.store, "list_due_callbacks", lambda **_kwargs: [])
    monkeypatch.setattr(
        queue_builder.store,
        "list_prospects_by_stages",
        lambda **_kwargs: [
            _prospect("fresh-tx", stage="call_ready", metro="Dallas"),
            _prospect("fresh-fl", stage="call_ready", metro="Miami"),
        ],
    )
    monkeypatch.setattr(queue_builder.store, "list_today_dial_prospect_ids", lambda **_kwargs: set())

    queue = queue_builder.build_queue(block="AM", segment="TX")

    assert [prospect["id"] for prospect in queue["prospects"]] == ["fresh-tx"]
    assert queue["summary"] == "0 callbacks, 0 interested, 0 follow-up, 1 fresh"


def test_build_queue_excludes_already_dialed_prospects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        queue_builder.store,
        "list_due_callbacks",
        lambda **_kwargs: [{"prospect_id": "cb-1", "business_name": "Callback One", "stage": "callback"}],
    )
    monkeypatch.setattr(
        queue_builder.store,
        "list_prospects_by_stages",
        lambda **_kwargs: [
            _prospect("int-1", stage="interested", metro="Dallas"),
            _prospect("fresh-1", stage="call_ready", metro="Dallas"),
        ],
    )
    monkeypatch.setattr(
        queue_builder.store,
        "list_today_dial_prospect_ids",
        lambda **_kwargs: {"cb-1", "fresh-1"},
    )

    queue = queue_builder.build_queue(block="AM", segment="TX")

    assert [prospect["id"] for prospect in queue["prospects"]] == ["int-1"]
    assert queue["already_dialed_today"] == 2


def test_build_queue_marks_needs_attention_for_stale_or_missing_next_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue_builder.store, "list_due_callbacks", lambda **_kwargs: [])
    monkeypatch.setattr(
        queue_builder.store,
        "list_prospects_by_stages",
        lambda **_kwargs: [
            _prospect("int-missing", stage="interested", metro="Dallas"),
            _prospect("cb-stale", stage="callback", metro="Dallas", next_action_date="2026-04-10", last_touched_hours_ago=72),
            _prospect("fresh-1", stage="call_ready", metro="Dallas"),
        ],
    )
    monkeypatch.setattr(queue_builder.store, "list_today_dial_prospect_ids", lambda **_kwargs: set())

    queue = queue_builder.build_queue(block="AM", segment="TX")
    indexed = {prospect["id"]: prospect for prospect in queue["prospects"]}

    assert indexed["int-missing"]["needs_attention"] is True
    assert indexed["cb-stale"]["needs_attention"] is True
    assert indexed["fresh-1"]["needs_attention"] is False


def test_build_queue_block_all_returns_per_block_queues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(queue_builder.store, "list_due_callbacks", lambda **_kwargs: [])
    monkeypatch.setattr(queue_builder.store, "list_prospects_by_stages", lambda **_kwargs: [])
    monkeypatch.setattr(queue_builder.store, "list_today_dial_prospect_ids", lambda **_kwargs: set())
    monkeypatch.setattr(
        queue_builder.sprint_state,
        "get_current_state",
        lambda **_kwargs: {
            "all_blocks": [
                {"block": "AM", "segments": ["FL", "TX"]},
                {"block": "MID", "segments": ["callbacks", "warm_callbacks"]},
            ]
        },
    )

    queue = queue_builder.build_queue(block="all")

    assert [entry["block"] for entry in queue["queues"]] == ["AM", "MID"]

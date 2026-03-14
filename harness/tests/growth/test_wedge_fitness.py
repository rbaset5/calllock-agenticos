from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db import local_repository
from growth.attribution.tokens import mint_token
from growth.engine.wedge_fitness import compute_and_persist_wedge_fitness, compute_wedge_fitness
from growth.idempotency.keys import monday_snapshot_week
from growth.memory import repository as growth_repository


def _seed_wedge_inputs(monkeypatch, *, deep_conversion_count: int) -> datetime:
    now = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
    tenant_id = "tenant-alpha"

    contacted = []
    conversions = []
    for index in range(20):
        prospect_id = f"prospect-{index}"
        contacted.append(
            {
                "touchpoint_id": f"tp-email-{index}",
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "touchpoint_type": "email_sent",
                "created_at": (now - timedelta(days=7)).isoformat(),
                "wedge_id": "hvac",
            }
        )
        conversions.append(
            {
                "touchpoint_id": f"tp-meeting-{index}",
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "touchpoint_type": "meeting_booked",
                "attribution_token": mint_token(tenant_id, prospect_id, issued_at=int((now - timedelta(days=7)).timestamp())),
                "created_at": (now - timedelta(days=6)).isoformat(),
                "wedge_id": "hvac",
            }
        )
    pilot_started = [
        {
            "touchpoint_id": "tp-pilot-1",
            "tenant_id": tenant_id,
            "prospect_id": "prospect-0",
            "touchpoint_type": "pilot_started",
            "created_at": (now - timedelta(days=5)).isoformat(),
            "wedge_id": "hvac",
        }
    ]
    touchpoints = contacted + conversions + pilot_started

    belief_events = [
        {
            "belief_event_id": f"be-{index}-{shift}",
            "tenant_id": tenant_id,
            "prospect_id": f"prospect-{index}",
            "source_touchpoint_id": f"tp-source-{index}-{shift}",
            "touchpoint_type": "email_replied",
            "belief_shift": "up",
            "confidence": 0.8,
            "created_at": (now - timedelta(days=5)).isoformat(),
        }
        for index in range(deep_conversion_count)
        for shift in (1, 2)
    ]

    segment_rows = [
        {
            "tenant_id": tenant_id,
            "wedge_id": "hvac",
            "proof_asset": f"proof-{index}",
            "sample_size": 8,
            "conversion_rate": 0.2,
            "created_at": (now - timedelta(days=10)).isoformat(),
        }
        for index in range(5)
    ]
    experiments = [
        {
            "experiment_id": "00000000-0000-0000-0000-00000000e101",
            "tenant_id": tenant_id,
            "wedge_id": "hvac",
            "status": "winner_declared",
            "created_at": (now - timedelta(days=35)).isoformat(),
            "winner_declared_at": (now - timedelta(days=20)).isoformat(),
        },
        {
            "experiment_id": "00000000-0000-0000-0000-00000000e102",
            "tenant_id": tenant_id,
            "wedge_id": "hvac",
            "status": "winner_declared",
            "created_at": (now - timedelta(days=30)).isoformat(),
            "winner_declared_at": (now - timedelta(days=18)).isoformat(),
        },
    ]
    cost_rows = [
        {
            "tenant_id": tenant_id,
            "created_at": (now - timedelta(days=days)).isoformat(),
            "total_cost_per_meeting": cost,
            "wedge_id": "hvac",
        }
        for days, cost in ((28, 100), (21, 90), (14, 85), (7, 80))
    ]
    insights = [
        {
            "tenant_id": tenant_id,
            "review_status": "approved",
            "created_at": (now - timedelta(days=3)).isoformat(),
        }
        for _ in range(10)
    ]

    monkeypatch.setattr(growth_repository, "list_touchpoints", lambda *, tenant_id, touchpoint_type=None: touchpoints)
    monkeypatch.setattr(growth_repository, "list_belief_events", lambda *, tenant_id: belief_events)
    monkeypatch.setattr(growth_repository, "list_segment_performance", lambda *, tenant_id: segment_rows)
    monkeypatch.setattr(growth_repository, "list_experiment_history", lambda *, tenant_id: experiments)
    monkeypatch.setattr(growth_repository, "list_cost_per_acquisition", lambda *, tenant_id: cost_rows)
    monkeypatch.setattr(growth_repository, "list_insights", lambda *, tenant_id: insights)
    monkeypatch.setattr(growth_repository, "list_founder_overrides", lambda *, tenant_id: [])
    monkeypatch.setattr(growth_repository, "list_loss_records", lambda *, tenant_id: [{"loss_id": f"loss-{idx}"} for idx in range(35)])
    return now


def test_wedge_fitness_preserves_belief_depth_hard_cliff(monkeypatch) -> None:
    now = _seed_wedge_inputs(monkeypatch, deep_conversion_count=7)
    below = compute_wedge_fitness(
        "tenant-alpha",
        "hvac",
        context={"retention_quality_raw": 0.9, "doctrine_stable_weeks": 3, "pricing_experiment_completed": True, "price_loss_ratio": 0.3},
        now=now,
    )
    assert below.component_scores["belief_depth"]["raw"] == 0.35
    assert below.component_scores["belief_depth"]["score"] == 87.5
    assert below.gates_status["closed_loop_eligible"] is False

    now = _seed_wedge_inputs(monkeypatch, deep_conversion_count=8)
    at_threshold = compute_wedge_fitness(
        "tenant-alpha",
        "hvac",
        context={"retention_quality_raw": 0.9, "doctrine_stable_weeks": 3, "pricing_experiment_completed": True, "price_loss_ratio": 0.3},
        now=now,
    )
    assert at_threshold.component_scores["belief_depth"]["raw"] == 0.4
    assert at_threshold.component_scores["belief_depth"]["score"] == 100.0
    assert at_threshold.gates_status["closed_loop_eligible"] is True


def test_same_snapshot_week_upserts_instead_of_duplicating(monkeypatch) -> None:
    now = _seed_wedge_inputs(monkeypatch, deep_conversion_count=8)

    first = compute_and_persist_wedge_fitness(
        "tenant-alpha",
        "hvac",
        source_version="growth-tests-v1",
        context={"retention_quality_raw": 0.9, "doctrine_stable_weeks": 3, "pricing_experiment_completed": True, "price_loss_ratio": 0.3},
        now=now,
    )
    second = compute_and_persist_wedge_fitness(
        "tenant-alpha",
        "hvac",
        source_version="growth-tests-v2",
        context={"retention_quality_raw": 0.95, "doctrine_stable_weeks": 4, "pricing_experiment_completed": True, "price_loss_ratio": 0.3},
        now=now + timedelta(hours=2),
    )

    rows = local_repository._state()["wedge_fitness_snapshots"]
    assert len(rows) == 1
    assert first["snapshot_week"] == monday_snapshot_week(now).isoformat()
    assert second["snapshot_week"] == monday_snapshot_week(now).isoformat()
    assert rows[0]["source_version"] == "growth-tests-v2"
    latest = growth_repository.get_latest_wedge_fitness_snapshot(tenant_id="tenant-alpha", wedge="hvac")
    assert latest is not None
    assert latest["source_version"] == "growth-tests-v2"

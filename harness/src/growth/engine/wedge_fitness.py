from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any

from growth.attribution.tokens import validate_token
from growth.idempotency.keys import monday_snapshot_week
from growth.memory.models import InvalidAttributionTokenError, WedgeFitnessResult
from growth.memory import repository as growth_repository


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _within(days: int, now: datetime, value: str | None) -> bool:
    parsed = _parse_dt(value)
    if parsed is None:
        return False
    return parsed >= now - timedelta(days=days)


def _piecewise(raw: float, points: list[tuple[float, float]]) -> float:
    if raw <= points[0][0]:
        return points[0][1]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if raw <= x2:
            if x2 == x1:
                return y2
            ratio = (raw - x1) / (x2 - x1)
            return y1 + ((y2 - y1) * ratio)
    return points[-1][1]


def _clamp(score: float) -> float:
    return max(0.0, min(100.0, round(score, 2)))


def _cold(score_name: str) -> dict[str, Any]:
    return {"score": 50.0, "cold_start": True, "raw": None, "name": score_name}


def _filter_wedge(records: list[dict[str, Any]], wedge: str) -> list[dict[str, Any]]:
    filtered = []
    for record in records:
        if record.get("wedge_id") == wedge or record.get("wedge") == wedge:
            filtered.append(record)
            continue
        metadata = record.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("wedge") == wedge:
            filtered.append(record)
            continue
        if not record.get("wedge_id") and not record.get("wedge") and not metadata.get("wedge"):
            filtered.append(record)
    return filtered


def _booked_pilot_score(touchpoints: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    window = [row for row in touchpoints if _within(28, now, row.get("created_at"))]
    contacted = {row["prospect_id"] for row in window if str(row.get("touchpoint_type", "")).startswith("email_sent")}
    if len(contacted) < 5:
        return _cold("booked_pilot_rate")
    started = {row["prospect_id"] for row in window if row.get("touchpoint_type") == "pilot_started"}
    raw = len(started) / max(len(contacted), 1)
    return {"score": _clamp(min(100.0, raw / 0.04 * 100.0)), "cold_start": False, "raw": raw, "name": "booked_pilot_rate"}


def _attribution_score(touchpoints: list[dict[str, Any]], tenant_id: str, now: datetime) -> dict[str, Any]:
    conversions = [
        row
        for row in touchpoints
        if _within(28, now, row.get("created_at")) and row.get("touchpoint_type") in {"meeting_booked", "pilot_started"}
    ]
    if len(conversions) < 5:
        return _cold("attribution_completeness")
    valid = 0
    for row in conversions:
        token = row.get("attribution_token")
        if not token:
            continue
        try:
            validate_token(str(token), tenant_id, now=int(now.timestamp()))
        except InvalidAttributionTokenError:
            continue
        valid += 1
    raw = valid / max(len(conversions), 1)
    score = _piecewise(raw, [(0.0, 0.0), (0.4, 10.0), (0.6, 30.0), (0.8, 60.0), (0.9, 80.0), (0.95, 100.0)])
    if raw < 0.4:
        score = 0.0
    return {"score": _clamp(score), "cold_start": False, "raw": raw, "name": "attribution_completeness"}


def _proof_coverage_score(segment_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in segment_rows if row.get("proof_asset")]
    if len(rows) < 5:
        return _cold("proof_coverage")
    covered = [row for row in rows if int(row.get("sample_size", 0)) >= 5 and float(row.get("conversion_rate", 0)) > 0]
    raw = len(covered) / max(len(rows), 1)
    return {"score": _clamp(_piecewise(raw, [(0.0, 0.0), (0.3, 25.0), (0.5, 50.0), (0.7, 75.0), (0.9, 100.0)])), "cold_start": False, "raw": raw, "name": "proof_coverage"}


def _founder_alignment_score(insights: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> dict[str, Any]:
    total = [row for row in insights if row.get("review_status") in {"approved", "rejected"}]
    if len(total) < 5:
        return _cold("founder_alignment")
    rejected = [row for row in overrides if row.get("override_action") == "rejected"]
    raw = 1.0 - (len(rejected) / max(len(total), 1))
    return {"score": _clamp(_piecewise(raw, [(0.0, 0.0), (0.5, 25.0), (0.7, 50.0), (0.85, 75.0), (0.95, 100.0)])), "cold_start": False, "raw": raw, "name": "founder_alignment"}


def _learning_velocity_score(experiments: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    winner_rows = [
        row
        for row in experiments
        if row.get("status") == "winner_declared" and _within(90, now, row.get("winner_declared_at"))
    ]
    if len(winner_rows) < 2:
        return _cold("learning_velocity")
    durations = []
    for row in winner_rows:
        created_at = _parse_dt(row.get("created_at"))
        declared_at = _parse_dt(row.get("winner_declared_at"))
        if created_at and declared_at:
            durations.append((declared_at - created_at).total_seconds() / 86400)
    if len(durations) < 2:
        return _cold("learning_velocity")
    median_days = median(durations)
    score = max(0.0, min(100.0, ((60 - median_days) / 46) * 100.0))
    return {"score": _clamp(score), "cold_start": False, "raw": median_days, "name": "learning_velocity"}


def _retention_quality_score(context: dict[str, Any]) -> dict[str, Any]:
    if "retention_quality_raw" not in context:
        return _cold("retention_quality")
    raw = float(context["retention_quality_raw"])
    return {"score": _clamp(_piecewise(raw, [(0.0, 0.0), (0.6, 25.0), (0.7, 50.0), (0.8, 75.0), (0.9, 100.0)])), "cold_start": False, "raw": raw, "name": "retention_quality"}


def _segment_clarity_score(touchpoints: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    window = [row for row in touchpoints if _within(28, now, row.get("created_at"))]
    prospects = {row["prospect_id"] for row in window}
    if len(prospects) < 5:
        return _cold("segment_clarity")
    oscillated = {row["prospect_id"] for row in window if row.get("touchpoint_type") == "segment_reassigned"}
    raw = 1.0 - (len(oscillated) / max(len(prospects), 1))
    return {"score": _clamp(_piecewise(raw, [(0.0, 0.0), (0.8, 25.0), (0.85, 50.0), (0.9, 75.0), (0.95, 100.0)])), "cold_start": False, "raw": raw, "name": "segment_clarity"}


def _cost_efficiency_score(cost_rows: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    weekly: dict[date, list[float]] = {}
    for row in cost_rows:
        if not _within(28, now, row.get("created_at")):
            continue
        value = row.get("total_cost_per_meeting")
        created_at = _parse_dt(row.get("created_at"))
        if value is None or created_at is None:
            continue
        week = monday_snapshot_week(created_at)
        weekly.setdefault(week, []).append(float(value))
    weeks = sorted(weekly)
    if len(weeks) < 4:
        return _cold("cost_efficiency")
    averages = [sum(weekly[week]) / len(weekly[week]) for week in weeks[-4:]]
    first = averages[0]
    last = averages[-1]
    if first == 0:
        return _cold("cost_efficiency")
    trend = (last - first) / first
    score = _piecewise(trend, [(-0.2, 100.0), (-0.1, 75.0), (0.0, 50.0), (0.1, 25.0), (0.2, 0.0)])
    return {"score": _clamp(score), "cold_start": False, "raw": trend, "name": "cost_efficiency"}


def _belief_depth_score(touchpoints: list[dict[str, Any]], belief_events: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    conversions = {
        row["prospect_id"]
        for row in touchpoints
        if _within(28, now, row.get("created_at")) and row.get("touchpoint_type") in {"meeting_booked", "pilot_started"}
    }
    if len(conversions) < 5:
        return _cold("belief_depth")
    counts = Counter(
        row["prospect_id"]
        for row in belief_events
        if row.get("prospect_id") in conversions and row.get("belief_shift") in {"up", "down"}
    )
    deep = sum(1 for prospect_id in conversions if counts[prospect_id] >= 2)
    raw = deep / max(len(conversions), 1)
    return {"score": _clamp(_piecewise(raw, [(0.0, 0.0), (0.1, 25.0), (0.2, 50.0), (0.3, 75.0), (0.4, 100.0)])), "cold_start": False, "raw": raw, "name": "belief_depth"}


def compute_wedge_fitness(
    tenant_id: str,
    wedge: str,
    *,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> WedgeFitnessResult:
    runtime = now or datetime.now(timezone.utc)
    config = context or {}
    touchpoints = _filter_wedge(growth_repository.list_touchpoints(tenant_id=tenant_id), wedge)
    segment_rows = _filter_wedge(growth_repository.list_segment_performance(tenant_id=tenant_id), wedge)
    experiments = _filter_wedge(growth_repository.list_experiment_history(tenant_id=tenant_id), wedge)
    cost_rows = _filter_wedge(growth_repository.list_cost_per_acquisition(tenant_id=tenant_id), wedge)
    belief_events = growth_repository.list_belief_events(tenant_id=tenant_id)
    insights = growth_repository.list_insights(tenant_id=tenant_id)
    overrides = growth_repository.list_founder_overrides(tenant_id=tenant_id)

    component_details = {
        "booked_pilot_rate": _booked_pilot_score(touchpoints, runtime),
        "attribution_completeness": _attribution_score(touchpoints, tenant_id, runtime),
        "proof_coverage": _proof_coverage_score(segment_rows),
        "founder_alignment": _founder_alignment_score(insights, overrides),
        "learning_velocity": _learning_velocity_score(experiments, runtime),
        "retention_quality": _retention_quality_score(config),
        "segment_clarity": _segment_clarity_score(touchpoints, runtime),
        "cost_efficiency": _cost_efficiency_score(cost_rows, runtime),
        "belief_depth": _belief_depth_score(touchpoints, belief_events, runtime),
    }
    weights = {
        "booked_pilot_rate": 0.15,
        "attribution_completeness": 0.15,
        "proof_coverage": 0.15,
        "founder_alignment": 0.10,
        "learning_velocity": 0.10,
        "retention_quality": 0.10,
        "segment_clarity": 0.10,
        "cost_efficiency": 0.10,
        "belief_depth": 0.05,
    }
    score = round(sum(component_details[name]["score"] * weight for name, weight in weights.items()), 2)
    founder_override_rate = config.get("founder_override_rate")
    if founder_override_rate is None:
        total_reviews = len([row for row in insights if row.get("review_status") in {"approved", "rejected"}])
        founder_override_rate = len([row for row in overrides if row.get("override_action") == "rejected"]) / max(total_reviews, 1) if total_reviews else 1.0
    gate_context = {
        "doctrine_stable_weeks": int(config.get("doctrine_stable_weeks", 0)),
        "founder_override_rate": float(founder_override_rate),
        "pricing_experiment_completed": bool(config.get("pricing_experiment_completed", False)),
        "loss_records_count": int(config.get("loss_records_count", len(growth_repository.list_loss_records(tenant_id=tenant_id)))),
        "price_loss_ratio": float(config.get("price_loss_ratio", 0.0)),
    }
    gates_status = {
        "automation_eligible": (
            score >= 40
            and component_details["attribution_completeness"]["score"] >= 60
            and component_details["proof_coverage"]["score"] >= 50
            and gate_context["doctrine_stable_weeks"] >= 2
        ),
        "closed_loop_eligible": (
            score >= 60
            and component_details["belief_depth"]["score"] >= 100
            and gate_context["founder_override_rate"] < 0.4
        ),
        "expansion_eligible": (
            score >= 75
            and component_details["retention_quality"]["score"] >= 50
            and gate_context["pricing_experiment_completed"]
        ),
        "pricing_experiment_eligible": (
            score >= 50
            and gate_context["loss_records_count"] >= 30
            and gate_context["price_loss_ratio"] >= 0.2
        ),
    }
    blocking_gaps: list[str] = []
    if not gates_status["automation_eligible"]:
        if score < 40:
            blocking_gaps.append("automation: composite_below_40")
        if component_details["attribution_completeness"]["score"] < 60:
            blocking_gaps.append("automation: attribution_below_threshold")
        if component_details["proof_coverage"]["score"] < 50:
            blocking_gaps.append("automation: proof_coverage_below_threshold")
        if gate_context["doctrine_stable_weeks"] < 2:
            blocking_gaps.append("automation: doctrine_not_stable")
    if not gates_status["closed_loop_eligible"]:
        if score < 60:
            blocking_gaps.append("closed_loop: composite_below_60")
        if component_details["belief_depth"]["score"] < 100:
            blocking_gaps.append("closed_loop: belief_depth_below_0_40")
        if gate_context["founder_override_rate"] >= 0.4:
            blocking_gaps.append("closed_loop: founder_override_rate_too_high")
    if not gates_status["expansion_eligible"]:
        if score < 75:
            blocking_gaps.append("expansion: composite_below_75")
        if component_details["retention_quality"]["score"] < 50:
            blocking_gaps.append("expansion: retention_quality_below_threshold")
        if not gate_context["pricing_experiment_completed"]:
            blocking_gaps.append("expansion: pricing_experiment_missing")
    if not gates_status["pricing_experiment_eligible"]:
        if score < 50:
            blocking_gaps.append("pricing: composite_below_50")
        if gate_context["loss_records_count"] < 30:
            blocking_gaps.append("pricing: insufficient_loss_records")
        if gate_context["price_loss_ratio"] < 0.2:
            blocking_gaps.append("pricing: price_loss_ratio_below_threshold")
    return WedgeFitnessResult(
        wedge=wedge,
        snapshot_week=monday_snapshot_week(runtime),
        score=score,
        component_scores=component_details,
        gates_status=gates_status,
        blocking_gaps=blocking_gaps,
        launch_recommendation="launch" if gates_status["automation_eligible"] else "hold",
    )


def compute_and_persist_wedge_fitness(
    tenant_id: str,
    wedge: str,
    *,
    source_version: str,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    result = compute_wedge_fitness(tenant_id, wedge, context=context, now=now)
    payload = {
        "tenant_id": tenant_id,
        "wedge": wedge,
        "snapshot_week": result.snapshot_week.isoformat(),
        "score": result.score,
        "component_scores": result.component_scores,
        "gates_status": result.gates_status,
        "blocking_gaps": result.blocking_gaps,
        "launch_recommendation": result.launch_recommendation,
        "source_version": source_version,
        "computed_at": (now or datetime.now(timezone.utc)).isoformat(),
    }
    return growth_repository.upsert_wedge_fitness_snapshot(payload)

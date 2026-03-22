from __future__ import annotations

import hashlib
import json
from typing import Any

from . import store
from .constants import DISPATCH_SCORE_WEIGHTS, OUTBOUND_TENANT_ID, TIER_THRESHOLDS


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "active"}
    return False


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_signal_rows(raw_source: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    if _truthy(raw_source.get("is_spending_on_ads")):
        signals.append(
            {
                "signal_type": "paid_demand",
                "signal_tier": 1,
                "score": DISPATCH_SCORE_WEIGHTS["paid_demand"],
                "raw_evidence": {"is_spending_on_ads": raw_source.get("is_spending_on_ads")},
            }
        )

    workday_timing = str(raw_source.get("workday_timing") or "").lower()
    if workday_timing and any(flag in workday_timing for flag in ("weekday", "daytime", "business hours", "8-5")):
        signals.append(
            {
                "signal_type": "hours_mismatch",
                "signal_tier": 2,
                "score": DISPATCH_SCORE_WEIGHTS["hours"],
                "raw_evidence": {"workday_timing": raw_source.get("workday_timing")},
            }
        )

    reviews = _number(raw_source.get("reviews") or raw_source.get("review_count"))
    rating = _number(raw_source.get("rating"))
    if (rating is not None and rating < 4.2) or (reviews is not None and reviews < 20):
        signals.append(
            {
                "signal_type": "review_pain",
                "signal_tier": 3,
                "score": DISPATCH_SCORE_WEIGHTS["review_pain"],
                "raw_evidence": {"reviews": reviews, "rating": rating},
            }
        )

    is_franchise = raw_source.get("is_franchise")
    owner_name = raw_source.get("owner_name_found") or raw_source.get("owner_name")
    if not _truthy(is_franchise) and owner_name:
        signals.append(
            {
                "signal_type": "owner_operated",
                "signal_tier": 2,
                "score": DISPATCH_SCORE_WEIGHTS["owner_operated"],
                "raw_evidence": {"is_franchise": is_franchise, "owner_name": owner_name},
            }
        )

    if raw_source.get("admin_count") in {0, "0"} or raw_source.get("has_dispatcher") in {False, "false", "False"}:
        signals.append(
            {
                "signal_type": "no_admin_layer",
                "signal_tier": 2,
                "score": DISPATCH_SCORE_WEIGHTS["owner_operated"],
                "raw_evidence": {
                    "admin_count": raw_source.get("admin_count"),
                    "has_dispatcher": raw_source.get("has_dispatcher"),
                },
            }
        )

    if raw_source.get("backup_intake") in {False, "false", "False"} or raw_source.get("after_hours_answering") in {False, "false", "False"}:
        signals.append(
            {
                "signal_type": "no_backup_intake",
                "signal_tier": 1,
                "score": DISPATCH_SCORE_WEIGHTS["backup_intake"],
                "raw_evidence": {
                    "backup_intake": raw_source.get("backup_intake"),
                    "after_hours_answering": raw_source.get("after_hours_answering"),
                },
            }
        )

    return signals


def compute_dimension_scores(signals: list[dict[str, Any]]) -> dict[str, int]:
    scores = {
        "paid_demand": 0,
        "after_hours": 0,
        "backup_intake": 0,
        "hours": 0,
        "owner_operated": 0,
        "review_pain": 0,
    }
    for signal in signals:
        signal_type = signal["signal_type"]
        if signal_type == "paid_demand":
            scores["paid_demand"] = max(scores["paid_demand"], int(signal["score"]))
        elif signal_type == "after_hours_behavior":
            scores["after_hours"] = max(scores["after_hours"], int(signal["score"]))
        elif signal_type == "no_backup_intake":
            scores["backup_intake"] = max(scores["backup_intake"], int(signal["score"]))
        elif signal_type == "hours_mismatch":
            scores["hours"] = max(scores["hours"], int(signal["score"]))
        elif signal_type in {"owner_operated", "no_admin_layer"}:
            scores["owner_operated"] = max(scores["owner_operated"], int(signal["score"]))
        elif signal_type == "review_pain":
            scores["review_pain"] = max(scores["review_pain"], int(signal["score"]))
    return scores


def compute_total_score(dimension_scores: dict[str, int]) -> int:
    return min(100, sum(int(value) for value in dimension_scores.values()))


def classify_tier(total_score: int) -> str:
    if total_score >= TIER_THRESHOLDS["a_lead"]:
        return "a_lead"
    if total_score >= TIER_THRESHOLDS["b_lead"]:
        return "b_lead"
    if total_score >= TIER_THRESHOLDS["c_lead"]:
        return "c_lead"
    return "disqualified"


def rubric_hash() -> str:
    payload = {
        "weights": DISPATCH_SCORE_WEIGHTS,
        "thresholds": TIER_THRESHOLDS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def score_prospects(prospect_ids: list[str] | None = None) -> dict[str, int]:
    prospects = store.list_outbound_prospects(
        tenant_id=OUTBOUND_TENANT_ID,
        stages=["discovered", "validated"] if prospect_ids is None else None,
        prospect_ids=prospect_ids,
    )

    summary = {"scored": 0, "a_leads": 0, "b_leads": 0, "c_leads": 0, "disqualified": 0}
    rubric = rubric_hash()

    for prospect in prospects:
        raw_source = prospect.get("raw_source") or {}
        signals = extract_signal_rows(raw_source)
        for signal in signals:
            store.insert_prospect_signal(
                {
                    "tenant_id": OUTBOUND_TENANT_ID,
                    "prospect_id": prospect["id"],
                    **signal,
                }
            )

        dimensions = compute_dimension_scores(signals)
        total = compute_total_score(dimensions)
        tier = classify_tier(total)
        store.insert_prospect_score(
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "prospect_id": prospect["id"],
                "dimension_scores": dimensions,
                "total_score": total,
                "tier": tier,
                "rubric_hash": rubric,
            }
        )
        store.update_outbound_prospect(
            prospect["id"],
            {
                "total_score": total,
                "score_tier": tier,
                "stage": "scored",
            },
        )
        summary["scored"] += 1
        if tier == "disqualified":
            summary["disqualified"] += 1
        else:
            summary[f"{tier}s"] += 1

    return summary

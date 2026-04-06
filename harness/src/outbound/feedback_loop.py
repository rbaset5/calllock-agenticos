"""Feedback loop: track call outcomes → retrain scoring weights.

Measures which scoring signals actually predict "interested" prospects,
suggests weight adjustments, and tracks model performance over time.

Usage:
    python -m outbound.feedback_loop [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from . import store
from .constants import DISPATCH_SCORE_WEIGHTS, OUTBOUND_TENANT_ID, REVIEW_SIGNAL_WEIGHTS
from .scoring import rubric_hash

# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

POSITIVE_OUTCOMES = {"answered_interested"}
POSITIVE_STAGES = {"converted"}
NEGATIVE_OUTCOMES = {"answered_not_interested", "wrong_number", "gatekeeper_blocked"}

MIN_CONCLUSIVE_OUTCOMES = 20
BAYESIAN_ALPHA = 1  # Beta(1,1) uniform prior
BAYESIAN_BETA = 1


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SignalEffectiveness:
    dimension: str
    total_with_signal: int
    positive_with_signal: int
    total_without_signal: int
    positive_without_signal: int
    raw_precision: float
    smoothed_precision: float
    lift: float
    coverage: float


@dataclass
class TierAccuracy:
    tier: str
    total: int
    positive: int
    negative: int
    precision: float


@dataclass
class FeedbackReport:
    total_analyzed: int
    positive_count: int
    negative_count: int
    inconclusive_count: int
    base_rate: float
    min_sample_met: bool
    rubric_hash: str
    dimension_metrics: list[SignalEffectiveness]
    tier_accuracy: list[TierAccuracy]
    current_weights: dict[str, int]
    suggested_weights: dict[str, int]
    review_signal_metrics: list[SignalEffectiveness] | None
    discrimination_score: float | None


# ---------------------------------------------------------------------------
# Label assignment
# ---------------------------------------------------------------------------


def _best_label(outcomes: list[str], stage: str | None = None) -> str:
    """Determine prospect label from all their call outcomes.

    Priority: positive > negative > inconclusive.
    A prospect called 3x who was no_answer twice then answered_interested
    once is labeled positive.
    """
    outcome_set = set(outcomes)
    if outcome_set & POSITIVE_OUTCOMES or stage in POSITIVE_STAGES:
        return "positive"
    if outcome_set & NEGATIVE_OUTCOMES:
        return "negative"
    return "inconclusive"


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def collect_training_data(
    *, tenant_id: str = OUTBOUND_TENANT_ID,
) -> list[dict[str, Any]]:
    """Join called prospects with their scores and call outcomes.

    Four bulk queries, in-memory join by prospect_id.  Returns one record
    per prospect that has at least one outbound call.
    """
    prospects = store.list_outbound_prospects(tenant_id=tenant_id)
    all_calls = store.list_outbound_calls(tenant_id=tenant_id)
    all_scores = store.list_prospect_scores(tenant_id=tenant_id)

    # Group calls by prospect_id
    calls_by_pid: dict[str, list[dict]] = defaultdict(list)
    for call in all_calls:
        pid = call.get("prospect_id")
        if pid:
            calls_by_pid[pid].append(call)

    # Latest score per prospect_id
    scores_by_pid: dict[str, dict] = {}
    for score in all_scores:
        pid = score.get("prospect_id")
        if not pid:
            continue
        existing = scores_by_pid.get(pid)
        if not existing or score.get("scored_at", "") > existing.get("scored_at", ""):
            scores_by_pid[pid] = score

    # Build training records
    records: list[dict[str, Any]] = []
    for prospect in prospects:
        pid = prospect["id"]
        calls = calls_by_pid.get(pid)
        if not calls:
            continue

        outcomes = [c["outcome"] for c in calls if c.get("outcome")]
        label = _best_label(outcomes, prospect.get("stage"))
        score_rec = scores_by_pid.get(pid, {})

        records.append({
            "prospect_id": pid,
            "business_name": prospect.get("business_name", ""),
            "metro": prospect.get("metro", ""),
            "total_score": prospect.get("total_score", 0),
            "score_tier": prospect.get("score_tier", "unscored"),
            "dimension_scores": score_rec.get("dimension_scores", {}),
            "outcomes": outcomes,
            "label": label,
            "review_signals": prospect.get("review_signals"),
            "desperation_score": prospect.get("desperation_score", 0),
        })

    return records


# ---------------------------------------------------------------------------
# Signal effectiveness
# ---------------------------------------------------------------------------


def compute_signal_effectiveness(
    training_data: list[dict[str, Any]],
    dimensions: list[str],
) -> tuple[float, list[SignalEffectiveness]]:
    """Per-dimension precision, lift, coverage with Bayesian smoothing.

    Filters to conclusive outcomes only (positive + negative).
    """
    conclusive = [r for r in training_data if r["label"] in ("positive", "negative")]
    if not conclusive:
        return 0.0, []

    total_positive = sum(1 for r in conclusive if r["label"] == "positive")
    base_rate = total_positive / len(conclusive)

    results: list[SignalEffectiveness] = []
    for dim in dimensions:
        with_signal = [r for r in conclusive if r["dimension_scores"].get(dim, 0) != 0]
        without_signal = [r for r in conclusive if r["dimension_scores"].get(dim, 0) == 0]

        pos_with = sum(1 for r in with_signal if r["label"] == "positive")
        pos_without = sum(1 for r in without_signal if r["label"] == "positive")
        total_with = len(with_signal)
        total_without = len(without_signal)

        raw_prec = pos_with / total_with if total_with else 0.0
        smoothed = (pos_with + BAYESIAN_ALPHA) / (total_with + BAYESIAN_ALPHA + BAYESIAN_BETA)
        lift = smoothed / base_rate if base_rate > 0 else 0.0
        coverage = pos_with / total_positive if total_positive > 0 else 0.0

        results.append(SignalEffectiveness(
            dimension=dim,
            total_with_signal=total_with,
            positive_with_signal=pos_with,
            total_without_signal=total_without,
            positive_without_signal=pos_without,
            raw_precision=round(raw_prec, 4),
            smoothed_precision=round(smoothed, 4),
            lift=round(lift, 4),
            coverage=round(coverage, 4),
        ))

    return round(base_rate, 4), results


# ---------------------------------------------------------------------------
# Tier accuracy
# ---------------------------------------------------------------------------


def compute_tier_accuracy(
    training_data: list[dict[str, Any]],
) -> list[TierAccuracy]:
    """Positive rate by score tier."""
    conclusive = [r for r in training_data if r["label"] in ("positive", "negative")]
    tiers_order = ["a_lead", "b_lead", "c_lead", "disqualified", "unscored"]

    by_tier: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0})
    for r in conclusive:
        tier = r.get("score_tier", "unscored")
        by_tier[tier]["total"] += 1
        by_tier[tier][r["label"]] += 1

    results: list[TierAccuracy] = []
    for tier in tiers_order:
        data = by_tier.get(tier)
        if not data or data["total"] == 0:
            continue
        results.append(TierAccuracy(
            tier=tier,
            total=data["total"],
            positive=data["positive"],
            negative=data["negative"],
            precision=round(data["positive"] / data["total"], 4),
        ))
    return results


# ---------------------------------------------------------------------------
# Discrimination score (AUC proxy)
# ---------------------------------------------------------------------------


def compute_discrimination_score(
    training_data: list[dict[str, Any]],
    *,
    max_sample: int = 500,
) -> float | None:
    """Wilcoxon-Mann-Whitney concordance index.

    Fraction of (positive, negative) pairs where the positive has a higher
    total_score.  Returns None if fewer than 5 positives or 5 negatives.
    Samples down to max_sample per class to avoid O(n*m) blowup.
    """
    import random

    conclusive = [r for r in training_data if r["label"] in ("positive", "negative")]
    positives = [r["total_score"] for r in conclusive if r["label"] == "positive"]
    negatives = [r["total_score"] for r in conclusive if r["label"] == "negative"]

    if len(positives) < 5 or len(negatives) < 5:
        return None

    # Sample to cap computation at max_sample^2 pairs
    if len(positives) > max_sample:
        positives = random.sample(positives, max_sample)
    if len(negatives) > max_sample:
        negatives = random.sample(negatives, max_sample)

    concordant = 0.0
    total_pairs = len(positives) * len(negatives)
    for p in positives:
        for n in negatives:
            if p > n:
                concordant += 1.0
            elif p == n:
                concordant += 0.5

    return round(concordant / total_pairs, 4)


# ---------------------------------------------------------------------------
# Weight suggestions
# ---------------------------------------------------------------------------


def suggest_weights(
    base_rate: float,
    effectiveness: list[SignalEffectiveness],
    current_weights: dict[str, int],
    min_sample_met: bool,
) -> dict[str, int]:
    """Scale current weights by lift, renormalize positives to sum=100.

    Returns current_weights unchanged if min_sample_met is False.
    """
    if not min_sample_met or not effectiveness:
        return dict(current_weights)

    eff_by_dim = {e.dimension: e for e in effectiveness}
    raw_suggested: dict[str, float] = {}

    for dim, weight in current_weights.items():
        eff = eff_by_dim.get(dim)
        if not eff or eff.total_with_signal == 0:
            raw_suggested[dim] = float(weight)
            continue

        lift = max(eff.lift, 0.1)
        if weight > 0:
            raw_suggested[dim] = weight * lift
        else:
            # Negative weight: high lift (signal predicts positive) → reduce penalty
            raw_suggested[dim] = weight / lift

    # Renormalize positive weights to preserve budget
    current_pos_sum = sum(w for w in current_weights.values() if w > 0)
    raw_pos_sum = sum(v for v in raw_suggested.values() if v > 0)

    if raw_pos_sum > 0 and current_pos_sum > 0:
        scale = current_pos_sum / raw_pos_sum
        for dim in raw_suggested:
            if raw_suggested[dim] > 0:
                raw_suggested[dim] *= scale

    # Clamp and round
    suggested: dict[str, int] = {}
    for dim, val in raw_suggested.items():
        clamped = max(-30, min(40, val))
        suggested[dim] = round(clamped)

    # Fix rounding drift on positive weights
    pos_sum = sum(v for v in suggested.values() if v > 0)
    if pos_sum != current_pos_sum and pos_sum > 0:
        biggest_pos = max((d for d in suggested if suggested[d] > 0), key=lambda d: suggested[d])
        suggested[biggest_pos] += current_pos_sum - pos_sum

    return suggested


# ---------------------------------------------------------------------------
# Review signal analysis
# ---------------------------------------------------------------------------


def compute_review_signal_effectiveness(
    training_data: list[dict[str, Any]],
) -> list[SignalEffectiveness] | None:
    """Analyze review enrichment signals for conclusive prospects.

    Returns None if fewer than 10 prospects have review enrichment data.
    """
    enriched = [r for r in training_data if r.get("review_signals")]
    if len(enriched) < 10:
        return None

    conclusive = [r for r in enriched if r["label"] in ("positive", "negative")]
    if not conclusive:
        return None

    total_positive = sum(1 for r in conclusive if r["label"] == "positive")
    base_rate = total_positive / len(conclusive) if conclusive else 0.0

    dimensions = list(REVIEW_SIGNAL_WEIGHTS.keys())
    results: list[SignalEffectiveness] = []

    for dim in dimensions:
        def _has_signal(r: dict, _dim: str = dim) -> bool:
            signals = r.get("review_signals") or {}
            signal_list = signals.get("signals", [])
            return any(s.get("signal_type") == _dim for s in signal_list)

        with_signal = [r for r in conclusive if _has_signal(r)]
        without_signal = [r for r in conclusive if not _has_signal(r)]

        pos_with = sum(1 for r in with_signal if r["label"] == "positive")
        total_with = len(with_signal)
        total_without = len(without_signal)
        pos_without = sum(1 for r in without_signal if r["label"] == "positive")

        raw_prec = pos_with / total_with if total_with else 0.0
        smoothed = (pos_with + BAYESIAN_ALPHA) / (total_with + BAYESIAN_ALPHA + BAYESIAN_BETA)
        lift = smoothed / base_rate if base_rate > 0 else 0.0
        coverage = pos_with / total_positive if total_positive > 0 else 0.0

        results.append(SignalEffectiveness(
            dimension=dim,
            total_with_signal=total_with,
            positive_with_signal=pos_with,
            total_without_signal=total_without,
            positive_without_signal=pos_without,
            raw_precision=round(raw_prec, 4),
            smoothed_precision=round(smoothed, 4),
            lift=round(lift, 4),
            coverage=round(coverage, 4),
        ))

    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_feedback_analysis(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    dry_run: bool = False,
) -> FeedbackReport:
    """Collect data, compute all metrics, optionally store, return report."""
    training_data = collect_training_data(tenant_id=tenant_id)

    conclusive = [r for r in training_data if r["label"] in ("positive", "negative")]
    positive_count = sum(1 for r in training_data if r["label"] == "positive")
    negative_count = sum(1 for r in training_data if r["label"] == "negative")
    inconclusive_count = sum(1 for r in training_data if r["label"] == "inconclusive")
    min_sample_met = len(conclusive) >= MIN_CONCLUSIVE_OUTCOMES

    dimensions = list(DISPATCH_SCORE_WEIGHTS.keys())
    base_rate, dim_metrics = compute_signal_effectiveness(training_data, dimensions)

    tier_acc = compute_tier_accuracy(training_data)
    disc_score = compute_discrimination_score(training_data)
    suggested = suggest_weights(base_rate, dim_metrics, DISPATCH_SCORE_WEIGHTS, min_sample_met)
    review_metrics = compute_review_signal_effectiveness(training_data)

    current_hash = rubric_hash()

    report = FeedbackReport(
        total_analyzed=len(training_data),
        positive_count=positive_count,
        negative_count=negative_count,
        inconclusive_count=inconclusive_count,
        base_rate=base_rate,
        min_sample_met=min_sample_met,
        rubric_hash=current_hash,
        dimension_metrics=dim_metrics,
        tier_accuracy=tier_acc,
        current_weights=dict(DISPATCH_SCORE_WEIGHTS),
        suggested_weights=suggested,
        review_signal_metrics=review_metrics,
        discrimination_score=disc_score,
    )

    if not dry_run:
        store.insert_scoring_feedback({
            "tenant_id": tenant_id,
            "rubric_hash": current_hash,
            "total_prospects_analyzed": report.total_analyzed,
            "positive_count": report.positive_count,
            "negative_count": report.negative_count,
            "inconclusive_count": report.inconclusive_count,
            "base_rate": float(report.base_rate),
            "dimension_metrics": _metrics_to_json(dim_metrics),
            "current_weights": report.current_weights,
            "suggested_weights": report.suggested_weights,
            "review_signal_metrics": _metrics_to_json(review_metrics) if review_metrics else None,
            "tier_accuracy": _tier_acc_to_json(tier_acc),
            "discrimination_score": report.discrimination_score,
        })

    return report


def _metrics_to_json(metrics: list[SignalEffectiveness]) -> list[dict[str, Any]]:
    return [
        {
            "dimension": m.dimension,
            "total_with_signal": m.total_with_signal,
            "positive_with_signal": m.positive_with_signal,
            "raw_precision": m.raw_precision,
            "smoothed_precision": m.smoothed_precision,
            "lift": m.lift,
            "coverage": m.coverage,
        }
        for m in metrics
    ]


def _tier_acc_to_json(tiers: list[TierAccuracy]) -> list[dict[str, Any]]:
    return [
        {"tier": t.tier, "total": t.total, "positive": t.positive,
         "negative": t.negative, "precision": t.precision}
        for t in tiers
    ]


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_report(report: FeedbackReport) -> str:
    """Human-readable text report."""
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("  SCORING FEEDBACK REPORT")
    lines.append("=" * 60)

    # Sample summary
    lines.append("")
    lines.append(f"  Prospects analyzed: {report.total_analyzed}")
    lines.append(f"  Positive (interested/converted): {report.positive_count}")
    lines.append(f"  Negative (not interested/wrong#/gatekeeper): {report.negative_count}")
    lines.append(f"  Inconclusive (no answer/voicemail/callback): {report.inconclusive_count}")
    lines.append(f"  Base rate: {report.base_rate:.1%}")
    lines.append(f"  Rubric hash: {report.rubric_hash[:12]}...")

    if not report.min_sample_met:
        lines.append("")
        lines.append(f"  ⚠  Not enough data ({report.positive_count + report.negative_count}"
                     f" conclusive, need {MIN_CONCLUSIVE_OUTCOMES})")
        lines.append("     Weight suggestions suppressed.")

    # Signal effectiveness
    if report.dimension_metrics:
        lines.append("")
        lines.append("-" * 60)
        lines.append("  SIGNAL EFFECTIVENESS")
        lines.append("-" * 60)
        lines.append(f"  {'Dimension':<20} {'Prec':>6} {'Lift':>6} {'Cov':>6} {'n':>5}")
        lines.append(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*5}")
        for m in sorted(report.dimension_metrics, key=lambda x: x.lift, reverse=True):
            lines.append(
                f"  {m.dimension:<20} {m.smoothed_precision:>5.0%} {m.lift:>5.1f}x "
                f"{m.coverage:>5.0%} {m.total_with_signal:>5}"
            )

    # Tier accuracy
    if report.tier_accuracy:
        lines.append("")
        lines.append("-" * 60)
        lines.append("  TIER ACCURACY")
        lines.append("-" * 60)
        lines.append(f"  {'Tier':<15} {'Total':>6} {'Pos':>6} {'Neg':>6} {'Prec':>7}")
        lines.append(f"  {'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*7}")
        for t in report.tier_accuracy:
            lines.append(
                f"  {t.tier:<15} {t.total:>6} {t.positive:>6} {t.negative:>6} {t.precision:>6.0%}"
            )

    # Weight comparison
    if report.min_sample_met:
        lines.append("")
        lines.append("-" * 60)
        lines.append("  WEIGHT SUGGESTIONS")
        lines.append("-" * 60)
        lines.append(f"  {'Dimension':<20} {'Current':>8} {'Suggested':>10} {'Delta':>7}")
        lines.append(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*7}")
        for dim in DISPATCH_SCORE_WEIGHTS:
            cur = report.current_weights[dim]
            sug = report.suggested_weights[dim]
            delta = sug - cur
            sign = "+" if delta > 0 else ""
            lines.append(f"  {dim:<20} {cur:>8} {sug:>10} {sign}{delta:>6}")

    # Discrimination score
    if report.discrimination_score is not None:
        lines.append("")
        lines.append(f"  Discrimination (AUC proxy): {report.discrimination_score:.3f}")
        if report.discrimination_score >= 0.7:
            lines.append("  → Scoring separates positive from negative well.")
        elif report.discrimination_score >= 0.5:
            lines.append("  → Scoring has some predictive value.")
        else:
            lines.append("  → Scoring is not discriminating — weights need rework.")

    # Review signals
    if report.review_signal_metrics:
        lines.append("")
        lines.append("-" * 60)
        lines.append("  REVIEW ENRICHMENT SIGNALS")
        lines.append("-" * 60)
        lines.append(f"  {'Signal':<25} {'Prec':>6} {'Lift':>6} {'n':>5}")
        lines.append(f"  {'-'*25} {'-'*6} {'-'*6} {'-'*5}")
        for m in sorted(report.review_signal_metrics, key=lambda x: x.lift, reverse=True):
            lines.append(
                f"  {m.dimension:<25} {m.smoothed_precision:>5.0%} {m.lift:>5.1f}x {m.total_with_signal:>5}"
            )

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Scoring feedback loop analysis")
    parser.add_argument("--dry-run", action="store_true", help="Do not store results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--tenant-id", default=OUTBOUND_TENANT_ID)
    args = parser.parse_args()

    report = run_feedback_analysis(tenant_id=args.tenant_id, dry_run=args.dry_run)

    if args.json:
        out = {
            "total_analyzed": report.total_analyzed,
            "positive_count": report.positive_count,
            "negative_count": report.negative_count,
            "inconclusive_count": report.inconclusive_count,
            "base_rate": report.base_rate,
            "min_sample_met": report.min_sample_met,
            "rubric_hash": report.rubric_hash,
            "dimension_metrics": _metrics_to_json(report.dimension_metrics),
            "tier_accuracy": _tier_acc_to_json(report.tier_accuracy),
            "current_weights": report.current_weights,
            "suggested_weights": report.suggested_weights,
            "review_signal_metrics": _metrics_to_json(report.review_signal_metrics) if report.review_signal_metrics else None,
            "discrimination_score": report.discrimination_score,
        }
        print(json.dumps(out, indent=2))
    else:
        print(format_report(report))

    if args.dry_run:
        print("\n  (dry run — results not stored)")


if __name__ == "__main__":
    main()

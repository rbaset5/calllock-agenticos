from __future__ import annotations

from unittest.mock import patch

from outbound.constants import DISPATCH_SCORE_WEIGHTS, OUTBOUND_TENANT_ID
from outbound.feedback_loop import (
    MIN_CONCLUSIVE_OUTCOMES,
    SignalEffectiveness,
    _best_label,
    compute_discrimination_score,
    compute_signal_effectiveness,
    compute_tier_accuracy,
    format_report,
    run_feedback_analysis,
    suggest_weights,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    label: str,
    total_score: int = 50,
    tier: str = "b_lead",
    dimension_scores: dict | None = None,
    review_signals: dict | None = None,
) -> dict:
    return {
        "prospect_id": f"p-{id(label)}-{total_score}",
        "business_name": "Test Co",
        "metro": "MI",
        "total_score": total_score,
        "score_tier": tier,
        "dimension_scores": dimension_scores or {},
        "outcomes": ["answered_interested"] if label == "positive" else ["answered_not_interested"],
        "label": label,
        "review_signals": review_signals,
        "desperation_score": 0,
    }


# ---------------------------------------------------------------------------
# _best_label tests
# ---------------------------------------------------------------------------


def test_best_label_positive_wins():
    """Positive outcome wins even if mixed with negatives."""
    assert _best_label(["no_answer", "answered_not_interested", "answered_interested"]) == "positive"


def test_best_label_positive_from_stage():
    """Converted stage counts as positive."""
    assert _best_label(["no_answer"], stage="converted") == "positive"


def test_best_label_negative_over_inconclusive():
    assert _best_label(["no_answer", "voicemail_left", "answered_not_interested"]) == "negative"


def test_best_label_all_inconclusive():
    assert _best_label(["no_answer", "voicemail_left"]) == "inconclusive"


def test_best_label_empty():
    assert _best_label([]) == "inconclusive"


# ---------------------------------------------------------------------------
# Signal effectiveness
# ---------------------------------------------------------------------------


def test_signal_effectiveness_perfect_signal():
    """Signal that appears on all positives and no negatives → high lift."""
    data = [
        _make_record("positive", dimension_scores={"paid_demand": 25}),
        _make_record("positive", dimension_scores={"paid_demand": 25}),
        _make_record("negative", dimension_scores={"paid_demand": 0}),
        _make_record("negative", dimension_scores={"paid_demand": 0}),
    ]
    base_rate, metrics = compute_signal_effectiveness(data, ["paid_demand"])
    assert base_rate == 0.5
    m = metrics[0]
    assert m.positive_with_signal == 2
    assert m.total_with_signal == 2
    assert m.raw_precision == 1.0
    assert m.lift > 1.0


def test_signal_effectiveness_useless_signal():
    """Signal present on both positive and negative equally → lift near 1."""
    data = [
        _make_record("positive", dimension_scores={"paid_demand": 25}),
        _make_record("negative", dimension_scores={"paid_demand": 25}),
        _make_record("positive", dimension_scores={"paid_demand": 0}),
        _make_record("negative", dimension_scores={"paid_demand": 0}),
    ]
    base_rate, metrics = compute_signal_effectiveness(data, ["paid_demand"])
    m = metrics[0]
    # With Bayesian smoothing, lift should be close to 1.0
    assert 0.8 <= m.lift <= 1.2


def test_bayesian_smoothing_small_sample():
    """1/1 positive should NOT yield 100% smoothed precision."""
    data = [_make_record("positive", dimension_scores={"paid_demand": 25})]
    _, metrics = compute_signal_effectiveness(data, ["paid_demand"])
    m = metrics[0]
    assert m.raw_precision == 1.0
    # Smoothed: (1+1)/(1+1+1) = 0.667, not 1.0
    assert m.smoothed_precision < 1.0
    assert abs(m.smoothed_precision - 0.6667) < 0.01


def test_signal_effectiveness_empty():
    base_rate, metrics = compute_signal_effectiveness([], ["paid_demand"])
    assert base_rate == 0.0
    assert metrics == []


def test_signal_effectiveness_filters_inconclusive():
    """Inconclusive records should not affect effectiveness calculations."""
    data = [
        _make_record("positive", dimension_scores={"paid_demand": 25}),
        _make_record("negative", dimension_scores={"paid_demand": 0}),
        _make_record("inconclusive", dimension_scores={"paid_demand": 25}),
    ]
    base_rate, metrics = compute_signal_effectiveness(data, ["paid_demand"])
    m = metrics[0]
    # Only 2 conclusive records, not 3
    assert m.total_with_signal + m.total_without_signal == 2


# ---------------------------------------------------------------------------
# Tier accuracy
# ---------------------------------------------------------------------------


def test_tier_accuracy_basic():
    data = [
        _make_record("positive", tier="a_lead"),
        _make_record("positive", tier="a_lead"),
        _make_record("negative", tier="a_lead"),
        _make_record("negative", tier="c_lead"),
    ]
    tiers = compute_tier_accuracy(data)
    a = next(t for t in tiers if t.tier == "a_lead")
    assert a.total == 3
    assert a.positive == 2
    assert abs(a.precision - 0.6667) < 0.01


def test_tier_accuracy_skips_empty():
    data = [_make_record("positive", tier="a_lead")]
    tiers = compute_tier_accuracy(data)
    tier_names = [t.tier for t in tiers]
    assert "b_lead" not in tier_names


# ---------------------------------------------------------------------------
# Discrimination score
# ---------------------------------------------------------------------------


def test_discrimination_score_perfect():
    """All positives score higher than all negatives → AUC = 1.0."""
    data = (
        [_make_record("positive", total_score=90) for _ in range(5)]
        + [_make_record("negative", total_score=30) for _ in range(5)]
    )
    assert compute_discrimination_score(data) == 1.0


def test_discrimination_score_inverse():
    """All negatives score higher → AUC = 0.0."""
    data = (
        [_make_record("positive", total_score=20) for _ in range(5)]
        + [_make_record("negative", total_score=80) for _ in range(5)]
    )
    assert compute_discrimination_score(data) == 0.0


def test_discrimination_score_random():
    """Same score for all → AUC = 0.5 (ties)."""
    data = (
        [_make_record("positive", total_score=50) for _ in range(5)]
        + [_make_record("negative", total_score=50) for _ in range(5)]
    )
    assert compute_discrimination_score(data) == 0.5


def test_discrimination_score_insufficient_data():
    data = [_make_record("positive") for _ in range(3)]
    assert compute_discrimination_score(data) is None


# ---------------------------------------------------------------------------
# Weight suggestions
# ---------------------------------------------------------------------------


def test_suggest_weights_preserves_sum():
    """Positive weights should sum to the same total as current."""
    effectiveness = [
        SignalEffectiveness("paid_demand", 10, 5, 10, 2, 0.5, 0.5, 2.0, 0.7),
        SignalEffectiveness("after_hours", 10, 3, 10, 4, 0.3, 0.3, 1.0, 0.4),
        SignalEffectiveness("backup_intake", 8, 2, 12, 5, 0.25, 0.25, 0.8, 0.3),
        SignalEffectiveness("hours", 5, 2, 15, 5, 0.4, 0.4, 1.3, 0.3),
        SignalEffectiveness("owner_operated", 6, 3, 14, 4, 0.5, 0.5, 1.5, 0.4),
        SignalEffectiveness("review_pain", 4, 1, 16, 6, 0.25, 0.25, 0.8, 0.1),
        SignalEffectiveness("already_served", 3, 0, 17, 7, 0.0, 0.0, 0.0, 0.0),
    ]
    suggested = suggest_weights(0.35, effectiveness, DISPATCH_SCORE_WEIGHTS, min_sample_met=True)
    pos_sum = sum(v for v in suggested.values() if v > 0)
    current_pos_sum = sum(v for v in DISPATCH_SCORE_WEIGHTS.values() if v > 0)
    assert pos_sum == current_pos_sum


def test_suggest_weights_no_change_when_insufficient():
    """With min_sample_met=False, returns current weights unchanged."""
    suggested = suggest_weights(0.3, [], DISPATCH_SCORE_WEIGHTS, min_sample_met=False)
    assert suggested == DISPATCH_SCORE_WEIGHTS


def test_suggest_weights_negative_stays_negative():
    """already_served weight should remain negative."""
    effectiveness = [
        SignalEffectiveness("paid_demand", 10, 5, 10, 2, 0.5, 0.5, 1.5, 0.7),
        SignalEffectiveness("after_hours", 10, 3, 10, 4, 0.3, 0.3, 1.0, 0.4),
        SignalEffectiveness("backup_intake", 8, 2, 12, 5, 0.25, 0.25, 0.8, 0.3),
        SignalEffectiveness("hours", 5, 2, 15, 5, 0.4, 0.4, 1.3, 0.3),
        SignalEffectiveness("owner_operated", 6, 3, 14, 4, 0.5, 0.5, 1.5, 0.4),
        SignalEffectiveness("review_pain", 4, 1, 16, 6, 0.25, 0.25, 0.8, 0.1),
        SignalEffectiveness("already_served", 3, 1, 17, 6, 0.33, 0.33, 1.0, 0.1),
    ]
    suggested = suggest_weights(0.35, effectiveness, DISPATCH_SCORE_WEIGHTS, min_sample_met=True)
    assert suggested["already_served"] < 0


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def test_format_report_renders():
    """Smoke test: format_report returns non-empty string."""
    data = (
        [_make_record("positive", total_score=80, tier="a_lead",
                       dimension_scores={"paid_demand": 25}) for _ in range(12)]
        + [_make_record("negative", total_score=40, tier="c_lead",
                         dimension_scores={"paid_demand": 0}) for _ in range(12)]
    )
    base_rate, metrics = compute_signal_effectiveness(data, list(DISPATCH_SCORE_WEIGHTS.keys()))
    tier_acc = compute_tier_accuracy(data)
    disc = compute_discrimination_score(data)
    suggested = suggest_weights(base_rate, metrics, DISPATCH_SCORE_WEIGHTS, min_sample_met=True)

    from outbound.feedback_loop import FeedbackReport
    from outbound.scoring import rubric_hash as rh

    report = FeedbackReport(
        total_analyzed=24,
        positive_count=12,
        negative_count=12,
        inconclusive_count=0,
        base_rate=base_rate,
        min_sample_met=True,
        rubric_hash=rh(),
        dimension_metrics=metrics,
        tier_accuracy=tier_acc,
        current_weights=dict(DISPATCH_SCORE_WEIGHTS),
        suggested_weights=suggested,
        review_signal_metrics=None,
        discrimination_score=disc,
    )
    text = format_report(report)
    assert "SCORING FEEDBACK REPORT" in text
    assert "SIGNAL EFFECTIVENESS" in text
    assert "WEIGHT SUGGESTIONS" in text


# ---------------------------------------------------------------------------
# Integration: run_feedback_analysis
# ---------------------------------------------------------------------------


def test_run_feedback_analysis_dry_run(monkeypatch):
    """Dry run should not call insert_scoring_feedback."""
    from outbound import feedback_loop, store

    # Seed some test data in local store
    for i in range(25):
        label = "positive" if i < 10 else "negative"
        phone = f"+1555000{i:04d}"
        store.upsert_outbound_prospects([{
            "tenant_id": OUTBOUND_TENANT_ID,
            "business_name": f"Test {i}",
            "trade": "hvac",
            "metro": "MI",
            "phone": phone,
            "phone_normalized": phone,
            "source": "manual",
            "timezone": "America/Detroit",
            "raw_source": {"is_spending_on_ads": True},
            "total_score": 80 if label == "positive" else 40,
            "score_tier": "a_lead" if label == "positive" else "c_lead",
            "stage": "called",
        }])
        pid = store.list_outbound_prospects()[-1]["id"]

        # Insert a score record
        store.insert_prospect_score({
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": pid,
            "dimension_scores": {"paid_demand": 25 if label == "positive" else 0},
            "total_score": 80 if label == "positive" else 40,
            "tier": "a_lead" if label == "positive" else "c_lead",
            "rubric_hash": "test-hash",
        })

        # Insert a call
        outcome = "answered_interested" if label == "positive" else "answered_not_interested"
        store.insert_outbound_call({
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": pid,
            "twilio_call_sid": f"CA-test-{i:04d}",
            "outcome": outcome,
        })

    insert_called = []
    original_insert = store.insert_scoring_feedback

    def mock_insert(payload):
        insert_called.append(payload)
        return original_insert(payload)

    monkeypatch.setattr(store, "insert_scoring_feedback", mock_insert)

    report = feedback_loop.run_feedback_analysis(dry_run=True)

    assert report.total_analyzed >= 25
    assert report.positive_count >= 10
    assert report.negative_count >= 15
    assert len(insert_called) == 0  # dry run → no store call

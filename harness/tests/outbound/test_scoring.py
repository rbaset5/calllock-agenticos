from __future__ import annotations

from outbound import store
from outbound.constants import OUTBOUND_TENANT_ID
from outbound.scoring import (
    classify_tier,
    compute_dimension_scores,
    compute_total_score,
    extract_signal_rows,
    score_prospects,
)


def _insert_prospect(raw_source: dict[str, object], *, business_name: str = "Prospect") -> str:
    result = store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": business_name,
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": "+16025550100",
                "phone_normalized": f"+1602555{len(store.list_outbound_prospects()):04d}",
                "source": "leads_db",
                "timezone": "America/Phoenix",
                "raw_source": raw_source,
            }
        ]
    )
    return result["records"][0]["id"]


def test_dimension_score_calculation_for_supported_signals() -> None:
    signals = extract_signal_rows(
        {
            "is_spending_on_ads": True,
            "workday_timing": "Weekday only 8-5",
            "reviews": 12,
            "rating": 4.0,
            "owner_name_found": "Alex",
            "is_franchise": False,
            "has_dispatcher": False,
            "backup_intake": False,
        }
    )

    dimensions = compute_dimension_scores(signals)

    assert dimensions == {
        "paid_demand": 25,
        "after_hours": 0,
        "backup_intake": 20,
        "hours": 10,
        "owner_operated": 10,
        "review_pain": 10,
    }


def test_weighted_sum_and_tier_thresholds() -> None:
    assert compute_total_score({"paid_demand": 25, "after_hours": 25, "backup_intake": 20, "hours": 5, "owner_operated": 0, "review_pain": 0}) == 75
    assert classify_tier(75) == "a_lead"
    assert classify_tier(50) == "b_lead"
    assert classify_tier(30) == "c_lead"
    assert classify_tier(29) == "disqualified"


def test_score_prospects_zero_signals_disqualifies() -> None:
    prospect_id = _insert_prospect({})

    result = score_prospects([prospect_id])
    prospect = store.get_outbound_prospect(prospect_id)

    assert result == {"scored": 1, "a_leads": 0, "b_leads": 0, "c_leads": 0, "disqualified": 1}
    assert prospect is not None
    assert prospect["total_score"] == 0
    assert prospect["score_tier"] == "disqualified"


def test_score_prospects_respects_exact_threshold_boundaries() -> None:
    a_id = _insert_prospect({"is_spending_on_ads": True, "backup_intake": False, "workday_timing": "Weekday only 8-5", "owner_name_found": "Alex", "is_franchise": False, "reviews": 12, "rating": 4.0}, business_name="A")
    b_id = _insert_prospect({"is_spending_on_ads": True, "backup_intake": False, "owner_name_found": "Alex", "is_franchise": False, "reviews": 50, "rating": 4.9}, business_name="B")
    c_id = _insert_prospect({"is_spending_on_ads": True, "reviews": 5, "rating": 4.0}, business_name="C")

    score_prospects([a_id, b_id, c_id])

    assert store.get_outbound_prospect(a_id)["score_tier"] == "a_lead"
    assert store.get_outbound_prospect(b_id)["score_tier"] == "b_lead"
    assert store.get_outbound_prospect(c_id)["score_tier"] == "c_lead"

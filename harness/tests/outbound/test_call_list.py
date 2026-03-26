from __future__ import annotations

from outbound import store
from outbound.call_list import get_ranked_prospects
from outbound.constants import OUTBOUND_TENANT_ID


def _insert_call_ready(name: str, score: int, idx: int) -> None:
    store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": name,
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": f"+1602555{idx:04d}",
                "phone_normalized": f"+1602555{idx:04d}",
                "source": "leads_db",
                "timezone": "America/Phoenix",
                "total_score": score,
                "score_tier": "a_lead",
                "stage": "call_ready",
                "raw_source": {},
            }
        ]
    )


def test_call_list_ranks_higher_score_first() -> None:
    _insert_call_ready("Lower", 50, 1)
    _insert_call_ready("Higher", 80, 2)

    ranked = get_ranked_prospects()

    assert [item["business_name"] for item in ranked[:2]] == ["Higher", "Lower"]


def test_call_list_truncates_to_top_100() -> None:
    for idx in range(200):
        _insert_call_ready(f"Prospect {idx}", 200 - idx, idx)

    ranked = get_ranked_prospects()

    assert len(ranked) == 100
    assert ranked[0]["total_score"] == 200
    assert ranked[-1]["total_score"] == 101


def test_call_list_empty_returns_empty_list() -> None:
    assert get_ranked_prospects() == []

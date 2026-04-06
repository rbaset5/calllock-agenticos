from __future__ import annotations

import uuid

OUTBOUND_TENANT_ID = "00000000-0000-0000-0000-000000000001"
OUTBOUND_UUID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
OUTBOUND_SOURCE_VERSION = "outbound-scout-v1"

DISPATCH_SCORE_WEIGHTS = {
    "paid_demand": 25,
    "after_hours": 25,
    "backup_intake": 20,
    "hours": 10,
    "owner_operated": 10,
    "review_pain": 10,
    "already_served": -15,
}

TIER_THRESHOLDS = {
    "a_lead": 75,
    "b_lead": 50,
    "c_lead": 30,
}

PROBE_ELIGIBLE_TIERS = {"a_lead", "b_lead"}
CALL_READY_LIMIT = 100

# ---------------------------------------------------------------------------
# Review scanner enrichment
# ---------------------------------------------------------------------------
REVIEW_ENRICHMENT_CAP = 30  # max ICP score delta from review enrichment

REVIEW_SIGNAL_WEIGHTS = {
    "responsiveness_gap": 15,
    "after_hours_gap": 10,
    "owner_absent": 5,
    "small_team_confirmed": 5,
    "declining_quality": 5,
    "low_response_rate": 5,
    "negative_trend": 5,
}

DESPERATION_WEIGHTS = {
    "responsiveness_gap": 30,
    "after_hours_gap": 20,
    "declining_quality": 15,
    "owner_absent": 15,
    "small_team_confirmed": 10,
    "low_response_rate": 10,
    "negative_trend": 10,
}

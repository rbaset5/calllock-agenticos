from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from outbound.lsa_db import export_csv, init_db, query_completed, save_query, upsert_business
from outbound.lsa_discovery import parse_lsa_results, query_hash

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_lsa_fixture():
    """Parse real SerpAPI LSA response and extract correct fields."""
    with open(FIXTURES / "lsa_response.json") as f:
        data = json.load(f)
    results = parse_lsa_results(data, "Traverse City", "MI")
    assert len(results) > 0
    first = results[0]
    assert first["business_name"]
    assert first["phone"].startswith("+1")
    assert first["town"] == "Traverse City"
    assert first["state"] == "MI"
    assert isinstance(first.get("rating"), (int, float)) or first.get("rating") is None
    assert isinstance(first.get("review_count"), (int, type(None)))


def test_phone_dedup():
    """Same phone from different towns resolves to one row."""
    conn = init_db(":memory:")
    biz1 = {"business_name": "HVAC Co", "phone": "+12315551234", "town": "Traverse City", "state": "MI"}
    biz2 = {"business_name": "HVAC Co", "phone": "+12315551234", "town": "Petoskey", "state": "MI"}
    upsert_business(conn, biz1)
    upsert_business(conn, biz2)
    count = conn.execute("SELECT COUNT(*) FROM lsa_businesses").fetchone()[0]
    assert count == 1


def test_leads_db_match_flag():
    """Cross-reference sets leads_db_match correctly."""
    conn = init_db(":memory:")
    biz = {
        "business_name": "Test HVAC", "phone": "+12315559999",
        "town": "Adrian", "state": "MI", "leads_db_match": 1,
    }
    upsert_business(conn, biz)
    row = conn.execute("SELECT leads_db_match FROM lsa_businesses WHERE phone=?",
                       ("+12315559999",)).fetchone()
    assert row[0] == 1


def test_query_hash_idempotent():
    """Same town/state always produces same hash; rerun skips completed."""
    conn = init_db(":memory:")
    h = query_hash("Traverse City", "MI")
    assert h == query_hash("Traverse City", "MI")
    assert not query_completed(conn, h)
    save_query(conn, h, "Traverse City", "MI", "success", result_count=10)
    assert query_completed(conn, h)


def test_csv_export_sorted():
    """CSV exports sorted by review_count ASC."""
    conn = init_db(":memory:")
    upsert_business(conn, {"business_name": "Big Co", "phone": "+12315551111",
                           "town": "A", "state": "MI", "review_count": 200})
    upsert_business(conn, {"business_name": "Small Co", "phone": "+12315552222",
                           "town": "B", "state": "MI", "review_count": 5})
    upsert_business(conn, {"business_name": "Mid Co", "phone": "+12315553333",
                           "town": "C", "state": "MI", "review_count": 50})

    import tempfile, csv
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        path = f.name
    export_csv(conn, path)
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["business_name"] == "Small Co"
    assert rows[1]["business_name"] == "Mid Co"
    assert rows[2]["business_name"] == "Big Co"


# --- LSA → Supabase ingest bridge tests ---


def test_lsa_icp_scoring():
    """LSA businesses get paid_demand=25 and c_lead floor."""
    from outbound.ingest import compute_lsa_icp_score

    # High-rating, high-review business: only paid_demand fires
    score, tier, signals = compute_lsa_icp_score({"rating": 5.0, "review_count": 80})
    assert signals["paid_demand"] == 25
    assert "review_pain" not in signals
    assert "small_operation" not in signals
    assert score >= 30  # c_lead floor
    assert tier == "c_lead"

    # Low-rating, low-review business: all signals fire
    score2, tier2, signals2 = compute_lsa_icp_score({"rating": 3.5, "review_count": 15})
    assert signals2["paid_demand"] == 25
    assert signals2["review_pain"] == 20
    assert signals2["small_operation"] == 15
    assert score2 == 60
    assert tier2 == "b_lead"


def test_lsa_icp_floor():
    """LSA businesses never score below c_lead threshold (30)."""
    from outbound.ingest import compute_lsa_icp_score

    # Edge case: no rating, no reviews, only paid_demand=25
    score, tier, _ = compute_lsa_icp_score({"rating": 0, "review_count": 0})
    assert score >= 30
    assert tier == "c_lead"


def test_lsa_ingest_filter_range(tmp_path):
    """ingest_from_lsa filters to specified review range."""
    from outbound.ingest import ingest_from_lsa
    from outbound.lsa_db import init_db, upsert_business

    db_path = tmp_path / "test_lsa.db"
    conn = init_db(str(db_path))
    # Insert businesses with varying review counts
    upsert_business(conn, {"business_name": "Too Small", "phone": "+15551110001",
                           "town": "Sebring", "state": "FL", "review_count": 5})
    upsert_business(conn, {"business_name": "In Range", "phone": "+15551110002",
                           "town": "Sebring", "state": "FL", "review_count": 50})
    upsert_business(conn, {"business_name": "Too Big", "phone": "+15551110003",
                           "town": "Sebring", "state": "FL", "review_count": 200})
    conn.close()

    result = ingest_from_lsa(lsa_db_path=str(db_path), min_reviews=10, max_reviews=100)
    # Only "In Range" should be ingested
    assert result["inserted"] == 1


def test_lsa_ingest_filters_non_sprint_states(tmp_path):
    """ingest_from_lsa skips WY businesses (not in sprint segments) but passes FL, OH, MI."""
    from outbound.ingest import ingest_from_lsa
    from outbound.lsa_db import init_db, upsert_business

    db_path = tmp_path / "test_lsa.db"
    conn = init_db(str(db_path))
    upsert_business(conn, {"business_name": "WY Shop", "phone": "+15551110004",
                           "town": "Cheyenne", "state": "WY", "review_count": 50})
    upsert_business(conn, {"business_name": "FL Shop", "phone": "+15551110005",
                           "town": "Sebring", "state": "FL", "review_count": 50})
    upsert_business(conn, {"business_name": "OH Shop", "phone": "+15551110006",
                           "town": "Columbus", "state": "OH", "review_count": 50})
    upsert_business(conn, {"business_name": "MI Shop", "phone": "+15551110007",
                           "town": "Adrian", "state": "MI", "review_count": 50})
    conn.close()

    result = ingest_from_lsa(lsa_db_path=str(db_path), min_reviews=10, max_reviews=100)
    assert result["filtered_out"] == 1  # WY shop filtered
    assert result["inserted"] == 3  # FL + OH + MI ingested

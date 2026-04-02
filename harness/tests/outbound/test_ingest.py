from __future__ import annotations

import sqlite3

from outbound.ingest import compute_icp_score, normalize_phone, run_batch
from outbound.metro import extract_zip, zip_to_timezone
from outbound.store import list_outbound_prospects


def _seed_leads(db_path: str, rows: list[tuple[object, ...]]) -> None:
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        create table leads (
            id text,
            business_name text,
            source_category text,
            phone text,
            address text,
            website text,
            is_spending_on_ads text,
            reviews integer,
            rating real,
            owner_name text,
            is_franchise integer,
            workday_timing text default ''
        )
        """
    )
    connection.executemany(
        """
        insert into leads (
            id, business_name, source_category, phone, address, website,
            is_spending_on_ads, reviews, rating, owner_name, is_franchise
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()


def test_normalize_phone_supports_expected_formats() -> None:
    assert normalize_phone("4155550100") == "+14155550100"
    assert normalize_phone("14155550100") == "+14155550100"
    assert normalize_phone("+1 (415) 555-0100") == "+14155550100"
    assert normalize_phone("+49 30 123456") == "+4930123456"
    assert normalize_phone("123") is None


def test_run_batch_dedups_and_skips_missing_phone(tmp_path) -> None:
    db_path = tmp_path / "leads.db"
    _seed_leads(
        str(db_path),
        [
            ("1", "Phoenix HVAC 1", "hvac", "6025550100", "123 Main St Phoenix AZ 85001", None, 1, 14, 4.1, "Alex", 0),
            ("2", "Phoenix HVAC 2", "hvac", "(602) 555-0100", "456 Main St Phoenix AZ 85001", None, 0, 10, 3.9, "Casey", 0),
            ("3", "Missing Phone", "hvac", "", "789 Main St Phoenix AZ 85001", None, 0, 0, 5.0, "", 0),
        ],
    )

    result = run_batch(str(db_path), metros=["Phoenix"], trades=["hvac"], batch_size=10)

    assert result == {"ingested": 1, "skipped_dedup": 1, "skipped_no_phone": 0, "skipped_no_metro": 0}
    prospects = list_outbound_prospects()
    assert len(prospects) == 1
    assert prospects[0]["phone_normalized"] == "+16025550100"
    assert prospects[0]["stage"] == "call_ready"
    assert prospects[0]["total_score"] > 0


def test_run_batch_filters_by_metro(tmp_path) -> None:
    db_path = tmp_path / "leads.db"
    _seed_leads(
        str(db_path),
        [
            ("1", "Phoenix HVAC", "hvac", "6025550100", "123 Main St Phoenix AZ 85001", None, 1, 14, 4.1, "Alex", 0),
            ("2", "Chicago HVAC", "hvac", "3125550100", "123 Lake St Chicago IL 60601", None, 1, 14, 4.1, "Alex", 0),
        ],
    )

    result = run_batch(str(db_path), metros=["Phoenix"], trades=["hvac"], batch_size=10)

    assert result["ingested"] == 1
    assert result["skipped_no_metro"] == 1
    prospects = list_outbound_prospects()
    assert [row["metro"] for row in prospects] == ["Phoenix"]
    assert prospects[0]["stage"] == "call_ready"


def test_extract_zip_handles_country_suffixes() -> None:
    assert extract_zip("Musterstrasse 1, Phoenix AZ 85001, Vereinigte Staaten") == "85001"
    assert extract_zip("123 Main St, Chicago, IL 60601") == "60601"
    assert extract_zip("No zip here") is None


def test_zip_to_timezone_uses_static_map() -> None:
    assert zip_to_timezone("85001") == "America/Phoenix"
    assert zip_to_timezone("60601") == "America/Chicago"


def test_compute_icp_score_strong_icp() -> None:
    """Owner-operated, low reviews, has website, spending on ads → high score."""
    row = {
        "is_spending_on_ads": "True",
        "owner_name": "Alex Johnson",
        "is_franchise": 0,
        "reviews": 12,
        "rating": 3.8,
        "website": "https://example.com",
        "workday_timing": "",
    }
    total, tier, signals = compute_icp_score(row)
    assert total >= 75
    assert tier == "a_lead"
    assert "paid_demand" in signals
    assert "owner_operated" in signals
    assert "review_pain" in signals


def test_compute_icp_score_weak_lead() -> None:
    """No signals at all → low score."""
    row = {
        "is_spending_on_ads": "",
        "owner_name": "",
        "is_franchise": 1,
        "reviews": 0,
        "rating": 0,
        "website": "",
        "workday_timing": "",
    }
    total, tier, _signals = compute_icp_score(row)
    assert total == 0
    assert tier == "unscored"


def test_run_batch_excludes_franchises(tmp_path) -> None:
    db_path = tmp_path / "leads.db"
    _seed_leads(
        str(db_path),
        [
            ("1", "Local Plumber", "plumbing", "6025550101", "123 Main St Phoenix AZ 85001", None, "True", 8, 3.5, "Mike", 0),
            ("2", "Roto-Rooter #412", "plumbing", "6025550102", "456 Main St Phoenix AZ 85001", None, "True", 500, 4.5, "", 1),
        ],
    )

    result = run_batch(str(db_path), metros=["Phoenix"], trades=["plumbing"], batch_size=10)

    assert result["ingested"] == 1
    prospects = list_outbound_prospects()
    assert len(prospects) == 1
    assert prospects[0]["business_name"] == "Local Plumber"

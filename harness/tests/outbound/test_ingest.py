from __future__ import annotations

import sqlite3

from outbound.ingest import normalize_phone, run_batch
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
            is_spending_on_ads integer,
            reviews integer,
            rating real,
            owner_name_found text,
            is_franchise integer
        )
        """
    )
    connection.executemany(
        """
        insert into leads (
            id, business_name, source_category, phone, address, website,
            is_spending_on_ads, reviews, rating, owner_name_found, is_franchise
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

    assert result == {"ingested": 1, "skipped_dedup": 1, "skipped_no_phone": 1, "skipped_no_metro": 0}
    prospects = list_outbound_prospects()
    assert len(prospects) == 1
    assert prospects[0]["phone_normalized"] == "+16025550100"


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
    assert [row["metro"] for row in list_outbound_prospects()] == ["Phoenix"]


def test_extract_zip_handles_country_suffixes() -> None:
    assert extract_zip("Musterstrasse 1, Phoenix AZ 85001, Vereinigte Staaten") == "85001"
    assert extract_zip("123 Main St, Chicago, IL 60601") == "60601"
    assert extract_zip("No zip here") is None


def test_zip_to_timezone_uses_static_map() -> None:
    assert zip_to_timezone("85001") == "America/Phoenix"
    assert zip_to_timezone("60601") == "America/Chicago"

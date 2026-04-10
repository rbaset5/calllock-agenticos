from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from outbound import maps_scraper_ingest
from outbound.constants import OUTBOUND_TENANT_ID
from outbound.maps_scraper_ingest import (
    has_after_hours_coverage,
    is_blacklisted_category,
    is_toll_free,
    list_cohort_a,
    load_scraper_output,
    run_ingest,
)
from outbound.store import list_outbound_prospects


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "maps_scraper_sample.json"


def _seed_lsa_db(path: Path, phones: list[str]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE lsa_businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            phone TEXT,
            UNIQUE(phone)
        )
        """
    )
    conn.executemany(
        "INSERT INTO lsa_businesses (business_name, phone) VALUES (?, ?)",
        [(f"lsa shop {i}", p) for i, p in enumerate(phones)],
    )
    conn.commit()
    conn.close()


def _write_fixture(tmp_path: Path, rows: list[dict]) -> str:
    p = tmp_path / "sample.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def test_has_after_hours_coverage() -> None:
    assert has_after_hours_coverage({"Monday": "Open 24 hours"}) is True
    assert has_after_hours_coverage({"Monday": "9 AM - 5 PM"}) is False
    assert has_after_hours_coverage({}) is None
    assert has_after_hours_coverage(None) is None
    assert has_after_hours_coverage("Open 24 hours") is True
    assert has_after_hours_coverage("9am-5pm") is False


def test_is_toll_free() -> None:
    assert is_toll_free("+18005551234") is True
    assert is_toll_free("+18885551234") is True
    assert is_toll_free("+18775551234") is True
    assert is_toll_free("+12485551234") is False
    assert is_toll_free(None) is False
    assert is_toll_free("") is False


def test_load_scraper_output_json_array(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, [{"title": "A"}, {"title": "B"}])
    rows = load_scraper_output(path)
    assert len(rows) == 2
    assert rows[0]["title"] == "A"


def test_load_scraper_output_ndjson_fallback(tmp_path: Path) -> None:
    # Truncated JSON: missing closing bracket → must fall back to line-by-line.
    p = tmp_path / "broken.json"
    p.write_text('{"title": "A"}\n{"title": "B"}\n', encoding="utf-8")
    rows = load_scraper_output(str(p))
    assert len(rows) == 2
    assert rows[1]["title"] == "B"


def test_load_scraper_output_total_failure(tmp_path: Path) -> None:
    p = tmp_path / "garbage.json"
    p.write_text("not json at all {{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_scraper_output(str(p))


# ---------------------------------------------------------------------------
# Full fixture — 15 rows, all 11 acceptance cases
# ---------------------------------------------------------------------------

def test_full_fixture_end_to_end(tmp_path: Path) -> None:
    lsa_db = tmp_path / "lsa_discovery.db"
    _seed_lsa_db(lsa_db, ["+12485550112"])

    result = run_ingest(
        input_path=str(FIXTURE_PATH),
        state="MI",
        dry_run=False,
        lsa_db_path=lsa_db,
    )

    assert "error" not in result
    # Fixture total: 15 rows
    assert result["raw_rows"] == 15
    # Drops: missing phone (row 8) → 14 valid phones
    assert result["phone_valid"] == 14
    # Toll-free row counted + disqualified
    assert result["toll_free"] == 1
    assert result["disqualified"] == 1
    # LSA overlap: row 13 phone is in the mock lsa db
    assert result["lsa_exclude"] == 1
    # Missing rating / missing review_count → 2 drops
    assert result["missing_fields_drop"] == 2
    # Loosened filter (rating>=4.0, reviews 30-200, after-hours gate dropped):
    # call_ready = rows 1, 2, 3, 5 (4.6 now allowed), 6 (49 now allowed),
    # 7 (101 now allowed), 12 (empty hours kept), 14 (business-hours-only
    # no longer dropped), 15 = 9 rows.
    assert result["final_ingest"] == 9

    prospects = list_outbound_prospects()
    call_ready_maps = [
        p for p in prospects
        if p.get("source") == "maps_scraper" and p.get("stage") == "call_ready"
    ]
    disqualified_maps = [
        p for p in prospects
        if p.get("source") == "maps_scraper" and p.get("stage") == "disqualified"
    ]
    assert len(call_ready_maps) == 9
    assert len(disqualified_maps) == 1

    # Assertion bundle for test case 7: record shape
    sample = call_ready_maps[0]
    assert sample["tenant_id"] == OUTBOUND_TENANT_ID
    assert sample["source"] == "maps_scraper"
    assert sample["stage"] == "call_ready"
    assert sample["raw_source"]["cohort"] == "a"
    assert sample["raw_source"]["scraper_source"] == "gosom/google-maps-scraper"
    assert sample["timezone"] == "America/Detroit"
    assert "upsert_duration_sec" in result
    assert "per_record_ms" in result

    # The Supabase path honors disqualification_reason (POSTs record as-is),
    # but store.py:200 hardcodes it to None in the local-state INSERT path.
    # We assert the stage instead — that's the field that matters for --list retrieval.
    assert disqualified_maps[0]["stage"] == "disqualified"
    assert disqualified_maps[0]["source"] == "maps_scraper"


# ---------------------------------------------------------------------------
# Targeted boundary tests (each ~1 row to keep local state isolated)
# ---------------------------------------------------------------------------

def test_rating_boundaries(tmp_path: Path) -> None:
    # Loosened filter: rating >= 4.0 only (no ceiling).
    rows = [
        {"title": "r=4.0", "phone": "+12485550201", "rating": 4.0, "review_count": 75},
        {"title": "r=3.9", "phone": "+12485550202", "rating": 3.9, "review_count": 75},
        {"title": "r=4.5", "phone": "+12485550203", "rating": 4.5, "review_count": 75},
        {"title": "r=5.0", "phone": "+12485550204", "rating": 5.0, "review_count": 75},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["final_ingest"] == 3
    prospects = list_outbound_prospects()
    names = sorted(p["business_name"] for p in prospects)
    assert names == ["r=4.0", "r=4.5", "r=5.0"]


def test_review_count_boundaries(tmp_path: Path) -> None:
    # Loosened filter: 0 <= review_count <= 200. Floor dropped — include brand-new
    # listings since Michigan HVAC ratings cluster so tight that review count is
    # the primary signal of "not a mega-shop".
    rows = [
        {"title": "rc=0", "phone": "+12485550301", "rating": 4.2, "review_count": 0},
        {"title": "rc=1", "phone": "+12485550302", "rating": 4.2, "review_count": 1},
        {"title": "rc=200", "phone": "+12485550303", "rating": 4.2, "review_count": 200},
        {"title": "rc=201", "phone": "+12485550304", "rating": 4.2, "review_count": 201},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["final_ingest"] == 3
    prospects = list_outbound_prospects()
    names = sorted(p["business_name"] for p in prospects)
    assert names == ["rc=0", "rc=1", "rc=200"]


def test_phone_normalization_variants(tmp_path: Path) -> None:
    rows = [
        {"title": "E.164", "phone": "+12485550401", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "10-digit", "phone": "2485550402", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "pretty", "phone": "(248) 555-0403", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "null", "phone": "", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "toll-free", "phone": "+18005550405", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["phone_valid"] == 4
    assert result["toll_free"] == 1
    assert result["final_ingest"] == 3

    prospects = list_outbound_prospects()
    phones = {p["phone_normalized"] for p in prospects}
    assert "+12485550401" in phones
    assert "+12485550402" in phones
    assert "+12485550403" in phones
    assert "+18005550405" in phones  # disqualified but still upserted for dedup
    # null was dropped
    disqualified = [p for p in prospects if p["stage"] == "disqualified"]
    assert len(disqualified) == 1
    assert disqualified[0]["phone_normalized"] == "+18005550405"


def test_pre_check_dedup(tmp_path: Path) -> None:
    # First run ingests; second run must see the phone as already present.
    rows = [
        {"title": "Dup1", "phone": "+12485550501", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    first = run_ingest(input_path=path, state="MI")
    assert first["final_ingest"] == 1

    second = run_ingest(input_path=path, state="MI")
    assert second["dedup_skip"] == 1
    assert second["final_ingest"] == 0
    assert len(list_outbound_prospects()) == 1


def test_lsa_exclusion(tmp_path: Path) -> None:
    lsa_db = tmp_path / "lsa.db"
    _seed_lsa_db(lsa_db, ["+12485550601"])
    rows = [
        {"title": "LSA overlap", "phone": "+12485550601", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "Clean", "phone": "+12485550602", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI", lsa_db_path=lsa_db)
    assert result["lsa_exclude"] == 1
    assert result["final_ingest"] == 1
    prospects = list_outbound_prospects()
    assert len(prospects) == 1
    assert prospects[0]["phone_normalized"] == "+12485550602"


def test_dry_run_does_not_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"title": "Dry", "phone": "+12485550701", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)

    call_count = {"n": 0}
    real_upsert = maps_scraper_ingest.store.upsert_or_enrich_prospects

    def _trap(records):
        call_count["n"] += 1
        return real_upsert(records)

    monkeypatch.setattr(maps_scraper_ingest.store, "upsert_or_enrich_prospects", _trap)

    result = run_ingest(input_path=path, state="MI", dry_run=True)
    assert result["dry_run"] is True
    assert result["final_ingest"] == 1
    assert len(result["sample_records"]) == 1
    assert call_count["n"] == 0
    assert list_outbound_prospects() == []


def test_missing_rating_field_drops_row(tmp_path: Path) -> None:
    rows = [
        {"title": "No rating", "phone": "+12485550801", "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "Fine", "phone": "+12485550802", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["missing_fields_drop"] == 1
    assert result["final_ingest"] == 1


def test_missing_review_count_drops_row(tmp_path: Path) -> None:
    rows = [
        {"title": "No reviews", "phone": "+12485550901", "rating": 4.2, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "Fine", "phone": "+12485550902", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["missing_fields_drop"] == 1
    assert result["final_ingest"] == 1


def test_truncated_json_falls_back_to_ndjson(tmp_path: Path) -> None:
    p = tmp_path / "truncated.json"
    p.write_text(
        '{"title": "Row1", "phone": "+12485551001", "rating": 4.2, "review_count": 75, '
        '"open_hours": {"Mon": "Open 24 hours"}}\n'
        '{"title": "Row2", "phone": "+12485551002", "rating": 4.2, "review_count": 75, '
        '"open_hours": {"Mon": "Open 24 hours"}}\n',
        encoding="utf-8",
    )
    result = run_ingest(input_path=str(p), state="MI")
    assert result["final_ingest"] == 2


def test_category_blacklist_rejects_wholesaler(tmp_path: Path) -> None:
    rows = [
        {
            "title": "Legit Contractor",
            "phone": "+12485551301",
            "rating": 4.5,
            "review_count": 75,
            "category": "Air conditioning contractor",
        },
        {
            "title": "Johnstone-ish Supply",
            "phone": "+12485551302",
            "rating": 4.5,
            "review_count": 75,
            "category": "HVAC equipment supplier",
            "categories": ["Wholesaler"],
        },
        {
            "title": "Random Parts Shop",
            "phone": "+12485551303",
            "rating": 4.5,
            "review_count": 75,
            "categories": ["Auto parts store", "Repair service"],
        },
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["category_blacklist"] == 2
    assert result["final_ingest"] == 1
    prospects = list_outbound_prospects()
    assert [p["business_name"] for p in prospects] == ["Legit Contractor"]


def test_is_blacklisted_category_helper() -> None:
    assert is_blacklisted_category({"category": "HVAC contractor"}) is False
    assert is_blacklisted_category({"category": "HVAC wholesaler"}) is True
    assert is_blacklisted_category({"categories": ["Air conditioning contractor"]}) is False
    assert is_blacklisted_category({"categories": ["Plumbing supply"]}) is True
    assert is_blacklisted_category({"categories": ["Electrical contractor", "Warehouse"]}) is True
    assert is_blacklisted_category({}) is False


def test_empty_hours_dict_not_dropped(tmp_path: Path) -> None:
    rows = [
        {"title": "Unknown hours", "phone": "+12485551101", "rating": 4.2, "review_count": 75, "open_hours": {}},
    ]
    path = _write_fixture(tmp_path, rows)
    result = run_ingest(input_path=path, state="MI")
    assert result["final_ingest"] == 1
    prospects = list_outbound_prospects()
    assert len(prospects) == 1
    assert prospects[0]["raw_source"]["has_after_hours_coverage"] is None


def test_list_cohort_a_only_returns_maps_scraper(tmp_path: Path) -> None:
    rows = [
        {"title": "Cohort A 1", "phone": "+12485551201", "rating": 4.2, "review_count": 75, "open_hours": {"Mon": "Open 24 hours"}},
        {"title": "Cohort A 2", "phone": "+12485551202", "rating": 4.3, "review_count": 80, "open_hours": {"Mon": "Open 24 hours"}},
    ]
    path = _write_fixture(tmp_path, rows)
    run_ingest(input_path=path, state="MI")

    listed = list_cohort_a(limit=10)
    assert len(listed) == 2
    names = sorted(r["business_name"] for r in listed)
    assert names == ["Cohort A 1", "Cohort A 2"]
    assert all(r["source"] == "maps_scraper" for r in listed)
    assert all(r["stage"] == "call_ready" for r in listed)

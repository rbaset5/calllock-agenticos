"""Tests for review_scanner.py — Google review enrichment pipeline."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from outbound.review_scanner import (
    compute_desperation_score,
    compute_metadata_signals,
    compute_review_enrichment_score,
    extract_review_signals,
    fetch_reviews,
    lookup_place_id,
    post_discord_summary,
    run_review_scan,
)
from outbound.lsa_db import init_db

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _load_reviews_fixture() -> dict:
    with open(FIXTURES / "google_reviews_response.json") as f:
        return json.load(f)


def _parse_fixture_reviews(data: dict) -> list[dict]:
    """Parse fixture into the format fetch_reviews returns."""
    reviews = []
    for review in data.get("reviews", []):
        reviews.append({
            "text": review.get("snippet", ""),
            "rating": review.get("rating"),
            "date": review.get("date", ""),
            "response_text": (review.get("response", {}) or {}).get("snippet", ""),
            "user_name": review.get("user", {}).get("name", ""),
        })
    return reviews


@pytest.fixture
def sample_reviews():
    return _parse_fixture_reviews(_load_reviews_fixture())


@pytest.fixture
def lsa_db(tmp_path):
    """Create a temporary LSA database with test data."""
    db_path = tmp_path / "test_lsa.db"
    conn = init_db(db_path)
    conn.execute(
        """INSERT INTO lsa_businesses
           (business_name, phone, town, state, rating, review_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Test HVAC Co", "+15551234567", "Traverse City", "MI", 3.5, 25),
    )
    conn.commit()
    return conn, db_path


# ---------------------------------------------------------------------------
# fetch_reviews
# ---------------------------------------------------------------------------

@patch("outbound.review_scanner.requests.get")
def test_parse_reviews(mock_get):
    """Fixture response parses into structured review list."""
    fixture = _load_reviews_fixture()
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    reviews = fetch_reviews("test_data_id", max_pages=1)
    assert len(reviews) == 10
    assert reviews[0]["text"] == "Called three times and nobody picked up. Left voicemails and never got a callback. Finally went with another company."
    assert reviews[0]["rating"] == 2
    assert reviews[0]["response_text"] == ""
    assert reviews[1]["response_text"] == "Thank you Sarah! We always try to provide same-day service."


# ---------------------------------------------------------------------------
# compute_metadata_signals
# ---------------------------------------------------------------------------

def test_metadata_signals_all_responded():
    reviews = [
        {"text": "Good", "rating": 5, "response_text": "Thanks!"},
        {"text": "OK", "rating": 4, "response_text": "Thank you"},
    ]
    result = compute_metadata_signals(reviews)
    assert result["response_rate"] == 1.0
    assert result["review_count"] == 2


def test_metadata_signals_none_responded():
    reviews = [
        {"text": "Bad", "rating": 2, "response_text": ""},
        {"text": "Terrible", "rating": 1, "response_text": ""},
        {"text": "OK", "rating": 3, "response_text": ""},
    ]
    result = compute_metadata_signals(reviews)
    assert result["response_rate"] == 0.0


def test_metadata_signals_negative_trend():
    """Recent reviews averaging lower than all-time triggers negative trend."""
    # 10 recent reviews at 2.0, 5 older reviews at 5.0
    reviews = [{"text": "Bad", "rating": 2, "response_text": ""} for _ in range(10)]
    reviews += [{"text": "Good", "rating": 5, "response_text": ""} for _ in range(5)]
    result = compute_metadata_signals(reviews)
    assert result["trend_delta"] < -0.5


def test_metadata_signals_empty():
    result = compute_metadata_signals([])
    assert result["response_rate"] == 0.0
    assert result["review_count"] == 0


# ---------------------------------------------------------------------------
# extract_review_signals
# ---------------------------------------------------------------------------

@patch("outbound.review_scanner.llm_completion")
def test_extract_signals_mock_llm(mock_llm, sample_reviews):
    mock_llm.return_value = {
        "text": json.dumps({
            "signals": [
                {"signal_type": "responsiveness_gap", "evidence": "Called three times, nobody picked up", "confidence": "high"},
                {"signal_type": "after_hours_gap", "evidence": "No after-hours service", "confidence": "medium"},
                {"signal_type": "small_team_confirmed", "evidence": "Owner and his son", "confidence": "high"},
            ],
            "owner_response_style": "template",
            "overall_sentiment": "mixed",
            "top_complaint": "responsiveness",
            "recommended_opener": "I noticed your customers mention difficulty reaching you by phone.",
        }),
        "status": "complete",
    }

    result = extract_review_signals(sample_reviews, "Test HVAC", "Traverse City", "MI")
    assert result is not None
    assert len(result["signals"]) == 3
    assert result["signals"][0]["signal_type"] == "responsiveness_gap"
    assert result["owner_response_style"] == "template"
    assert result["recommended_opener"].startswith("I noticed")


@patch("outbound.review_scanner.llm_completion")
def test_extract_signals_llm_failure(mock_llm):
    mock_llm.return_value = {"text": None, "status": "failed"}
    result = extract_review_signals(
        [{"text": "OK", "rating": 3}], "Test", "Town", "MI"
    )
    assert result is None


def test_extract_signals_empty_reviews():
    result = extract_review_signals([], "Test", "Town", "MI")
    assert result is None


@patch("outbound.review_scanner.llm_completion")
def test_extract_signals_invalid_json(mock_llm):
    mock_llm.return_value = {"text": "not valid json {{{", "status": "complete"}
    result = extract_review_signals(
        [{"text": "OK", "rating": 3}], "Test", "Town", "MI"
    )
    assert result is None


@patch("outbound.review_scanner.llm_completion")
def test_extract_signals_filters_invalid_types(mock_llm):
    """Invalid signal types are filtered out."""
    mock_llm.return_value = {
        "text": json.dumps({
            "signals": [
                {"signal_type": "responsiveness_gap", "evidence": "test", "confidence": "high"},
                {"signal_type": "made_up_type", "evidence": "test", "confidence": "high"},
            ],
            "owner_response_style": "engaged",
            "overall_sentiment": "mixed",
            "top_complaint": "none",
            "recommended_opener": "Test opener.",
        }),
        "status": "complete",
    }
    result = extract_review_signals(
        [{"text": "OK", "rating": 3}], "Test", "Town", "MI"
    )
    assert result is not None
    assert len(result["signals"]) == 1
    assert result["signals"][0]["signal_type"] == "responsiveness_gap"


# ---------------------------------------------------------------------------
# compute_desperation_score
# ---------------------------------------------------------------------------

def test_desperation_score_max():
    """All signals present results in capped score of 100."""
    signals = [
        {"signal_type": "responsiveness_gap", "confidence": "high"},
        {"signal_type": "after_hours_gap", "confidence": "high"},
        {"signal_type": "declining_quality", "confidence": "high"},
        {"signal_type": "small_team_confirmed", "confidence": "high"},
    ]
    metadata = {"response_rate": 0.1, "trend_delta": -1.0}
    score = compute_desperation_score(signals, metadata, "absent")
    assert score == 100


def test_desperation_score_zero():
    score = compute_desperation_score(None, {"response_rate": 1.0, "trend_delta": 0.0}, "engaged")
    assert score == 0


def test_desperation_score_medium_confidence():
    """Medium confidence signals get half weight."""
    signals = [{"signal_type": "responsiveness_gap", "confidence": "medium"}]
    metadata = {"response_rate": 1.0, "trend_delta": 0.0}
    score = compute_desperation_score(signals, metadata, "engaged")
    assert score == 15  # 30 // 2


# ---------------------------------------------------------------------------
# compute_review_enrichment_score
# ---------------------------------------------------------------------------

def test_enrichment_score_cap():
    """Enrichment score is capped at REVIEW_ENRICHMENT_CAP (30)."""
    signals = [
        {"signal_type": "responsiveness_gap"},
        {"signal_type": "after_hours_gap"},
        {"signal_type": "owner_absent"},
        {"signal_type": "small_team_confirmed"},
        {"signal_type": "declining_quality"},
    ]
    metadata = {"response_rate": 0.1, "trend_delta": -1.0}
    score = compute_review_enrichment_score(signals, metadata)
    assert score == 30  # capped


def test_enrichment_score_deduplicates_signal_types():
    """Same signal type appearing twice only counts once."""
    signals = [
        {"signal_type": "responsiveness_gap"},
        {"signal_type": "responsiveness_gap"},
    ]
    metadata = {"response_rate": 1.0, "trend_delta": 0.0}
    score = compute_review_enrichment_score(signals, metadata)
    assert score == 15  # only counted once


# ---------------------------------------------------------------------------
# lookup_place_id
# ---------------------------------------------------------------------------

@patch("outbound.review_scanner.SERPAPI_KEY", "test-key")
@patch("outbound.review_scanner.requests.get")
def test_lookup_place_id_ambiguous(mock_get):
    """Multiple results with no phone match returns None."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "local_results": [
            {"data_id": "id1", "phone": "+15559999999"},
            {"data_id": "id2", "phone": "+15558888888"},
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = lookup_place_id("Test HVAC", "+15551234567", "Town", "MI")
    assert result is None


@patch("outbound.review_scanner.SERPAPI_KEY", "test-key")
@patch("outbound.review_scanner.requests.get")
def test_lookup_place_id_single_result(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "local_results": [{"data_id": "0x123:0x456", "phone": "+15551234567"}]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = lookup_place_id("Test HVAC", "+15551234567", "Town", "MI")
    assert result == "0x123:0x456"


@patch("outbound.review_scanner.SERPAPI_KEY", "test-key")
@patch("outbound.review_scanner.requests.get")
def test_lookup_place_id_phone_match(mock_get):
    """Multiple results: matches by phone number."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "local_results": [
            {"data_id": "wrong_id", "phone": "+15559999999"},
            {"data_id": "correct_id", "phone": "+15551234567"},
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = lookup_place_id("Test HVAC", "+15551234567", "Town", "MI")
    assert result == "correct_id"


@patch("outbound.review_scanner.SERPAPI_KEY", "test-key")
@patch("outbound.review_scanner.requests.get")
def test_lookup_place_id_api_error(mock_get):
    """SerpAPI returns error JSON (e.g., bad API key) → returns None, no crash."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"error": "Invalid API key"}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = lookup_place_id("Test HVAC", "+15551234567", "Town", "MI")
    assert result is None


@patch("outbound.review_scanner.SERPAPI_KEY", "test-key")
@patch("outbound.review_scanner.requests.get")
def test_lookup_place_id_cache_hit(mock_get, lsa_db):
    """Cached place_id returns immediately without SerpAPI call."""
    conn, _ = lsa_db
    from outbound.lsa_db import save_place_id
    save_place_id(conn, "+15551234567", "cached_data_id", status="success")

    result = lookup_place_id("Test HVAC", "+15551234567", "Town", "MI", conn=conn)
    assert result == "cached_data_id"
    mock_get.assert_not_called()  # no API call made


# ---------------------------------------------------------------------------
# enrich_prospect_reviews (store.py)
# ---------------------------------------------------------------------------

def test_enrich_prospect_reviews_updates_score():
    """enrich_prospect_reviews adds enrichment delta to existing total_score."""
    from outbound import store
    # Seed a prospect
    store.upsert_outbound_prospects([{
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "business_name": "Test Co",
        "phone": "+15551234567",
        "phone_normalized": "+15551234567",
        "source": "lsa_discovery",
        "trade": "hvac",
        "total_score": 50,
        "score_tier": "b_lead",
        "stage": "call_ready",
    }])

    result = store.enrich_prospect_reviews("+15551234567", {
        "review_signals": {"signals": []},
        "review_opener": "Test opener",
        "review_enrichment_score": 20,
        "desperation_score": 45,
    })
    assert result is True

    # Check the score was updated
    prospects = store.list_outbound_prospects(stages=["call_ready"])
    match = [p for p in prospects if p["phone_normalized"] == "+15551234567"]
    assert len(match) == 1
    assert match[0]["total_score"] == 70  # 50 + 20
    assert match[0]["desperation_score"] == 45
    assert match[0]["review_opener"] == "Test opener"


def test_enrich_prospect_reviews_idempotent():
    """Running enrichment twice doesn't double the score."""
    from outbound import store
    store.upsert_outbound_prospects([{
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "business_name": "Idem Co",
        "phone": "+15559876543",
        "phone_normalized": "+15559876543",
        "source": "lsa_discovery",
        "trade": "hvac",
        "total_score": 40,
        "score_tier": "c_lead",
        "stage": "call_ready",
    }])

    enrichment = {
        "review_signals": {"signals": []},
        "review_opener": "Opener",
        "review_enrichment_score": 15,
        "desperation_score": 30,
    }

    store.enrich_prospect_reviews("+15559876543", enrichment)
    store.enrich_prospect_reviews("+15559876543", enrichment)  # second run

    prospects = store.list_outbound_prospects(stages=["call_ready"])
    match = [p for p in prospects if p["phone_normalized"] == "+15559876543"]
    assert match[0]["total_score"] == 55  # 40 + 15, NOT 40 + 15 + 15


# ---------------------------------------------------------------------------
# post_discord_summary
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"DISCORD_OUTBOUND_WEBHOOK_URL": "https://hooks.example.com/test"})
def test_discord_summary_format():
    """Discord summary includes key stats and top prospects."""
    import httpx as _httpx
    with patch.object(_httpx, "post") as mock_post:
        result = {"scanned": 10, "enriched": 8, "errors": 1,
                  "skipped_no_place_id": 1, "skipped_no_reviews": 0}
        top = [
            {"business_name": "Hot HVAC", "town": "Detroit", "state": "MI",
             "desperation_score": 85, "signal_summary": "responsiveness_gap(high)"},
        ]
        post_discord_summary(result, top)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        message = call_args[1]["json"]["content"]
        assert "Review Scanner Complete" in message
        assert "Hot HVAC" in message
        assert "desperation: 85" in message


# ---------------------------------------------------------------------------
# run_review_scan (dry run)
# ---------------------------------------------------------------------------

def test_run_scan_dry_run(lsa_db):
    conn, db_path = lsa_db
    with patch("outbound.review_scanner.init_db", return_value=conn):
        result = run_review_scan(dry_run=True)
    assert result["dry_run"] is True
    assert result["prospect_count"] == 1
    assert result["scanned"] == 0


# ---------------------------------------------------------------------------
# run_review_scan (idempotent)
# ---------------------------------------------------------------------------

@patch("outbound.review_scanner.time.sleep")
@patch("outbound.review_scanner.extract_review_signals")
@patch("outbound.review_scanner.fetch_reviews")
@patch("outbound.review_scanner.lookup_place_id")
def test_run_scan_idempotent(mock_lookup, mock_fetch, mock_extract, mock_sleep, lsa_db):
    """Scanning the same prospect twice produces the same enrichment, not double."""
    _, db_path = lsa_db

    mock_lookup.return_value = "test_data_id"
    mock_fetch.return_value = [{"text": "OK", "rating": 3, "response_text": "", "date": "", "user_name": ""}]
    mock_extract.return_value = {
        "signals": [{"signal_type": "responsiveness_gap", "evidence": "test", "confidence": "high"}],
        "owner_response_style": "absent",
        "overall_sentiment": "mixed",
        "top_complaint": "responsiveness",
        "recommended_opener": "Test opener.",
    }

    # Each run gets a fresh connection (init_db re-opens the same file)
    with patch("outbound.review_scanner.init_db", side_effect=lambda: init_db(db_path)), \
         patch("outbound.review_scanner.store") as mock_store_mod:
        mock_store_mod.enrich_prospect_reviews.return_value = True
        result1 = run_review_scan()
        result2 = run_review_scan()

    # Both runs should process the same prospect
    assert result1["enriched"] == 1
    assert result2["enriched"] == 1
    # Store called once per run
    assert mock_store_mod.enrich_prospect_reviews.call_count == 2

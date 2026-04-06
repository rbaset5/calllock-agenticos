from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from outbound.website_scanner import scan_website, _FINGERPRINTS, FRIENDLY_NAMES
from outbound.scoring import compute_dimension_scores, extract_signal_rows


# ── scan_website unit tests ─────────────────────────────────────────


def _mock_response(html: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, text=html, request=httpx.Request("GET", "https://example.com"))


def test_detects_callrail_script():
    html = '<html><head><script src="https://cdn.calltrk.com/123.js"></script></head><body></body></html>'
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://example-hvac.com")
    assert result["scan_ok"] is True
    assert result["has_call_tracking"] is True
    assert result["has_chat_widget"] is False
    assert "callrail" in result["vendors"]
    assert "CallRail" in result["vendors_display"]


def test_detects_drift_chat():
    html = '<html><body><script src="https://js.driftt.com/widget.js"></script></body></html>'
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://example-hvac.com")
    assert result["has_chat_widget"] is True
    assert "drift" in result["vendors"]


def test_detects_multiple_vendors():
    html = '<html><script src="https://calltrk.com/x.js"></script><script src="https://widget.intercom.io/w.js"></script></html>'
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://example-hvac.com")
    assert result["has_call_tracking"] is True
    assert result["has_chat_widget"] is True
    assert set(result["vendors"]) == {"callrail", "intercom"}


def test_clean_site_returns_no_vendors():
    html = "<html><body><h1>Best HVAC in town</h1></body></html>"
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://clean-hvac.com")
    assert result["scan_ok"] is True
    assert result["vendors"] == []
    assert result["has_call_tracking"] is False
    assert result["has_chat_widget"] is False


def test_invalid_url_returns_error():
    result = scan_website("")
    assert result["scan_ok"] is False
    assert result["error"] == "invalid_url"

    result = scan_website("not-a-url")
    assert result["scan_ok"] is False
    assert result["error"] == "invalid_url"


def test_timeout_returns_error():
    with patch("outbound.website_scanner.httpx.get", side_effect=httpx.TimeoutException("slow")):
        result = scan_website("https://slow-site.com")
    assert result["scan_ok"] is False
    assert result["error"] == "timeout"


def test_http_error_returns_error():
    resp = httpx.Response(404, request=httpx.Request("GET", "https://gone.com"))
    with patch("outbound.website_scanner.httpx.get", return_value=resp):
        result = scan_website("https://gone.com")
    assert result["scan_ok"] is False
    assert result["error"] == "http_404"


# ── Scoring integration ─────────────────────────────────────────────


def test_already_served_signal_applies_penalty():
    raw_source = {
        "is_spending_on_ads": True,
        "website_scan": {
            "vendors": ["callrail"],
            "has_call_tracking": True,
            "has_chat_widget": False,
        },
    }
    signals = extract_signal_rows(raw_source)
    types = [s["signal_type"] for s in signals]
    assert "already_served" in types
    assert "paid_demand" in types

    dimensions = compute_dimension_scores(signals)
    assert dimensions["already_served"] == -15
    assert dimensions["paid_demand"] == 25


def test_no_scan_data_produces_no_penalty():
    signals = extract_signal_rows({"is_spending_on_ads": True})
    types = [s["signal_type"] for s in signals]
    assert "already_served" not in types


def test_all_fingerprints_have_friendly_names():
    for vendor_slug, _, _ in _FINGERPRINTS:
        assert vendor_slug in FRIENDLY_NAMES, f"Missing friendly name for {vendor_slug}"


def test_servicetitan_is_disqualifier():
    html = '<html><script src="https://servicetitan.com/widget.js"></script></html>'
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://big-hvac.com")
    assert result["has_disqualifier"] is True
    assert "servicetitan" in result["vendors"]
    assert result["has_chat_widget"] is False  # moved out of chat_widget category


def test_housecall_pro_is_disqualifier():
    html = '<html><script src="https://housecallpro.com/embed.js"></script></html>'
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://pro-hvac.com")
    assert result["has_disqualifier"] is True
    assert "housecall_pro" in result["vendors"]


def test_clean_site_has_no_disqualifier():
    html = "<html><body>Best HVAC</body></html>"
    with patch("outbound.website_scanner.httpx.get", return_value=_mock_response(html)):
        result = scan_website("https://clean.com")
    assert result["has_disqualifier"] is False

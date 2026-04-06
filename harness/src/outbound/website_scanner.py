"""Website scanner: detect existing call-tracking / chat widgets on prospect sites.

Fetches business website HTML and checks for known vendor script fingerprints.
Returns detected vendors so scoring can apply a penalty and the HUD can surface
competitor context to the SDR during live calls.

Usage:
    from outbound.website_scanner import scan_website
    result = scan_website("https://example-hvac.com")
    # => {"has_call_tracking": True, "has_chat_widget": False,
    #     "vendors": ["callrail"], "scan_ok": True}
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SCAN_TIMEOUT = 8  # seconds

# ── Vendor fingerprints ─────────────────────────────────────────────
# Each entry: (vendor_name, category, pattern_compiled_at_module_load)
# Patterns match against full HTML (script srcs, inline snippets, etc.)

_FINGERPRINTS: list[tuple[str, str, re.Pattern[str]]] = [
    # Call tracking
    ("callrail", "call_tracking", re.compile(r"calltrk\.com|callrail", re.I)),
    ("calltrackingmetrics", "call_tracking", re.compile(r"calltrackingmetrics\.com|ctm\.com", re.I)),
    ("marchex", "call_tracking", re.compile(r"marchex\.io|marchex\.com", re.I)),
    ("invoca", "call_tracking", re.compile(r"invoca\.net|invoca\.com", re.I)),
    ("responsetap", "call_tracking", re.compile(r"responsetap\.com", re.I)),
    ("dialogtech", "call_tracking", re.compile(r"dialogtech\.com|dialoginsight", re.I)),
    ("whatconverts", "call_tracking", re.compile(r"whatconverts\.com", re.I)),

    # Chat / answering
    ("ruby_receptionists", "chat_widget", re.compile(r"ruby\.com/widget|callruby\.com", re.I)),
    ("intercom", "chat_widget", re.compile(r"intercom\.io|intercomcdn\.com", re.I)),
    ("drift", "chat_widget", re.compile(r"drift\.com|js\.driftt\.com", re.I)),
    ("livechat", "chat_widget", re.compile(r"livechatinc\.com|livechat\.com", re.I)),
    ("podium", "chat_widget", re.compile(r"podium\.com|podiumfe\.com", re.I)),

    # Disqualifiers — direct competitors or full-stack platforms (prospect is already served)
    ("smith_ai", "disqualifier", re.compile(r"smith\.ai", re.I)),
    ("servicetitan", "disqualifier", re.compile(r"servicetitan\.com", re.I)),
    ("housecall_pro", "disqualifier", re.compile(r"housecallpro\.com", re.I)),
    ("zendesk", "chat_widget", re.compile(r"zdassets\.com|zendesk\.com/embeddable", re.I)),
    ("tidio", "chat_widget", re.compile(r"tidio\.co|tidiochat\.com", re.I)),
]

FRIENDLY_NAMES: dict[str, str] = {
    "callrail": "CallRail",
    "calltrackingmetrics": "CallTrackingMetrics",
    "marchex": "Marchex",
    "invoca": "Invoca",
    "responsetap": "ResponseTap",
    "dialogtech": "DialogTech",
    "whatconverts": "WhatConverts",
    "smith_ai": "Smith.ai",
    "ruby_receptionists": "Ruby Receptionists",
    "intercom": "Intercom",
    "drift": "Drift",
    "livechat": "LiveChat",
    "podium": "Podium",
    "servicetitan": "ServiceTitan",
    "zendesk": "Zendesk Chat",
    "tidio": "Tidio",
    "housecall_pro": "Housecall Pro",
}


def _is_safe_url(url: str) -> bool:
    """Block SSRF: reject internal/private IPs and non-public hostnames."""
    from urllib.parse import urlparse
    import ipaddress

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    if not hostname or hostname == "localhost":
        return False

    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
    except ValueError:
        # Not an IP, it's a hostname — check for suspicious patterns
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False

    return True


def scan_website(url: str) -> dict[str, Any]:
    """Fetch *url* and return detected vendor widgets.

    Returns a dict with:
        scan_ok          bool   – True if we successfully fetched the page
        has_call_tracking bool  – True if any call-tracking vendor matched
        has_chat_widget   bool  – True if any chat/answering vendor matched
        vendors          list   – vendor slugs detected (e.g. ["callrail", "drift"])
        vendors_display  list   – human-friendly names (for HUD display)
        error            str|None – error message if scan failed
    """
    if not url or not url.startswith(("http://", "https://")):
        return _empty_result(error="invalid_url")

    if not _is_safe_url(url):
        return _empty_result(error="blocked_url")

    try:
        resp = httpx.get(
            url,
            timeout=SCAN_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CallLock-Scout/1.0)"},
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("website_scanner: timeout fetching %s", url)
        return _empty_result(error="timeout")
    except httpx.HTTPStatusError as exc:
        logger.warning("website_scanner: HTTP %s for %s", exc.response.status_code, url)
        return _empty_result(error=f"http_{exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.warning("website_scanner: request error for %s: %s", url, exc)
        return _empty_result(error="request_error")

    html = resp.text
    vendors: list[str] = []
    categories: set[str] = set()

    for vendor_slug, category, pattern in _FINGERPRINTS:
        if pattern.search(html):
            vendors.append(vendor_slug)
            categories.add(category)

    return {
        "scan_ok": True,
        "has_call_tracking": "call_tracking" in categories,
        "has_chat_widget": "chat_widget" in categories,
        "has_disqualifier": "disqualifier" in categories,
        "vendors": vendors,
        "vendors_display": [FRIENDLY_NAMES.get(v, v) for v in vendors],
        "error": None,
    }


def _empty_result(error: str) -> dict[str, Any]:
    return {
        "scan_ok": False,
        "has_call_tracking": False,
        "has_chat_widget": False,
        "has_disqualifier": False,
        "vendors": [],
        "vendors_display": [],
        "error": error,
    }

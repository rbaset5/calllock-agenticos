from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import logging
import socket
from typing import Any
from urllib import error, request

from inbound.quarantine import strip_html


logger = logging.getLogger(__name__)

INDUSTRY_KEYWORDS = ["hvac", "plumbing", "electrical", "roofing", "heating", "cooling", "air conditioning"]
SERVICE_BUSINESS_KEYWORDS = INDUSTRY_KEYWORDS + ["service", "services", "repair", "contractor", "installation"]


def is_private_ip(ip_str: str) -> bool:
    try:
        address = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return address.is_private or address.is_loopback or address.is_link_local


def resolve_domain(domain: str) -> list[str]:
    try:
        results = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    ips: list[str] = []
    for result in results:
        ip = str(result[4][0])
        if ip not in ips:
            ips.append(ip)
    return ips


def is_safe_domain(domain: str) -> bool:
    ips = resolve_domain(domain)
    if not ips:
        return False
    return all(not is_private_ip(ip) for ip in ips)


def fetch_homepage(domain: str, timeout: int = 10) -> str | None:
    if not is_safe_domain(domain):
        logger.warning("unsafe_domain_blocked", extra={"domain": domain})
        return None
    try:
        with request.urlopen(f"https://{domain}", timeout=timeout) as response:
            payload = response.read()
    except (OSError, ValueError, error.URLError):
        return None
    text = strip_html(payload.decode("utf-8", errors="replace"))
    return " ".join(text.split())


def research_sender(domain: str, tenant_id: str, repository: Any) -> dict[str, Any]:
    cached = repository.get_enrichment(tenant_id, domain, "sender_research", ttl_hours=168)
    if cached:
        return dict(cached.get("enrichment_data", {}))

    resolved_ips = resolve_domain(domain)
    homepage_text = (fetch_homepage(domain, timeout=10) or "")[:2000]
    lowered = homepage_text.lower()
    industry_signals = [keyword for keyword in INDUSTRY_KEYWORDS if keyword in lowered]
    research = {
        "domain": domain,
        "resolved_ips": resolved_ips,
        "homepage_text": homepage_text,
        "is_service_business": any(keyword in lowered for keyword in SERVICE_BUSINESS_KEYWORDS),
        "industry_signals": industry_signals,
    }
    repository.upsert_enrichment(
        tenant_id,
        domain,
        "sender_research",
        "inbound_pipeline",
        {
            "enrichment_data": research,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return research

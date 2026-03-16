from __future__ import annotations

from types import SimpleNamespace

from inbound import researcher


def test_is_private_ip_covers_ipv4_and_ipv6_ranges() -> None:
    private_ips = ["10.1.2.3", "172.16.5.4", "192.168.1.10", "127.0.0.1", "::1", "fc00::1"]
    public_ip = "8.8.8.8"

    for ip in private_ips:
        assert researcher.is_private_ip(ip) is True
    assert researcher.is_private_ip(public_ip) is False


def test_is_safe_domain_rejects_private_resolution(monkeypatch) -> None:
    monkeypatch.setattr(researcher, "resolve_domain", lambda domain: ["8.8.8.8"])
    assert researcher.is_safe_domain("example.com") is True

    monkeypatch.setattr(researcher, "resolve_domain", lambda domain: ["127.0.0.1"])
    assert researcher.is_safe_domain("localhost.test") is False


def test_fetch_homepage_returns_text_with_mock_http(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"<html><body><h1>HVAC repair</h1><p>Open 24/7</p></body></html>"

    monkeypatch.setattr(researcher, "is_safe_domain", lambda domain: True)
    monkeypatch.setattr(researcher.request, "urlopen", lambda url, timeout=10: FakeResponse())

    homepage = researcher.fetch_homepage("example.com", timeout=3)

    assert homepage == "HVAC repair Open 24/7"


def test_research_sender_returns_cached_result_without_upsert() -> None:
    cached = {"enrichment_data": {"domain": "cached.example", "resolved_ips": ["1.1.1.1"]}}
    repository = SimpleNamespace(
        get_enrichment=lambda tenant_id, cache_key, cache_type, ttl_hours=168: cached,
        upsert_enrichment=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not upsert on cache hit")),
    )

    result = researcher.research_sender("cached.example", "tenant-1", repository)

    assert result == cached["enrichment_data"]


def test_research_sender_builds_and_caches_on_miss(monkeypatch) -> None:
    captured: dict[str, object] = {}
    repository = SimpleNamespace(
        get_enrichment=lambda tenant_id, cache_key, cache_type, ttl_hours=168: None,
        upsert_enrichment=lambda tenant_id, cache_key, cache_type, source, data: captured.update(
            {
                "tenant_id": tenant_id,
                "cache_key": cache_key,
                "cache_type": cache_type,
                "source": source,
                "data": data,
            }
        ),
    )
    monkeypatch.setattr(researcher, "resolve_domain", lambda domain: ["1.2.3.4"])
    monkeypatch.setattr(researcher, "fetch_homepage", lambda domain, timeout=10: "HVAC plumbing repair and service")

    result = researcher.research_sender("example.com", "tenant-1", repository)

    assert result["domain"] == "example.com"
    assert result["resolved_ips"] == ["1.2.3.4"]
    assert result["is_service_business"] is True
    assert result["industry_signals"] == ["hvac", "plumbing"]
    assert captured["cache_key"] == "example.com"
    assert captured["cache_type"] == "sender_research"

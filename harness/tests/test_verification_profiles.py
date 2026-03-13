from harness.verification.profiles import derive_required_fields, get_profile


def test_required_fields_are_derived_from_worker_spec() -> None:
    fields = derive_required_fields({"outputs": ["lead routing decisions", "summary", "sentiment"]})
    assert fields == ["lead_route", "summary", "sentiment"]


def test_profile_uses_worker_defaults() -> None:
    profile = get_profile("product-marketer", {"outputs": ["messaging"]})
    assert profile["domain_safety"] == "product_marketer"
    assert profile["required_fields"] == ["messaging"]

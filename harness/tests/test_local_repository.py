from db.local_repository import get_compliance_rules, get_tenant, get_tenant_config


def test_local_repository_loads_tenant_by_slug() -> None:
    tenant = get_tenant("tenant-alpha")
    assert tenant["industry_pack_id"] == "hvac"


def test_local_repository_loads_config_and_rules() -> None:
    config = get_tenant_config("tenant-alpha")
    rules = get_compliance_rules("tenant-alpha")
    assert "notify_dispatch" in config["allowed_tools"]
    assert len(rules) >= 1

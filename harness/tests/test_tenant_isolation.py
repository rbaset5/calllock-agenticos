from cache.keys import tenant_key
from db.tenant_scope import with_tenant_scope


def test_tenant_keys_are_isolated() -> None:
    assert tenant_key("tenant-a", "pack", "hvac") != tenant_key("tenant-b", "pack", "hvac")


def test_scope_prefixes_sql() -> None:
    scoped = with_tenant_scope("tenant-a").apply_sql("select * from tenant_configs;")
    assert "app.current_tenant" in scoped
    assert "tenant-a" in scoped

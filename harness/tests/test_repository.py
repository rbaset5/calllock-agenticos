from db.repository import get_tenant, get_tenant_config, persist_run_record, using_supabase


def test_repository_defaults_to_local_without_supabase_env(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert using_supabase() is False
    assert get_tenant("tenant-alpha")["slug"] == "tenant-alpha"
    assert get_tenant_config("tenant-alpha")["industry_pack_id"] == "hvac"


def test_persist_run_record_uses_local_artifact_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("CALLLOCK_ARTIFACT_ROOT", str(tmp_path))
    record = persist_run_record(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-artifact",
            "worker_id": "customer-analyst",
            "status": "verified",
            "policy_verdict": "allow",
            "output": {"summary": "ok"},
        }
    )
    assert record["job"]["idempotency_key"] == "run-artifact"

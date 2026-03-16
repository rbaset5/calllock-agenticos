import pytest

from harness.workflows.onboarding import onboard_tenant


def test_onboarding_workflow_creates_tenant_and_config() -> None:
    result = onboard_tenant({"slug": "tenant-gamma", "name": "Tenant Gamma"})
    assert result["tenant"]["slug"] == "tenant-gamma"
    assert result["tenant_config"]["voice_agent"]["configured"] is True


def test_onboarding_rolls_back_on_failure(monkeypatch) -> None:
    from harness.workflows import onboarding

    monkeypatch.setattr(onboarding, "_verify_isolation", lambda tenant_id: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        onboard_tenant({"slug": "tenant-gamma", "name": "Tenant Gamma"})

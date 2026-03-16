from db.repository import list_audit_logs
from harness.audit import log_audit_event
from harness.workflows.onboarding import onboard_tenant


def test_audit_log_can_be_created_and_filtered() -> None:
    log_audit_event(
        action_type="control.kill_switch.updated",
        actor_id="operator-1",
        reason="pause tenant",
        tenant_id="00000000-0000-0000-0000-000000000001",
        target_type="tenant",
        target_id="00000000-0000-0000-0000-000000000001",
    )
    assert len(list_audit_logs()) == 1
    assert len(list_audit_logs(action_type="control.kill_switch.updated")) == 1


def test_onboarding_writes_audit_logs() -> None:
    onboard_tenant({"slug": "tenant-delta", "name": "Tenant Delta", "actor_id": "operator-2"})
    action_types = [log["action_type"] for log in list_audit_logs()]
    assert "tenant.onboard.started" in action_types
    assert "tenant.onboard.completed" in action_types

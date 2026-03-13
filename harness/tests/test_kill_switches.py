from harness.control_plane.kill_switches import upsert_kill_switch
from harness.nodes.policy_gate import evaluate_policy


def test_global_kill_switch_blocks_execution() -> None:
    upsert_kill_switch({"scope": "global", "reason": "maintenance", "active": True})
    decision = evaluate_policy(
        tool_name=None,
        worker_id="customer-analyst",
        tenant_id="tenant-alpha",
        approval_override=False,
        tenant_config={},
        compliance_rules=[{"id": "allow-default", "target": "*", "effect": "allow"}],
        feature_flags={"harness_enabled": True},
        granted_tools=[],
    )
    assert decision["verdict"] == "deny"

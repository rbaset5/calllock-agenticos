from harness.nodes.policy_gate import evaluate_policy
from harness.tool_registry import resolve_granted_tools
from observability.pii_redactor import redact_pii


def test_tool_registry_intersects_authoring_and_runtime() -> None:
    granted = resolve_granted_tools(
        ["read_knowledge", "notify_dispatch"],
        tenant_allowed=["notify_dispatch"],
        environment_allowed=["notify_dispatch", "book_appointment"],
    )
    assert granted == ["notify_dispatch"]


def test_policy_gate_denies_without_allow_rule() -> None:
    decision = evaluate_policy(
        tool_name="book_appointment",
        tenant_config={"industry_pack_id": "hvac"},
        compliance_rules=[],
        feature_flags={"harness_enabled": True},
        granted_tools=["book_appointment"],
    )
    assert decision["verdict"] == "deny"


def test_pii_redactor_masks_email_and_phone() -> None:
    redacted = redact_pii("Call me at 313-555-1212 or email ops@example.com")
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted

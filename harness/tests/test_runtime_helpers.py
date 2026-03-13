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
        worker_id="customer-analyst",
        tenant_id="tenant-alpha",
        approval_override=False,
        tenant_config={"industry_pack_id": "hvac"},
        compliance_rules=[],
        feature_flags={"harness_enabled": True},
        granted_tools=["book_appointment"],
    )
    assert decision["verdict"] == "deny"


def test_policy_gate_escalates_conflicting_compliance_rules() -> None:
    decision = evaluate_policy(
        tool_name="book_appointment",
        worker_id="customer-analyst",
        tenant_id="tenant-alpha",
        approval_override=False,
        tenant_config={"industry_pack_id": "hvac", "escalate_policy_violations": False},
        compliance_rules=[
            {
                "id": "allow-booking",
                "target": "book_appointment",
                "effect": "allow",
                "reason": "Booking is generally permitted.",
                "metadata": {"conflict_key": "booking-promise"},
            },
            {
                "id": "deny-booking",
                "target": "book_appointment",
                "effect": "deny",
                "reason": "Booking promises are restricted for this context.",
                "metadata": {"conflict_key": "booking-promise"},
            },
        ],
        feature_flags={"harness_enabled": True},
        granted_tools=["book_appointment"],
    )

    assert decision["verdict"] == "escalate"
    assert "allow-booking" in decision["matched_rules"]
    assert "deny-booking" in decision["matched_rules"]
    assert any("Compliance conflict" in reason for reason in decision["reasons"])


def test_policy_gate_escalate_rules_are_honored() -> None:
    decision = evaluate_policy(
        tool_name="book_appointment",
        worker_id="customer-analyst",
        tenant_id="tenant-alpha",
        approval_override=False,
        tenant_config={"industry_pack_id": "hvac"},
        compliance_rules=[
            {
                "id": "review-booking",
                "target": "book_appointment",
                "effect": "escalate",
                "reason": "Manual review required before confirming this booking.",
            }
        ],
        feature_flags={"harness_enabled": True},
        granted_tools=["book_appointment"],
    )

    assert decision["verdict"] == "escalate"
    assert decision["matched_rules"] == ["review-booking"]


def test_pii_redactor_masks_email_and_phone() -> None:
    redacted = redact_pii("Call me at 313-555-1212 or email ops@example.com")
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted

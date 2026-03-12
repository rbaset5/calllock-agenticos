from __future__ import annotations

from typing import Any


def evaluate_policy(
    *,
    tool_name: str | None,
    tenant_config: dict[str, Any],
    compliance_rules: list[dict[str, Any]],
    feature_flags: dict[str, bool],
    granted_tools: list[str],
) -> dict[str, Any]:
    if tool_name and tool_name not in granted_tools:
        return {
            "verdict": "deny",
            "reasons": [f"Tool '{tool_name}' is not granted for this tenant run."],
            "matched_rules": [],
        }

    if not feature_flags.get("harness_enabled", True):
        return {"verdict": "deny", "reasons": ["Harness feature flag disabled."], "matched_rules": []}

    matching = [
        rule
        for rule in compliance_rules
        if rule.get("target") in ("*", tool_name, tenant_config.get("industry_pack_id"))
    ]
    deny_rules = [rule for rule in matching if rule.get("effect") == "deny"]
    allow_rules = [rule for rule in matching if rule.get("effect") == "allow"]

    if deny_rules:
        return {
            "verdict": "deny",
            "reasons": [rule.get("reason", "Denied by compliance rule.") for rule in deny_rules],
            "matched_rules": [rule["id"] for rule in deny_rules if "id" in rule],
        }
    if allow_rules or tool_name is None:
        return {
            "verdict": "allow",
            "reasons": ["Allowed by explicit rule." if allow_rules else "No tool invocation requested."],
            "matched_rules": [rule["id"] for rule in allow_rules if "id" in rule],
        }
    return {
        "verdict": "deny",
        "reasons": ["Deny by default: no allow rule matched."],
        "matched_rules": [],
    }


def policy_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    return {
        "policy_decision": evaluate_policy(
            tool_name=state.get("tool_name"),
            tenant_config=task.get("tenant_config", {}),
            compliance_rules=task.get("compliance_rules", []),
            feature_flags=task.get("feature_flags", {}),
            granted_tools=state.get("tool_grants", []),
        )
    }

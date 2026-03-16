from __future__ import annotations

from typing import Any

from db.repository import count_active_jobs, list_kill_switches


def _target_matches(rule: dict[str, Any], tool_name: str | None, tenant_config: dict[str, Any]) -> bool:
    target = rule.get("target")
    if target == "*":
        return True
    if tool_name and target == tool_name:
        return True
    return target == tenant_config.get("industry_pack_id")


def _conflict_key(rule: dict[str, Any]) -> str:
    metadata = rule.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return str(metadata.get("conflict_key") or metadata.get("disclosure_key") or rule.get("target") or "*")


def resolve_compliance_outcome(
    compliance_rules: list[dict[str, Any]],
    *,
    tool_name: str | None,
    tenant_config: dict[str, Any],
    escalate_policy_violations: bool,
) -> dict[str, Any]:
    matching = [rule for rule in compliance_rules if _target_matches(rule, tool_name, tenant_config)]
    if not matching:
        return {
            "verdict": "escalate" if escalate_policy_violations else "deny",
            "reasons": ["Deny by default: no allow rule matched."],
            "matched_rules": [],
        }

    matching_by_key: dict[str, list[dict[str, Any]]] = {}
    for rule in matching:
        matching_by_key.setdefault(_conflict_key(rule), []).append(rule)

    conflicting_groups = []
    for rules in matching_by_key.values():
        effects = {rule.get("effect") for rule in rules}
        if len(effects) > 1:
            conflicting_groups.append(rules)

    if conflicting_groups:
        matched_rules = [
            rule["id"]
            for rules in conflicting_groups
            for rule in rules
            if "id" in rule
        ]
        reasons = []
        for rules in conflicting_groups:
            target = rules[0].get("target", "*")
            effects = sorted({str(rule.get("effect", "deny")) for rule in rules})
            reasons.append(f"Compliance conflict for '{target}': {', '.join(effects)} rules matched; blocked pending review.")
            reasons.extend(rule.get("reason", "Conflicting compliance rule.") for rule in rules)
        return {"verdict": "escalate", "reasons": reasons, "matched_rules": matched_rules}

    deny_rules = [rule for rule in matching if rule.get("effect") == "deny"]
    if deny_rules:
        if escalate_policy_violations:
            return {
                "verdict": "escalate",
                "reasons": [rule.get("reason", "Escalated by compliance rule.") for rule in deny_rules],
                "matched_rules": [rule["id"] for rule in deny_rules if "id" in rule],
            }
        return {
            "verdict": "deny",
            "reasons": [rule.get("reason", "Denied by compliance rule.") for rule in deny_rules],
            "matched_rules": [rule["id"] for rule in deny_rules if "id" in rule],
        }

    escalate_rules = [rule for rule in matching if rule.get("effect") == "escalate"]
    if escalate_rules:
        return {
            "verdict": "escalate",
            "reasons": [rule.get("reason", "Escalated by compliance rule.") for rule in escalate_rules],
            "matched_rules": [rule["id"] for rule in escalate_rules if "id" in rule],
        }

    allow_rules = [rule for rule in matching if rule.get("effect") == "allow"]
    if allow_rules or tool_name is None:
        return {
            "verdict": "allow",
            "reasons": ["Allowed by explicit rule." if allow_rules else "No tool invocation requested."],
            "matched_rules": [rule["id"] for rule in allow_rules if "id" in rule],
        }
    return {
        "verdict": "escalate" if escalate_policy_violations else "deny",
        "reasons": ["Deny by default: no allow rule matched."],
        "matched_rules": [],
    }


def _matching_kill_switch(worker_id: str | None, tenant_id: str | None) -> dict[str, Any] | None:
    for kill_switch in list_kill_switches(active_only=True):
        scope = kill_switch["scope"]
        if scope == "global":
            return kill_switch
        if scope == "worker" and worker_id and kill_switch.get("scope_id") == worker_id:
            return kill_switch
        if scope == "tenant" and tenant_id and kill_switch.get("scope_id") == tenant_id:
            return kill_switch
    return None


def evaluate_policy(
    *,
    tool_name: str | None,
    worker_id: str | None,
    tenant_id: str | None,
    approval_override: bool,
    tenant_config: dict[str, Any],
    compliance_rules: list[dict[str, Any]],
    feature_flags: dict[str, bool],
    granted_tools: list[str],
) -> dict[str, Any]:
    kill_switch = _matching_kill_switch(worker_id, tenant_id)
    if kill_switch is not None:
        return {
            "verdict": "deny",
            "reasons": [f"Execution blocked by {kill_switch['scope']} kill switch: {kill_switch['reason']}"],
            "matched_rules": [kill_switch["id"]],
        }

    if approval_override:
        return {
            "verdict": "allow",
            "reasons": ["Allowed by explicit operator approval override."],
            "matched_rules": [],
        }

    if tool_name and tool_name not in granted_tools:
        return {
            "verdict": "deny",
            "reasons": [f"Tool '{tool_name}' is not granted for this tenant run."],
            "matched_rules": [],
        }

    if not feature_flags.get("harness_enabled", True):
        return {"verdict": "deny", "reasons": ["Harness feature flag disabled."], "matched_rules": []}

    max_active_jobs = tenant_config.get("max_active_jobs", 5)
    if tenant_id and count_active_jobs(tenant_id) >= max_active_jobs:
        return {
            "verdict": "deny",
            "reasons": [f"Tenant has reached the active job limit of {max_active_jobs}."],
            "matched_rules": [],
        }
    return resolve_compliance_outcome(
        compliance_rules,
        tool_name=tool_name,
        tenant_config=tenant_config,
        escalate_policy_violations=bool(tenant_config.get("escalate_policy_violations")),
    )


def policy_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    return {
        "policy_decision": evaluate_policy(
            tool_name=state.get("tool_name"),
            worker_id=state.get("worker_id"),
            tenant_id=state.get("tenant_id"),
            approval_override=bool(task.get("approval_override")),
            tenant_config=task.get("tenant_config", {}),
            compliance_rules=task.get("compliance_rules", []),
            feature_flags=task.get("feature_flags", {}),
            granted_tools=state.get("tool_grants", []),
        )
    }

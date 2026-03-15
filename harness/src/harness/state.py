from __future__ import annotations

from typing import Any, Literal, TypedDict


PolicyVerdict = Literal["allow", "deny", "escalate"]


class HarnessMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class PolicyDecision(TypedDict, total=False):
    verdict: PolicyVerdict
    reasons: list[str]
    matched_rules: list[str]


class VerificationResult(TypedDict, total=False):
    passed: bool
    reasons: list[str]


class HarnessState(TypedDict, total=False):
    tenant_id: str
    run_id: str
    worker_id: str
    task: dict[str, Any]
    messages: list[HarnessMessage]
    context_items: list[dict[str, Any]]
    context_budget_remaining: int
    tool_name: str
    tool_args: dict[str, Any]
    tool_grants: list[str]
    policy_decision: PolicyDecision
    worker_output: dict[str, Any]
    verification: VerificationResult
    persistence: dict[str, Any]

from __future__ import annotations

from typing import Any, Literal, TypedDict


PolicyVerdict = Literal["allow", "deny", "escalate"]
VerificationVerdict = Literal["pass", "retry", "block", "escalate"]


class HarnessMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class PolicyDecision(TypedDict, total=False):
    verdict: PolicyVerdict
    reasons: list[str]
    matched_rules: list[str]


class VerificationResult(TypedDict, total=False):
    passed: bool
    verdict: VerificationVerdict
    reasons: list[str]
    findings: list[dict[str, Any]]


class GuardianGateResult(TypedDict, total=False):
    gate_passed: bool
    quarantine: bool
    gate_failures: list[str]


RunStatus = Literal[
    "queued",
    "context_assembly",
    "policy_check",
    "executing",
    "verifying",
    "gate_check",
    "dispatching",
    "persisting",
    "completed",
    "quarantined",
    "failed",
]


class HarnessState(TypedDict, total=False):
    tenant_id: str
    run_id: str
    worker_id: str
    current_state: str
    run_status: RunStatus
    task: dict[str, Any]
    messages: list[HarnessMessage]
    context_items: list[dict[str, Any]]
    context_budget_remaining: int
    tool_name: str
    tool_args: dict[str, Any]
    tool_grants: list[str]
    policy_decision: PolicyDecision
    worker_output: dict[str, Any]
    retry_count: int
    job_requests: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    verification: VerificationResult
    guardian_gate: GuardianGateResult
    persistence: dict[str, Any]

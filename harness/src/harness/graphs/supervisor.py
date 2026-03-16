from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]

from harness.nodes.context_assembly import assemble_context, context_assembly_node
from harness.jobs.dispatch import dispatch_job_requests
from harness.nodes.persist import build_persist_record, persist_node
from harness.nodes.policy_gate import evaluate_policy, policy_gate_node
from harness.nodes.verification import verify_output, verification_node
from harness.tool_registry import resolve_granted_tools
from harness.graphs.workers import get_worker
from harness.state import HarnessState


def _worker_node(state: HarnessState) -> dict[str, Any]:
    worker = get_worker(state["worker_id"])
    output = worker(state["task"])
    return {
        "worker_output": output,
        "job_requests": state["task"].get("job_requests", []) + output.get("job_requests", []),
    }


def _blocked_node(state: HarnessState) -> dict[str, Any]:
    return {
        "worker_output": {"status": "blocked"},
        "verification": {"passed": False, "verdict": "block", "reasons": state["policy_decision"]["reasons"], "findings": []},
    }


def _policy_route(state: HarnessState) -> str:
    return "worker" if state["policy_decision"]["verdict"] == "allow" else "blocked"


def _job_dispatch_node(state: HarnessState) -> dict[str, Any]:
    if state.get("verification", {}).get("verdict") != "pass":
        return {"jobs": []}
    return {
        "jobs": dispatch_job_requests(
            state.get("job_requests", []),
            tenant_id=state["tenant_id"],
            origin_worker_id=state["worker_id"],
            origin_run_id=state["run_id"],
        )
    }


def _verification_route(state: HarnessState) -> str:
    return "job_dispatch" if state.get("verification", {}).get("verdict") == "pass" else "persist"


def compile_supervisor_graph() -> Any:
    if StateGraph is None:
        return "context_assembly -> policy_gate -> worker -> verification -> persist"
    graph = StateGraph(HarnessState)
    graph.add_node("context_assembly", context_assembly_node)
    graph.add_node("policy_gate", policy_gate_node)
    graph.add_node("worker", _worker_node)
    graph.add_node("blocked", _blocked_node)
    graph.add_node("verification", verification_node)
    graph.add_node("job_dispatch", _job_dispatch_node)
    graph.add_node("persist", persist_node)
    graph.set_entry_point("context_assembly")
    graph.add_edge("context_assembly", "policy_gate")
    graph.add_conditional_edges("policy_gate", _policy_route, {"worker": "worker", "blocked": "blocked"})
    graph.add_edge("worker", "verification")
    graph.add_conditional_edges("verification", _verification_route, {"job_dispatch": "job_dispatch", "persist": "persist"})
    graph.add_edge("job_dispatch", "persist")
    graph.add_edge("blocked", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


def run_supervisor(state: HarnessState) -> HarnessState:
    worker_spec = state["task"]["worker_spec"]
    tenant_config = state["task"].get("tenant_config", {})

    authored_tools = worker_spec.get("tools_allowed", [])
    state["tool_grants"] = resolve_granted_tools(
        authored_tools,
        tenant_allowed=tenant_config.get("allowed_tools"),
        environment_allowed=state["task"].get("environment_allowed_tools"),
        runtime_denied=tenant_config.get("runtime_denied_tools"),
    )
    compiled = compile_supervisor_graph()
    if hasattr(compiled, "invoke"):
        result = compiled.invoke(state)
        state.update(result)
        return state

    assembled = assemble_context(
        worker_spec=worker_spec,
        task_context=state["task"],
        tenant_config=tenant_config,
        industry_pack=state["task"].get("industry_pack", {}),
        knowledge_nodes=state["task"].get("knowledge_nodes", []),
        memory=state["task"].get("memory", []),
        history=state["task"].get("history", []),
        budget_tokens=state["task"].get("context_budget", 1200),
    )
    state["context_items"] = assembled["items"]
    state["context_budget_remaining"] = assembled["budget_remaining"]
    state["policy_decision"] = evaluate_policy(
        tool_name=state.get("tool_name"),
        worker_id=state.get("worker_id"),
        tenant_id=state.get("tenant_id"),
        approval_override=bool(state["task"].get("approval_override")),
        tenant_config=tenant_config,
        compliance_rules=state["task"].get("compliance_rules", []),
        feature_flags=state["task"].get("feature_flags", {}),
        granted_tools=state["tool_grants"],
    )
    if state["policy_decision"]["verdict"] != "allow":
        state["worker_output"] = {"status": "blocked"}
        state["verification"] = {"passed": False, "verdict": "block", "reasons": state["policy_decision"]["reasons"], "findings": []}
        state.update(persist_node(state))
        return state

    state["worker_output"] = get_worker(state["worker_id"])(state["task"])
    state["job_requests"] = state["task"].get("job_requests", []) + state["worker_output"].get("job_requests", [])
    state["verification"] = verify_output(
        state["worker_output"],
        worker_id=state["worker_id"],
        worker_spec=worker_spec,
        tenant_config=tenant_config,
        context_items=state["context_items"],
        retry_count=state.get("retry_count", 0),
    )
    state["jobs"] = (
        dispatch_job_requests(
            state.get("job_requests", []),
            tenant_id=state["tenant_id"],
            origin_worker_id=state["worker_id"],
            origin_run_id=state["run_id"],
        )
        if state["verification"]["verdict"] == "pass"
        else []
    )
    state.update(persist_node(state))
    return state

from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]

from harness.nodes.context_assembly import assemble_context, context_assembly_node
from harness.nodes.persist import build_persist_record, persist_node
from harness.nodes.policy_gate import evaluate_policy, policy_gate_node
from harness.nodes.verification import verify_output, verification_node
from harness.tool_registry import resolve_granted_tools
from harness.graphs.workers.customer_analyst import run_customer_analyst
from harness.state import HarnessState


def _worker_node(state: HarnessState) -> dict[str, Any]:
    return {"worker_output": run_customer_analyst(state["task"])}


def _blocked_node(state: HarnessState) -> dict[str, Any]:
    return {
        "worker_output": {"status": "blocked"},
        "verification": {"passed": False, "reasons": state["policy_decision"]["reasons"]},
    }


def _policy_route(state: HarnessState) -> str:
    return "worker" if state["policy_decision"]["verdict"] == "allow" else "blocked"


def compile_supervisor_graph() -> Any:
    if StateGraph is None:
        return "context_assembly -> policy_gate -> worker -> verification -> persist"
    graph = StateGraph(HarnessState)
    graph.add_node("context_assembly", context_assembly_node)
    graph.add_node("policy_gate", policy_gate_node)
    graph.add_node("worker", _worker_node)
    graph.add_node("blocked", _blocked_node)
    graph.add_node("verification", verification_node)
    graph.add_node("persist", persist_node)
    graph.set_entry_point("context_assembly")
    graph.add_edge("context_assembly", "policy_gate")
    graph.add_conditional_edges("policy_gate", _policy_route, {"worker": "worker", "blocked": "blocked"})
    graph.add_edge("worker", "verification")
    graph.add_edge("verification", "persist")
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
        tenant_config=tenant_config,
        compliance_rules=state["task"].get("compliance_rules", []),
        feature_flags=state["task"].get("feature_flags", {}),
        granted_tools=state["tool_grants"],
    )
    if state["policy_decision"]["verdict"] != "allow":
        state["worker_output"] = {"status": "blocked"}
        state["verification"] = {"passed": False, "reasons": state["policy_decision"]["reasons"]}
        state["persistence"] = build_persist_record(state)
        return state

    state["worker_output"] = run_customer_analyst(state["task"])
    state["verification"] = verify_output(
        state["worker_output"],
        tenant_config=tenant_config,
        required_fields=["summary", "lead_route", "sentiment"],
    )
    state["persistence"] = build_persist_record(state)
    return state

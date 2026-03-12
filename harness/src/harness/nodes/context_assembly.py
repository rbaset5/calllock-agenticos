from __future__ import annotations

from typing import Any


PRIORITY_ORDER = [
    "worker_spec",
    "task_context",
    "tenant_config",
    "industry_pack",
    "knowledge_graph",
    "memory",
    "history",
]


def _text_for(item: dict[str, Any]) -> str:
    return str(item.get("content", ""))


def _approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def assemble_context(
    *,
    worker_spec: dict[str, Any],
    task_context: dict[str, Any],
    tenant_config: dict[str, Any],
    industry_pack: dict[str, Any],
    knowledge_nodes: list[dict[str, Any]],
    memory: list[dict[str, Any]],
    history: list[dict[str, Any]],
    budget_tokens: int,
) -> dict[str, Any]:
    items = [
        {"source": "worker_spec", "content": worker_spec.get("mission", "")},
        {"source": "task_context", "content": task_context.get("problem_description", "")},
        {"source": "tenant_config", "content": str(tenant_config)},
        {"source": "industry_pack", "content": str(industry_pack.get("summary", industry_pack))},
    ]
    items.extend({"source": "knowledge_graph", "content": node.get("summary", "")} for node in knowledge_nodes)
    items.extend({"source": "memory", "content": item.get("content", "")} for item in memory)
    items.extend({"source": "history", "content": item.get("content", "")} for item in history)

    kept: list[dict[str, Any]] = []
    remaining = budget_tokens
    for source in PRIORITY_ORDER:
        for item in [candidate for candidate in items if candidate["source"] == source]:
            cost = _approx_tokens(_text_for(item))
            if cost <= remaining:
                kept.append(item)
                remaining -= cost
    return {"items": kept, "budget_remaining": remaining}


def context_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    assembled = assemble_context(
        worker_spec=task["worker_spec"],
        task_context=task,
        tenant_config=task.get("tenant_config", {}),
        industry_pack=task.get("industry_pack", {}),
        knowledge_nodes=task.get("knowledge_nodes", []),
        memory=task.get("memory", []),
        history=task.get("history", []),
        budget_tokens=task.get("context_budget", 1200),
    )
    return {
        "context_items": assembled["items"],
        "context_budget_remaining": assembled["budget_remaining"],
    }

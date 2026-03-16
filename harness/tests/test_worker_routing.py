import pytest

from harness.graphs.supervisor import run_supervisor
from harness.graphs.workers import get_worker


def _state(worker_id: str) -> dict:
    return {
        "tenant_id": "tenant-alpha",
        "run_id": f"run-{worker_id}",
        "worker_id": worker_id,
        "task": {
            "problem_description": "Prepare next step",
            "transcript": "Customer is upset about no heat.",
            "worker_spec": {
                "mission": "Do the thing",
                "tools_allowed": ["read_knowledge"],
                "outputs": ["summary"] if worker_id == "customer-analyst" else ["plans"],
            },
            "tenant_config": {"allowed_tools": ["read_knowledge"], "tone_profile": {"formality": "direct", "banned_words": []}},
            "industry_pack": {"summary": "HVAC pack"},
            "knowledge_nodes": [{"summary": "No heat should route quickly."}],
            "feature_flags": {"harness_enabled": True, "llm_workers_enabled": False},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow"}],
        },
    }


def test_worker_registry_raises_for_unknown_worker() -> None:
    with pytest.raises(KeyError):
        get_worker("unknown")


def test_supervisor_routes_to_configured_worker() -> None:
    state = _state("product-manager")
    state["task"]["worker_spec"]["outputs"] = ["plans", "prioritized requirements", "decision memos"]
    result = run_supervisor(state)
    assert "plans" in result["worker_output"]

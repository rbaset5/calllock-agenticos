from harness.graphs.supervisor import run_supervisor


def test_supervisor_runs_customer_analyst_flow() -> None:
    state = {
        "tenant_id": "tenant-alpha",
        "run_id": "run-1",
        "worker_id": "customer-analyst",
        "tool_name": None,
        "task": {
            "problem_description": "No heat in the house",
            "transcript": "Customer is upset and has no heat tonight.",
            "worker_spec": {
                "mission": "Analyze post-call outcomes.",
                "tools_allowed": ["notify_dispatch"],
            },
            "tenant_config": {"allowed_tools": ["notify_dispatch"]},
            "industry_pack": {"summary": "HVAC pack"},
            "knowledge_nodes": [{"summary": "Emergency no-heat calls should route to dispatch."}],
            "feature_flags": {"harness_enabled": True},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow"}],
        },
    }
    result = run_supervisor(state)
    assert result["policy_decision"]["verdict"] == "allow"
    assert result["verification"]["passed"] is True
    assert result["worker_output"]["lead_route"] == "dispatcher"

from db.repository import list_approval_requests
from harness.approval_resume import continue_approved_request
from harness.nodes.persist import persist_node


def test_persist_node_creates_approval_request_for_escalation() -> None:
    result = persist_node(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-approval",
            "worker_id": "engineer",
            "task": {"worker_spec": {"approval_boundaries": ["schema changes"]}},
            "policy_decision": {"verdict": "allow", "reasons": []},
            "worker_output": {"code": "alter table jobs add column flag boolean"},
            "verification": {"passed": False, "verdict": "escalate", "reasons": ["Schema change requires approval"]},
        }
    )
    approval = result["persistence"]["approval_request"]
    assert approval["status"] == "pending"
    assert approval["request_type"] == "verification"
    assert len(list_approval_requests(status="pending")) == 1


def test_policy_approval_resume_runs_supervisor_after_approval() -> None:
    result = persist_node(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-policy-approval",
            "worker_id": "customer-analyst",
            "task": {
                "problem_description": "No heat",
                "transcript": "Customer says there is no heat tonight.",
                "worker_spec": {
                    "mission": "Analyze post-call outcomes.",
                    "tools_allowed": ["notify_dispatch"],
                    "outputs": ["lead routing decisions", "summary", "sentiment", "churn risk"],
                },
                "tenant_config": {
                    "allowed_tools": ["notify_dispatch"],
                    "tone_profile": {"formality": "direct", "banned_words": []},
                    "escalate_policy_violations": True,
                },
                "industry_pack": {"summary": "HVAC pack"},
                "knowledge_nodes": [{"summary": "Emergency no-heat calls should route to dispatch."}],
                "feature_flags": {"harness_enabled": True, "llm_workers_enabled": False},
                "compliance_rules": [],
            },
            "policy_decision": {"verdict": "escalate", "reasons": ["No allow rule matched"]},
            "worker_output": {"status": "blocked"},
            "verification": {"passed": False, "verdict": "block", "reasons": ["Awaiting approval"]},
        }
    )
    approval = result["persistence"]["approval_request"]
    continued = continue_approved_request(
        approval,
        actor_id="operator-1",
        resolution_notes="Approved for manual override",
    )
    assert continued["mode"] == "policy_resume"
    assert continued["state"]["policy_decision"]["verdict"] == "allow"
    assert continued["state"]["worker_output"]["lead_route"] == "dispatcher"

from harness.graphs.workers import base
from harness.graphs.workers.customer_analyst import run_customer_analyst


def test_customer_analyst_uses_llm_path_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        base,
        "call_llm",
        lambda prompt, output_fields: {
            "summary": "Customer needs urgent dispatch",
            "lead_route": "dispatcher",
            "sentiment": "negative",
            "churn_risk": "low",
        },
    )
    output = run_customer_analyst(
        {
            "problem_description": "No heat",
            "transcript": "Customer is upset and has no heat.",
            "worker_spec": {"outputs": ["summary", "lead routing decisions", "sentiment", "churn risk"]},
            "tenant_config": {"tone_profile": {"formality": "direct", "banned_words": []}},
            "feature_flags": {"llm_workers_enabled": True},
        }
    )
    assert output["lead_route"] == "dispatcher"

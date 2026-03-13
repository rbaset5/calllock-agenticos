from harness.graphs.workers.customer_analyst import run_customer_analyst


def test_customer_analyst_falls_back_to_deterministic_mode() -> None:
    output = run_customer_analyst(
        {
            "problem_description": "No heat",
            "transcript": "Customer is upset and has no heat.",
            "worker_spec": {"outputs": ["summary", "lead routing decisions", "sentiment", "churn risk"]},
            "tenant_config": {"deterministic_mode": True, "tone_profile": {"formality": "direct", "banned_words": []}},
            "feature_flags": {"llm_workers_enabled": True},
        }
    )
    assert output["lead_route"] == "dispatcher"

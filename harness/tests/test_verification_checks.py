from harness.nodes.verification import verify_output


def test_verification_blocks_forbidden_phrase() -> None:
    result = verify_output(
        {"summary": "guaranteed savings", "lead_route": "sales", "sentiment": "positive", "churn_risk": "low"},
        worker_id="customer-analyst",
        worker_spec={"outputs": ["summary", "lead routing decisions", "sentiment", "churn risk"]},
        tenant_config={"tone_profile": {"formality": "direct", "banned_words": []}},
        context_items=[{"content": "Customer asked for help with maintenance savings."}],
    )
    assert result["verdict"] == "block"


def test_verification_retries_when_context_does_not_support_claim() -> None:
    result = verify_output(
        {"summary": "Customer needs boiler replacement", "lead_route": "sales", "sentiment": "neutral", "churn_risk": "low"},
        worker_id="customer-analyst",
        worker_spec={"outputs": ["summary", "lead routing decisions", "sentiment", "churn risk"]},
        tenant_config={"tone_profile": {"formality": "direct", "banned_words": []}},
        context_items=[{"content": "Customer needs AC tune-up."}],
    )
    assert result["verdict"] == "retry"

import pytest

from harness.content_pipeline.pipeline import process_customer_content
from harness.improvement.experiments import run_experiment


def test_improvement_lab_runs_experiment() -> None:
    result = run_experiment(
        {
            "mutation_surface": "prompt:customer-analyst",
            "proposal": "tighten routing prompt",
            "baseline_score": 0.7,
            "candidate_score": 0.8,
        }
    )
    assert result["outcome"] == "keep"


def test_content_pipeline_redacts_pii() -> None:
    record = process_customer_content(
        {
            "tenant_id": "tenant-alpha",
            "call_id": "call-1",
            "transcript": "Call me at 313-555-1212",
            "consent_granted": True,
        }
    )
    assert "[REDACTED_PHONE]" in record["sanitized_transcript"]

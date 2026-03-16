from harness.graphs.workers.designer import run_designer
from harness.graphs.workers.engineer import run_engineer
from harness.graphs.workers.product_manager import run_product_manager
from harness.graphs.workers.product_marketer import run_product_marketer


def _task(outputs: list[str]) -> dict:
    return {
        "problem_description": "Prepare an update",
        "worker_spec": {"outputs": outputs},
        "tenant_config": {"deterministic_mode": True, "tone_profile": {"formality": "direct", "banned_words": []}},
        "feature_flags": {"llm_workers_enabled": False},
    }


def test_product_manager_output_shape() -> None:
    output = run_product_manager(_task(["plans", "prioritized requirements", "decision memos"]))
    assert set(output) >= {"plans", "prioritized_requirements", "decision_memos"}


def test_engineer_output_shape() -> None:
    output = run_engineer(_task(["code", "tests", "migration plans"]))
    assert set(output) >= {"code", "tests", "migration_plans"}


def test_designer_output_shape() -> None:
    output = run_designer(_task(["design specs", "content patterns", "interaction flows"]))
    assert set(output) >= {"design_specs", "content_patterns", "interaction_flows"}


def test_product_marketer_output_shape() -> None:
    output = run_product_marketer(_task(["messaging", "release notes", "campaign drafts"]))
    assert set(output) >= {"messaging", "release_notes", "campaign_drafts"}

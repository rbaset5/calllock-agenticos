from harness.evals.registry import discover_eval_datasets
from harness.evals.runner import run_eval_suite


def test_eval_registry_discovers_datasets() -> None:
    datasets = discover_eval_datasets()
    assert len(datasets) >= 10


def test_core_eval_suite_runs() -> None:
    result = run_eval_suite(level="core")
    assert result["level"] == "core"
    assert result["overall_score"] >= 0


def test_tenant_eval_suite_runs_with_tenant_scope() -> None:
    result = run_eval_suite(level="tenant", tenant_id="00000000-0000-0000-0000-000000000001")
    assert result["level"] == "tenant"

from __future__ import annotations

from statistics import mean
from typing import Any
from uuid import uuid4

from db.repository import get_tenant_config, list_eval_runs, save_eval_run
from harness.evals.registry import discover_eval_datasets
from harness.graphs.workers.customer_analyst import run_customer_analyst
from harness.graphs.workers.designer import run_designer
from harness.graphs.workers.engineer import run_engineer
from harness.graphs.workers.product_manager import run_product_manager
from harness.graphs.workers.product_marketer import run_product_marketer


def _task(input_text: str, tenant_id: str | None = None) -> dict[str, Any]:
    tenant_config = get_tenant_config(tenant_id) if tenant_id else {"deterministic_mode": True, "tone_profile": {"formality": "direct", "banned_words": []}}
    tenant_config.setdefault("deterministic_mode", True)
    tenant_config.setdefault("tone_profile", {"formality": "direct", "banned_words": []})
    return {
        "problem_description": input_text,
        "transcript": input_text,
        "worker_spec": {},
        "tenant_config": tenant_config,
        "feature_flags": {"llm_workers_enabled": False},
    }


def _evaluate_customer_analyst(metric: str, example: dict[str, Any], tenant_id: str | None) -> bool:
    output = run_customer_analyst(
        {
            **_task(example["input"], tenant_id),
            "worker_spec": {"outputs": ["summary", "lead routing decisions", "sentiment", "churn risk"]},
        }
    )
    if metric == "routing-accuracy":
        return output["lead_route"] == example["expected"]
    if metric == "sentiment-accuracy":
        return output["sentiment"] == example["expected"]
    return False


def _evaluate_generic(worker_id: str, example: dict[str, Any], tenant_id: str | None) -> bool:
    task = _task(example["input"], tenant_id)
    if worker_id == "product-manager":
        output = run_product_manager({**task, "worker_spec": {"outputs": ["plans", "prioritized requirements", "decision memos"]}})
        return bool(output["plans"] and output["prioritized_requirements"] and output["decision_memos"])
    if worker_id == "engineer":
        output = run_engineer({**task, "worker_spec": {"outputs": ["code", "tests", "migration plans"]}})
        return bool(output["code"] and output["tests"] and output["migration_plans"])
    if worker_id == "designer":
        output = run_designer({**task, "worker_spec": {"outputs": ["design specs", "content patterns", "interaction flows"]}})
        return bool(output["design_specs"] and output["content_patterns"] and output["interaction_flows"])
    if worker_id == "product-marketer":
        output = run_product_marketer({**task, "worker_spec": {"outputs": ["messaging", "release notes", "campaign drafts"]}})
        return bool(output["messaging"] and output["release_notes"] and output["campaign_drafts"])
    return False


def run_eval_suite(*, level: str, tenant_id: str | None = None, target: str | None = None) -> dict[str, Any]:
    datasets = discover_eval_datasets()
    selected = []
    for dataset in datasets:
        if level == "tenant":
            if tenant_id is None:
                continue
        elif dataset["level"] != level:
            continue
        if target and dataset["worker_id"] != target and dataset["metric"] != target:
            continue
        selected.append(dataset)

    dataset_results = []
    for dataset in selected:
        checks = []
        for example in dataset["examples"]:
            if dataset["worker_id"] == "customer-analyst":
                passed = _evaluate_customer_analyst(dataset["metric"], example, tenant_id)
            else:
                passed = _evaluate_generic(dataset["worker_id"], example, tenant_id)
            checks.append({"input": example["input"], "expected": example["expected"], "passed": passed})
        score = mean(1.0 if check["passed"] else 0.0 for check in checks) if checks else 0.0
        dataset_results.append(
            {
                "dataset_id": dataset["id"],
                "worker_id": dataset["worker_id"],
                "metric": dataset["metric"],
                "score": score,
                "checks": checks,
            }
        )

    overall_score = mean(result["score"] for result in dataset_results) if dataset_results else 0.0
    run = {
        "id": str(uuid4()),
        "level": level,
        "tenant_id": tenant_id,
        "target": target,
        "overall_score": overall_score,
        "dataset_results": dataset_results,
    }
    return save_eval_run(run)


def list_eval_runs_for_api(tenant_id: str | None = None, level: str | None = None) -> list[dict[str, Any]]:
    runs = list_eval_runs(tenant_id=tenant_id)
    if level is not None:
        runs = [run for run in runs if run["level"] == level]
    return runs

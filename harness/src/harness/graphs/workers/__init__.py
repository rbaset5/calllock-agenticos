"""Worker graph modules."""
from __future__ import annotations

from typing import Callable

from harness.graphs.workers.base import load_worker_spec, run_worker
from harness.graphs.workers.customer_analyst import run_customer_analyst
from harness.graphs.workers.designer import run_designer
from harness.graphs.workers.engineer import run_engineer
from harness.graphs.workers.product_manager import run_product_manager
from harness.graphs.workers.product_marketer import run_product_marketer


WORKER_REGISTRY: dict[str, Callable[[dict], dict]] = {
    "customer-analyst": run_customer_analyst,
    "product-manager": run_product_manager,
    "engineer": run_engineer,
    "designer": run_designer,
    "product-marketer": run_product_marketer,
}


def _build_spec_backed_worker(worker_id: str) -> Callable[[dict], dict]:
    load_worker_spec(worker_id)

    def _run_spec_worker(task: dict) -> dict:
        return run_worker(
            task,
            worker_id=worker_id,
            deterministic_builder=lambda _task: {},
        )

    return _run_spec_worker


def get_worker(worker_id: str) -> Callable[[dict], dict]:
    if worker_id not in WORKER_REGISTRY:
        try:
            return _build_spec_backed_worker(worker_id)
        except FileNotFoundError as exc:
            raise KeyError(f"Unknown worker_id: {worker_id}") from exc
    return WORKER_REGISTRY[worker_id]

from harness.graphs.workers import WORKER_REGISTRY


def test_worker_registry_contains_all_phase3_workers() -> None:
    assert sorted(WORKER_REGISTRY) == [
        "customer-analyst",
        "designer",
        "engineer",
        "product-manager",
        "product-marketer",
    ]

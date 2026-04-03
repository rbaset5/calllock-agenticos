from harness.graphs.workers import WORKER_REGISTRY, get_worker
from harness.graphs.workers.base import expected_output_fields, load_worker_spec


def test_worker_registry_contains_all_phase3_workers() -> None:
    assert sorted(WORKER_REGISTRY) == [
        "customer-analyst",
        "designer",
        "eng-product-qa",
        "engineer",
        "product-manager",
        "product-marketer",
    ]


def test_voice_split_workers_are_available_via_specs() -> None:
    builder = load_worker_spec("voice-builder")
    truth = load_worker_spec("voice-truth")
    legacy = load_worker_spec("eng-ai-voice")
    qa = load_worker_spec("eng-product-qa")
    builder_runner = get_worker("voice-builder")
    truth_runner = get_worker("voice-truth")

    assert builder["worker_id"] == "voice-builder"
    assert truth["worker_id"] == "voice-truth"
    assert legacy["status"] == "deprecated"
    assert legacy["scheduled_tasks"] == []
    assert legacy["reactive_triggers"] == []
    assert legacy["autonomy_tiers"] == {
        "auto_merge": [],
        "agent_review": [],
        "human_review": [],
    }
    assert legacy["git_workflow"] == {
        "branch_pattern": "",
        "commit_prefix": "",
        "pr_labels": [],
        "validated_by": "voice-truth",
    }
    assert "candidate refs for truth evaluation" in builder["outputs"]
    assert "candidate refs from voice-builder" in truth["inputs"]
    assert "truth verdict reports" in truth["outputs"]
    assert "voice-truth locked eval reports" in qa["inputs"]

    builder_result = builder_runner({"tenant_config": {"deterministic_mode": True}})
    truth_result = truth_runner({"tenant_config": {"deterministic_mode": True}})

    assert sorted(builder_result) == sorted(expected_output_fields(builder))
    assert sorted(truth_result) == sorted(expected_output_fields(truth))

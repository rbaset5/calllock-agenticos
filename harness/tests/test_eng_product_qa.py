"""Tests for eng-product-qa change gate logic."""
from __future__ import annotations

from harness.graphs.workers.eng_product_qa import (
    _deterministic_gate,
    check_contract_compliance,
    classify_change_tier,
    classify_surfaces,
)


class TestClassifySurfaces:
    def test_voice_only(self):
        result = classify_surfaces(["harness/src/voice/pipeline.py"])
        assert result == {"voice": True, "app": False, "cross_surface": False}

    def test_app_only(self):
        result = classify_surfaces(["web/src/app/page.tsx"])
        assert result == {"voice": False, "app": True, "cross_surface": False}

    def test_cross_surface(self):
        result = classify_surfaces(["harness/src/voice/pipeline.py", "web/src/lib/transforms.ts"])
        assert result == {"voice": True, "app": True, "cross_surface": True}

    def test_neither(self):
        result = classify_surfaces(["README.md"])
        assert result == {"voice": False, "app": False, "cross_surface": False}


class TestContractCompliance:
    def test_voice_change_without_contract_update(self):
        violations = check_contract_compliance(["harness/src/voice/pipeline.py"])
        types = [violation["type"] for violation in violations]
        assert "missing_contract_update" in types

    def test_voice_change_with_all_contracts(self):
        violations = check_contract_compliance(
            [
                "harness/src/voice/pipeline.py",
                "knowledge/voice-pipeline/voice-contract.yaml",
                "knowledge/voice-pipeline/seam-contract.yaml",
            ]
        )
        voice_violations = [violation for violation in violations if violation["surface"] == "voice"]
        assert len(voice_violations) == 0

    def test_app_change_without_contract(self):
        violations = check_contract_compliance(["web/src/components/mail/mail-list.tsx"])
        surfaces = [violation["surface"] for violation in violations]
        assert "app" in surfaces

    def test_no_surface_change_no_violations(self):
        violations = check_contract_compliance(["README.md", "docs/something.md"])
        assert len(violations) == 0


class TestChangeTier:
    def test_deploy_script_is_human_review(self):
        assert classify_change_tier(["scripts/deploy-retell-agent.py"]) == "human-review"

    def test_contract_change_is_agent_review(self):
        assert classify_change_tier(["knowledge/voice-pipeline/seam-contract.yaml"]) == "agent-review"

    def test_readme_is_auto_merge(self):
        assert classify_change_tier(["README.md"]) == "auto-merge"


class TestDeterministicGate:
    def test_approve_when_no_violations(self):
        task = {
            "task_context": {
                "task_type": "change-gate-review",
                "changed_files": ["README.md"],
            }
        }
        result = _deterministic_gate(task)
        assert result["gate_decision"] == "approve"

    def test_block_when_missing_contract(self):
        task = {
            "task_context": {
                "task_type": "change-gate-review",
                "changed_files": ["web/src/app/page.tsx"],
            }
        }
        result = _deterministic_gate(task)
        assert result["gate_decision"] == "block"
        assert len(result["violations"]) > 0

    def test_approve_when_contracts_updated(self):
        task = {
            "task_context": {
                "task_type": "change-gate-review",
                "changed_files": [
                    "web/src/app/page.tsx",
                    "knowledge/voice-pipeline/app-contract.yaml",
                    "knowledge/voice-pipeline/seam-contract.yaml",
                ],
            }
        }
        result = _deterministic_gate(task)
        assert result["gate_decision"] == "approve"

    def test_health_check_task(self):
        task = {
            "task_context": {
                "task_type": "cross-surface-health",
            }
        }
        result = _deterministic_gate(task)
        assert result["status"] == "complete"

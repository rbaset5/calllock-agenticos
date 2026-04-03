"""eng-product-qa worker: Product Guardian change gate and health check logic."""
from __future__ import annotations

from typing import Any

from harness.graphs.workers.base import run_worker

VOICE_PATHS = [
    "knowledge/voice-pipeline/voice-contract.yaml",
    "knowledge/voice-pipeline/eval/",
    "knowledge/voice-pipeline/test-tenant.yaml",
    "harness/src/voice/",
    "scripts/deploy-retell-agent.py",
    "scripts/run-voice-eval.py",
    "knowledge/industry-packs/",
]

APP_PATHS = [
    "knowledge/voice-pipeline/app-contract.yaml",
    "web/",
]

CONTRACT_FILES = [
    "knowledge/voice-pipeline/voice-contract.yaml",
    "knowledge/voice-pipeline/app-contract.yaml",
    "knowledge/voice-pipeline/seam-contract.yaml",
]


def classify_surfaces(changed_files: list[str]) -> dict[str, bool]:
    """Classify which surfaces a PR touches based on file paths."""
    voice = any(any(changed.startswith(path) for path in VOICE_PATHS) for changed in changed_files)
    app = any(any(changed.startswith(path) for path in APP_PATHS) for changed in changed_files)
    return {"voice": voice, "app": app, "cross_surface": voice and app}


def check_contract_compliance(changed_files: list[str]) -> list[dict[str, str]]:
    """Check if contract files are updated when surface code changes."""
    violations = []
    surfaces = classify_surfaces(changed_files)
    changed_set = set(changed_files)

    if surfaces["voice"] and "knowledge/voice-pipeline/voice-contract.yaml" not in changed_set:
        violations.append(
            {
                "type": "missing_contract_update",
                "surface": "voice",
                "message": "PR touches voice pipeline code but voice-contract.yaml is not updated.",
            }
        )

    if surfaces["app"] and "knowledge/voice-pipeline/app-contract.yaml" not in changed_set:
        violations.append(
            {
                "type": "missing_contract_update",
                "surface": "app",
                "message": "PR touches app code but app-contract.yaml is not updated.",
            }
        )

    if (surfaces["voice"] or surfaces["app"]) and "knowledge/voice-pipeline/seam-contract.yaml" not in changed_set:
        violations.append(
            {
                "type": "missing_contract_update",
                "surface": "seam",
                "message": "PR touches voice or app code but seam-contract.yaml is not updated. If no field mappings changed, this may be a false positive.",
            }
        )

    return violations


def classify_change_tier(changed_files: list[str]) -> str:
    """Classify the PR into an autonomy tier."""
    human_review_patterns = [
        "scripts/deploy-retell-agent.py",
        "knowledge/industry-packs/",
    ]
    for changed in changed_files:
        if any(changed.startswith(pattern) or changed == pattern for pattern in human_review_patterns):
            return "human-review"
        if "retell" in changed.lower() and ("prompt" in changed.lower() or "model" in changed.lower()):
            return "human-review"

    for changed in changed_files:
        if changed in CONTRACT_FILES:
            return "agent-review"

    return "auto-merge"


def _deterministic_gate(task: dict[str, Any]) -> dict[str, Any]:
    """Deterministic gate decision without LLM."""
    ctx = task.get("task_context", {})
    task_type = ctx.get("task_type", "")

    if task_type == "detection-investigate":
        detection_issue = ctx.get("detection_issue", {})
        alert_type = detection_issue.get("alert_type", "unknown_detection_issue")
        triage_outcome = detection_issue.get("triage_outcome", "investigate")
        incident_key = detection_issue.get("incident_key", "")
        return {
            "summary": f"Detection coordination: {alert_type} requires {triage_outcome} triage.",
            "status": "complete",
            "next_owner": "voice-builder" if str(alert_type).startswith("voice_") else "eng-app",
            "incident_key": incident_key,
            "triage_outcome": triage_outcome,
        }

    if task_type == "change-gate-review":
        changed_files = ctx.get("changed_files", [])
        if isinstance(changed_files, str):
            changed_files = [item.strip() for item in changed_files.split(",") if item.strip()]

        surfaces = classify_surfaces(changed_files)
        violations = check_contract_compliance(changed_files)
        tier = classify_change_tier(changed_files)
        gate_decision = "approve" if not violations else "block"
        surface_label = (
            "voice+app"
            if surfaces["cross_surface"]
            else "voice"
            if surfaces["voice"]
            else "app"
            if surfaces["app"]
            else "none"
        )

        return {
            "gate_decision": gate_decision,
            "tier": tier,
            "surfaces": surfaces,
            "violations": violations,
            "changed_files_count": len(changed_files),
            "summary": f"Gate: {gate_decision.upper()} | Tier: {tier} | Surfaces: {surface_label} | Violations: {len(violations)}",
            **({"warnings": [violation["message"] for violation in violations]} if violations else {}),
        }

    return {
        "summary": f"eng-product-qa ran task: {task_type}",
        "status": "complete",
    }


def run_eng_product_qa(task: dict[str, Any]) -> dict[str, Any]:
    """Run eng-product-qa worker with domain-specific deterministic builder."""
    return run_worker(
        task,
        worker_id="eng-product-qa",
        deterministic_builder=_deterministic_gate,
    )

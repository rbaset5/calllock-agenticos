from __future__ import annotations

from copy import deepcopy
from typing import Any


OUTPUT_FIELD_ALIASES = {
    "lead routing decisions": "lead_route",
    "summary": "summary",
    "sentiment": "sentiment",
    "churn risk": "churn_risk",
    "plans": "plans",
    "prioritized requirements": "prioritized_requirements",
    "decision memos": "decision_memos",
    "code": "code",
    "tests": "tests",
    "migration plans": "migration_plans",
    "design specs": "design_specs",
    "content patterns": "content_patterns",
    "interaction flows": "interaction_flows",
    "messaging": "messaging",
    "release notes": "release_notes",
    "campaign drafts": "campaign_drafts",
}

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "customer-analyst": {
        "max_retries": 1,
        "claim_fields": ["summary"],
        "domain_safety": "customer_analyst",
    },
    "product-manager": {
        "max_retries": 1,
        "claim_fields": ["plans", "decision_memos"],
        "domain_safety": "product_manager",
    },
    "engineer": {
        "max_retries": 1,
        "claim_fields": ["code", "migration_plans"],
        "domain_safety": "engineer",
    },
    "designer": {
        "max_retries": 1,
        "claim_fields": ["design_specs", "interaction_flows"],
        "domain_safety": "designer",
    },
    "product-marketer": {
        "max_retries": 1,
        "claim_fields": ["messaging", "release_notes", "campaign_drafts"],
        "domain_safety": "product_marketer",
    },
}


def _normalize_output_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in OUTPUT_FIELD_ALIASES:
        return OUTPUT_FIELD_ALIASES[lowered]
    return lowered.replace(" ", "_").replace("-", "_")


def derive_required_fields(worker_spec: dict[str, Any]) -> list[str]:
    outputs = worker_spec.get("outputs", [])
    return [_normalize_output_name(output) for output in outputs]


def get_profile(worker_id: str, worker_spec: dict[str, Any]) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_PROFILES.get(worker_id, {"max_retries": 1, "claim_fields": [], "domain_safety": "default"}))
    profile["worker_id"] = worker_id
    profile["required_fields"] = derive_required_fields(worker_spec)
    return profile

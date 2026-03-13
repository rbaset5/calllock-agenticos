from __future__ import annotations

import re
from typing import Any


PII_PATTERNS = [
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"),
]
FORBIDDEN_PHRASES = ["guaranteed savings", "always safe", "ignore the alarm"]
BOOKING_PROMISE_TERMS = ["guaranteed appointment", "confirmed technician arrival", "we will book this now"]
OVERCLAIM_TERMS = ["guaranteed same-day", "always compliant", "100% savings"]
SCHEMA_CHANGE_TERMS = ["alter table", "drop column", "rename column", "backfill production"]
SLANG_TERMS = ["awesome", "super easy", "no worries!"]


def _joined_output(output: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in output.values():
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts)


def _context_text(context_items: list[dict[str, Any]]) -> str:
    return " ".join(str(item.get("content", "")) for item in context_items).lower()


def check_required_fields(output: dict[str, Any], required_fields: list[str]) -> list[dict[str, str]]:
    findings = []
    for field in required_fields:
        value = output.get(field)
        if value in (None, "", []):
            findings.append({"severity": "retry", "reason": f"Missing required field: {field}", "check": "required_fields"})
    return findings


def check_forbidden_phrases(output: dict[str, Any], tenant_config: dict[str, Any]) -> list[dict[str, str]]:
    findings = []
    text = _joined_output(output).lower()
    for phrase in FORBIDDEN_PHRASES + tenant_config.get("forbidden_claims", []):
        if phrase.lower() in text:
            findings.append({"severity": "block", "reason": f"Forbidden claim detected: {phrase}", "check": "forbidden_phrases"})
    return findings


def check_pii(output: dict[str, Any]) -> list[dict[str, str]]:
    text = _joined_output(output)
    for pattern in PII_PATTERNS:
        if pattern.search(text):
            return [{"severity": "block", "reason": "PII leakage detected in output", "check": "pii"}]
    return []


def check_factual_accuracy(output: dict[str, Any], *, context_items: list[dict[str, Any]], claim_fields: list[str]) -> list[dict[str, str]]:
    if not claim_fields:
        return []
    context_text = _context_text(context_items)
    findings = []
    for field in claim_fields:
        value = output.get(field)
        if not value or not isinstance(value, str):
            continue
        tokens = [token for token in re.findall(r"[a-z0-9]{4,}", value.lower()) if token not in {"customer", "tenant", "needs", "should"}]
        if tokens and not any(token in context_text for token in tokens[:5]):
            findings.append(
                {
                    "severity": "retry",
                    "reason": f"Claim in '{field}' could not be grounded in provided context",
                    "check": "factual_accuracy",
                }
            )
    return findings


def check_tone(output: dict[str, Any], tenant_config: dict[str, Any]) -> list[dict[str, str]]:
    profile = tenant_config.get("tone_profile", {})
    banned_words = [word.lower() for word in profile.get("banned_words", [])]
    formality = profile.get("formality", "direct")
    text = _joined_output(output).lower()
    findings = []
    for word in banned_words:
        if word and word in text:
            findings.append({"severity": "block", "reason": f"Banned tone word detected: {word}", "check": "tone"})
    if formality == "formal" and any(term in text for term in SLANG_TERMS):
        findings.append({"severity": "retry", "reason": "Output violates formal tone profile", "check": "tone"})
    return findings


def check_domain_safety(output: dict[str, Any], *, worker_id: str, worker_spec: dict[str, Any]) -> list[dict[str, str]]:
    text = _joined_output(output).lower()
    findings = []
    if worker_id == "customer-analyst" and any(term in text for term in BOOKING_PROMISE_TERMS):
        findings.append({"severity": "block", "reason": "Customer analyst cannot make booking promises", "check": "domain_safety"})
    if worker_id == "product-marketer" and any(term in text for term in OVERCLAIM_TERMS):
        findings.append({"severity": "block", "reason": "Marketing output contains overclaiming language", "check": "domain_safety"})
    if worker_id == "engineer" and any(term in text for term in SCHEMA_CHANGE_TERMS):
        boundaries = " ".join(worker_spec.get("approval_boundaries", [])).lower()
        if "schema" in boundaries:
            findings.append({"severity": "escalate", "reason": "Engineer output proposes schema changes requiring approval", "check": "domain_safety"})
    return findings


def run_checks(
    output: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
    tenant_config: dict[str, Any],
    context_items: list[dict[str, Any]],
    profile: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    findings.extend(check_required_fields(output, profile.get("required_fields", [])))
    findings.extend(check_forbidden_phrases(output, tenant_config))
    findings.extend(check_pii(output))
    findings.extend(check_factual_accuracy(output, context_items=context_items, claim_fields=profile.get("claim_fields", [])))
    findings.extend(check_tone(output, tenant_config))
    findings.extend(check_domain_safety(output, worker_id=worker_id, worker_spec=worker_spec))
    return findings

"""Weekly production report for the Retell-backed voice stack."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any

from db import repository

_BAD_TOOL_STATUSES = {
    "exception",
    "validation_failed",
    "auth_failed",
    "timeout_unknown",
}
_LOW_QUALITY_THRESHOLD = 80
_MIGRATION_GATE_MIN_CALLS = 25
_MIGRATION_GATE_CRITICAL_FINDINGS = 3
_MIGRATION_GATE_TOOL_FAILURE_RATE = 0.20


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _quality_score(call: Mapping[str, Any]) -> float | None:
    value = call.get("quality_score")
    if value is None:
        extracted = call.get("extracted_fields")
        if isinstance(extracted, Mapping):
            value = extracted.get("quality_score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_low_quality_call(call: Mapping[str, Any]) -> bool:
    if call.get("extraction_status") != "complete":
        return True
    score = _quality_score(call)
    return score is not None and score < _LOW_QUALITY_THRESHOLD


def _build_top_recommended_fix(
    *,
    safety_by_type: Counter[str],
    safety_by_severity: Counter[str],
    tool_failures_by_tool: Counter[str],
    low_quality_calls: int,
    missing_config_snapshots: int,
) -> dict[str, Any]:
    if safety_by_type.get("emergency_mishandled", 0) and safety_by_severity.get("critical", 0):
        return {
            "code": "critical_emergency_findings",
            "reason": "Review emergency handling failures before tuning lower-risk voice behavior.",
        }
    if safety_by_type.get("fake_booking_claim", 0):
        return {
            "code": "fake_booking_claims",
            "reason": "Fix booking-confirmation wording and booking evidence before expanding automation.",
        }
    if safety_by_type.get("callback_claim_without_callback", 0):
        return {
            "code": "callback_failures",
            "reason": "Align callback promises with successful callback tool execution.",
        }
    repeated_tool_failures = [
        tool_name for tool_name, count in sorted(tool_failures_by_tool.items())
        if count >= 2
    ]
    if repeated_tool_failures:
        return {
            "code": "repeated_tool_exceptions",
            "reason": f"Stabilize repeated tool failures for: {', '.join(repeated_tool_failures)}.",
        }
    if low_quality_calls:
        return {
            "code": "low_extraction_quality",
            "reason": "Improve extraction quality before using production reports as automation triggers.",
        }
    if missing_config_snapshots:
        return {
            "code": "config_snapshot_missing",
            "reason": "Ensure every completed call has a Retell config snapshot for debuggability.",
        }
    return {
        "code": "no_issue_detected",
        "reason": "No production-layer issue was detected in this reporting window.",
    }


def _build_migration_gate(
    *,
    total_calls: int,
    critical_findings: int,
    tool_failure_call_count: int,
) -> dict[str, Any]:
    evidence_threshold_met = total_calls >= _MIGRATION_GATE_MIN_CALLS
    reasons: list[str] = []
    if evidence_threshold_met and critical_findings >= _MIGRATION_GATE_CRITICAL_FINDINGS:
        reasons.append("repeated_critical_safety_findings")
    tool_failure_rate = (tool_failure_call_count / total_calls) if total_calls else 0.0
    if evidence_threshold_met and tool_failure_rate >= _MIGRATION_GATE_TOOL_FAILURE_RATE:
        reasons.append("repeated_tool_failure_rate")
    return {
        "retell_replacement_recommended": bool(reasons),
        "reasons": reasons,
        "evidence_threshold_met": evidence_threshold_met,
    }


def build_voice_production_report(
    *,
    tenant_id: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Build a JSON-serializable weekly production report from stored evidence."""
    if days <= 0:
        raise ValueError("days must be positive")

    ended_at = datetime.now(timezone.utc)
    started_at = ended_at - timedelta(days=days)
    created_since = started_at.isoformat()

    calls = repository.list_voice_call_records(tenant_id=tenant_id, created_since=created_since)
    tool_calls = repository.list_voice_tool_calls_for_period(tenant_id=tenant_id, created_since=created_since)
    safety_findings = repository.list_voice_safety_findings_for_period(
        tenant_id=tenant_id,
        created_since=created_since,
    )
    config_snapshots = repository.list_voice_config_snapshots_for_period(
        tenant_id=tenant_id,
        created_since=created_since,
    )

    total_calls = len(calls)
    safety_by_type = Counter(str(finding.get("finding_type")) for finding in safety_findings)
    safety_by_severity = Counter(str(finding.get("severity")) for finding in safety_findings)
    unresolved_findings = sum(1 for finding in safety_findings if finding.get("status", "open") == "open")

    failed_tool_calls = [
        call for call in tool_calls
        if call.get("status") in _BAD_TOOL_STATUSES
    ]
    tool_failures_by_tool = Counter(str(call.get("tool_name")) for call in failed_tool_calls)
    tool_failure_call_ids = {str(call.get("call_id")) for call in failed_tool_calls}

    latencies_by_tool: dict[str, list[int]] = defaultdict(list)
    for call in tool_calls:
        latency = call.get("latency_ms")
        if isinstance(latency, int):
            latencies_by_tool[str(call.get("tool_name"))].append(latency)
    tool_latency_p95_ms = {
        tool_name: value
        for tool_name, values in sorted(latencies_by_tool.items())
        if (value := _p95(values)) is not None
    }

    call_ids = {str(call.get("call_id")) for call in calls}
    snapshot_call_ids = {str(snapshot.get("call_id")) for snapshot in config_snapshots}
    missing_config_snapshots = len(call_ids - snapshot_call_ids)
    low_quality_calls = sum(1 for call in calls if _is_low_quality_call(call))
    critical_findings = safety_by_severity.get("critical", 0)

    return {
        "report_type": "voice-production-weekly",
        "tenant_id": tenant_id,
        "period": {
            "days": days,
            "started_at": created_since,
            "ended_at": ended_at.isoformat(),
        },
        "total_calls": total_calls,
        "booked_calls": sum(1 for call in calls if call.get("booking_id")),
        "callback_calls": sum(1 for call in calls if call.get("callback_scheduled")),
        "safety_findings": {
            "total": len(safety_findings),
            "by_type": _counter_dict(str(finding.get("finding_type")) for finding in safety_findings),
            "by_severity": _counter_dict(str(finding.get("severity")) for finding in safety_findings),
        },
        "tool_failures": {
            "total": len(failed_tool_calls),
            "by_tool": dict(sorted(tool_failures_by_tool.items())),
        },
        "tool_latency_p95_ms": tool_latency_p95_ms,
        "extraction_drift": {
            "low_quality_calls": low_quality_calls,
            "low_quality_rate": round((low_quality_calls / total_calls), 4) if total_calls else 0.0,
        },
        "config_snapshots": {
            "present": len(snapshot_call_ids & call_ids),
            "missing": missing_config_snapshots,
        },
        "unresolved_findings": unresolved_findings,
        "top_recommended_fix": _build_top_recommended_fix(
            safety_by_type=safety_by_type,
            safety_by_severity=safety_by_severity,
            tool_failures_by_tool=tool_failures_by_tool,
            low_quality_calls=low_quality_calls,
            missing_config_snapshots=missing_config_snapshots,
        ),
        "migration_gate": _build_migration_gate(
            total_calls=total_calls,
            critical_findings=critical_findings,
            tool_failure_call_count=len(tool_failure_call_ids),
        ),
    }


__all__ = ["build_voice_production_report"]

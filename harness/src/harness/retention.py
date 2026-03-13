from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from db.repository import (
    delete_audit_logs_before,
    delete_customer_content_before,
    get_tenant_config,
    list_artifacts,
    list_tenants,
    update_artifact_lifecycle,
)
from harness.resilience.recovery_journal import journal_root
from observability.langsmith_tracer import trace_root


DEFAULT_RETENTION_POLICY = {
    "artifacts": {"archive_after_days": 30, "delete_after_days": 90},
    "customer_content_days": 30,
    "audit_log_days": 90,
    "local_trace_days": 30,
    "recovery_days": 30,
}


def _parse_iso(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _prune_jsonl(path: Path, cutoff: datetime, *, dry_run: bool) -> dict[str, int]:
    if not path.exists():
        return {"kept": 0, "deleted": 0}
    kept_lines: list[str] = []
    deleted = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        created_at = _parse_iso(record.get("created_at") or record.get("timestamp"))
        if created_at >= cutoff:
            kept_lines.append(line)
        else:
            deleted += 1
    if not dry_run:
        path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""))
    return {"kept": len(kept_lines), "deleted": deleted}


def _tenant_policy(tenant_id: str) -> dict[str, Any]:
    config = get_tenant_config(tenant_id)
    policy = config.get("retention_policy", {})
    merged = json.loads(json.dumps(DEFAULT_RETENTION_POLICY))
    for key, value in policy.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def _tenant_partitions(tenant: dict[str, Any]) -> list[str]:
    partitions: list[str] = []
    for candidate in (tenant.get("id"), tenant.get("slug")):
        if isinstance(candidate, str) and candidate and candidate not in partitions:
            partitions.append(candidate)
    return partitions


def _prune_legacy_local_files(now: datetime, *, dry_run: bool) -> dict[str, Any]:
    legacy_trace = trace_root() / "local-traces.jsonl"
    legacy_recovery_paths = [path for path in journal_root().glob("*.jsonl") if path.is_file()] if journal_root().exists() else []
    return {
        "traces": _prune_jsonl(
            legacy_trace,
            now - timedelta(days=DEFAULT_RETENTION_POLICY["local_trace_days"]),
            dry_run=dry_run,
        ),
        "recovery": {
            path.name: _prune_jsonl(
                path,
                now - timedelta(days=DEFAULT_RETENTION_POLICY["recovery_days"]),
                dry_run=dry_run,
            )
            for path in legacy_recovery_paths
        },
    }


def run_retention_pass(*, tenant_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    tenants = [tenant for tenant in list_tenants() if tenant_id is None or tenant["id"] == tenant_id or tenant["slug"] == tenant_id]
    report = {"tenants": [], "local": {"legacy": _prune_legacy_local_files(now, dry_run=dry_run)}}

    for tenant in tenants:
        policy = _tenant_policy(tenant["id"])
        archive_cutoff = now - timedelta(days=policy["artifacts"]["archive_after_days"])
        delete_cutoff = now - timedelta(days=policy["artifacts"]["delete_after_days"])
        archived = 0
        deleted_artifacts = 0
        for artifact in list_artifacts(tenant["id"]):
            created_at = _parse_iso(artifact["created_at"])
            if artifact["lifecycle_state"] in {"created", "active"} and created_at < archive_cutoff:
                archived += 1
                if not dry_run:
                    if artifact["lifecycle_state"] == "created":
                        artifact["lifecycle_state"] = "active"
                    update_artifact_lifecycle(artifact["id"], "archived", tenant_id=tenant["id"])
            elif artifact["lifecycle_state"] == "archived" and created_at < delete_cutoff:
                deleted_artifacts += 1
                if not dry_run:
                    update_artifact_lifecycle(artifact["id"], "deleted", tenant_id=tenant["id"])

        customer_deleted = delete_customer_content_before(
            tenant["id"],
            (now - timedelta(days=policy["customer_content_days"])).isoformat(),
            dry_run=dry_run,
        )
        audit_deleted = delete_audit_logs_before(
            (now - timedelta(days=policy["audit_log_days"])).isoformat(),
            tenant_id=tenant["id"],
            dry_run=dry_run,
        )
        local_trace_report = {"kept": 0, "deleted": 0}
        local_recovery_report: dict[str, dict[str, int]] = {}
        for partition in _tenant_partitions(tenant):
            trace_report = _prune_jsonl(
                trace_root() / partition / "local-traces.jsonl",
                now - timedelta(days=policy["local_trace_days"]),
                dry_run=dry_run,
            )
            local_trace_report["kept"] += trace_report["kept"]
            local_trace_report["deleted"] += trace_report["deleted"]
            recovery_partition = journal_root() / partition
            if recovery_partition.exists():
                for path in sorted(recovery_partition.glob("*.jsonl")):
                    current = _prune_jsonl(
                        path,
                        now - timedelta(days=policy["recovery_days"]),
                        dry_run=dry_run,
                    )
                    bucket = local_recovery_report.setdefault(path.name, {"kept": 0, "deleted": 0})
                    bucket["kept"] += current["kept"]
                    bucket["deleted"] += current["deleted"]
        report["tenants"].append(
            {
                "tenant_id": tenant["id"],
                "archived_artifacts": archived,
                "deleted_artifacts": deleted_artifacts,
                "deleted_customer_content": customer_deleted,
                "deleted_audit_logs": audit_deleted,
                "local_traces": local_trace_report,
                "local_recovery": local_recovery_report,
            }
        )
    return report

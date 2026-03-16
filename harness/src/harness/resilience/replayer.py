from __future__ import annotations

from copy import deepcopy

from db.repository import create_artifact, persist_run_record
from harness.resilience.recovery_journal import get_recovery_entry


def replay_recovery_entry(entry_id: str) -> dict:
    entry = get_recovery_entry(entry_id)
    if entry["entry_type"] != "persist-failure":
        raise ValueError(f"Unsupported recovery replay type: {entry['entry_type']}")

    record = deepcopy(entry["payload"]["record"])
    persisted = persist_run_record(record)
    artifact = create_artifact(
        {
            "tenant_id": record["tenant_id"],
            "run_id": record["run_id"],
            "created_by": record["worker_id"],
            "artifact_type": "run_record",
            "source_job_id": persisted.get("job", {}).get("id"),
            "payload": deepcopy(persisted),
            "lineage": {"replayed_from": entry_id, "worker_id": record["worker_id"]},
        }
    )
    return {"replayed": True, "entry_id": entry_id, "persisted": persisted, "artifact": artifact}

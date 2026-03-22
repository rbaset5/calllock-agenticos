from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

try:
    from db import local_repository, supabase_repository
except ModuleNotFoundError:  # pragma: no cover - supports `from src.outbound...` smoke path
    from src.db import local_repository, supabase_repository

from .constants import OUTBOUND_TENANT_ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _using_supabase() -> bool:
    return supabase_repository.is_configured()


def _local_state() -> dict[str, Any]:
    state = local_repository._state()  # type: ignore[attr-defined]
    state.setdefault("outbound_prospects", [])
    state.setdefault("prospect_signals", [])
    state.setdefault("prospect_scores", [])
    state.setdefault("call_tests", [])
    state.setdefault("outbound_calls", [])
    return state


def _matches_tenant(row_tenant_id: str, tenant_id: str) -> bool:
    return local_repository._tenant_matches(row_tenant_id, tenant_id)  # type: ignore[attr-defined]


def upsert_outbound_prospects(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"inserted": 0, "skipped_dedup": 0, "records": []}

    if _using_supabase():
        inserted = supabase_repository._request(  # type: ignore[attr-defined]
            "POST",
            "outbound_prospects",
            params={"on_conflict": "tenant_id,phone_normalized"},
            json=records,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        inserted_records = inserted or []
        return {
            "inserted": len(inserted_records),
            "skipped_dedup": len(records) - len(inserted_records),
            "records": inserted_records,
        }

    state = _local_state()
    inserted_records: list[dict[str, Any]] = []
    for record in records:
        duplicate = next(
            (
                row
                for row in state["outbound_prospects"]
                if row["tenant_id"] == record["tenant_id"] and row["phone_normalized"] == record["phone_normalized"]
            ),
            None,
        )
        if duplicate is not None:
            continue
        now = _now_iso()
        stored = {
            "id": record.get("id", str(uuid4())),
            "tenant_id": record.get("tenant_id", OUTBOUND_TENANT_ID),
            "business_name": record["business_name"],
            "trade": record["trade"],
            "metro": record.get("metro"),
            "website": record.get("website"),
            "address": record.get("address"),
            "phone": record.get("phone"),
            "phone_normalized": record["phone_normalized"],
            "source": record["source"],
            "source_listing_id": record.get("source_listing_id"),
            "timezone": record.get("timezone"),
            "raw_source": deepcopy(record.get("raw_source", {})),
            "total_score": int(record.get("total_score", 0)),
            "score_tier": record.get("score_tier", "unscored"),
            "discovered_at": record.get("discovered_at", now),
            "stage": record.get("stage", "discovered"),
            "disqualification_reason": record.get("disqualification_reason"),
            "created_at": record.get("created_at", now),
        }
        state["outbound_prospects"].append(stored)
        inserted_records.append(stored)
    return {
        "inserted": len(inserted_records),
        "skipped_dedup": len(records) - len(inserted_records),
        "records": inserted_records,
    }


def list_outbound_prospects(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    stages: list[str] | None = None,
    prospect_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "discovered_at.asc"}
        if stages:
            params["stage"] = f"in.({','.join(stages)})"
        if prospect_ids:
            params["id"] = f"in.({','.join(prospect_ids)})"
        return supabase_repository._request("GET", "outbound_prospects", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["outbound_prospects"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if stages:
        allowed = set(stages)
        rows = [row for row in rows if row.get("stage") in allowed]
    if prospect_ids:
        allowed_ids = set(prospect_ids)
        rows = [row for row in rows if row.get("id") in allowed_ids]
    return sorted(rows, key=lambda row: row.get("discovered_at", ""))


def get_outbound_prospect(prospect_id: str, *, tenant_id: str = OUTBOUND_TENANT_ID) -> dict[str, Any] | None:
    rows = list_outbound_prospects(tenant_id=tenant_id, prospect_ids=[prospect_id])
    return rows[0] if rows else None


def update_outbound_prospect(prospect_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "PATCH",
            "outbound_prospects",
            params={"id": f"eq.{prospect_id}"},
            json=updates,
            prefer="return=representation",
        )
        return data[0]

    for row in _local_state()["outbound_prospects"]:
        if row["id"] == prospect_id:
            row.update(deepcopy(updates))
            return row
    raise KeyError(f"Unknown outbound prospect: {prospect_id}")


def insert_prospect_signal(payload: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request("POST", "prospect_signals", json=payload, prefer="return=representation")  # type: ignore[attr-defined]
        return data[0] if data else payload

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "prospect_id": payload["prospect_id"],
        "signal_type": payload["signal_type"],
        "signal_tier": int(payload["signal_tier"]),
        "raw_evidence": deepcopy(payload.get("raw_evidence", {})),
        "score": int(payload.get("score", 0)),
        "observed_at": payload.get("observed_at", now),
    }
    _local_state()["prospect_signals"].append(record)
    return record


def list_prospect_signals(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    prospect_id: str | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "observed_at.asc"}
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        return supabase_repository._request("GET", "prospect_signals", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["prospect_signals"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row["prospect_id"] == prospect_id]
    return sorted(rows, key=lambda row: row.get("observed_at", ""))


def insert_prospect_score(payload: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request("POST", "prospect_scores", json=payload, prefer="return=representation")  # type: ignore[attr-defined]
        return data[0] if data else payload

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "prospect_id": payload["prospect_id"],
        "dimension_scores": deepcopy(payload["dimension_scores"]),
        "total_score": int(payload["total_score"]),
        "tier": payload["tier"],
        "rubric_hash": payload["rubric_hash"],
        "scored_at": payload.get("scored_at", now),
    }
    _local_state()["prospect_scores"].append(record)
    return record


def list_prospect_scores(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    prospect_id: str | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "scored_at.asc"}
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        return supabase_repository._request("GET", "prospect_scores", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["prospect_scores"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row["prospect_id"] == prospect_id]
    return sorted(rows, key=lambda row: row.get("scored_at", ""))


def list_probe_candidates(*, tenant_id: str = OUTBOUND_TENANT_ID) -> list[dict[str, Any]]:
    prospects = list_outbound_prospects(tenant_id=tenant_id, stages=["scored"])
    return [row for row in prospects if row.get("score_tier") in {"a_lead", "b_lead"}]


def insert_call_test(payload: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request("POST", "call_tests", json=payload, prefer="return=representation")  # type: ignore[attr-defined]
        return data[0] if data else payload

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "prospect_id": payload["prospect_id"],
        "twilio_call_sid": payload["twilio_call_sid"],
        "called_at": payload.get("called_at", now),
        "day_of_week": payload["day_of_week"],
        "local_time": payload["local_time"],
        "result": payload["result"],
        "amd_status": payload.get("amd_status"),
        "ring_duration_ms": payload.get("ring_duration_ms"),
    }
    _local_state()["call_tests"].append(record)
    return record


def list_call_tests(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    prospect_id: str | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "called_at.asc"}
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        return supabase_repository._request("GET", "call_tests", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["call_tests"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row["prospect_id"] == prospect_id]
    return sorted(rows, key=lambda row: row.get("called_at", ""))


def insert_outbound_call(payload: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "POST",
            "outbound_calls",
            params={"on_conflict": "tenant_id,twilio_call_sid"},
            json=payload,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        record = data[0] if data else None
        return {"inserted": record is not None, "record": record}

    state = _local_state()
    duplicate = next(
        (
            row
            for row in state["outbound_calls"]
            if row["tenant_id"] == payload["tenant_id"] and row["twilio_call_sid"] == payload["twilio_call_sid"]
        ),
        None,
    )
    if duplicate is not None:
        return {"inserted": False, "record": None}

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "prospect_id": payload["prospect_id"],
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "twilio_call_sid": payload["twilio_call_sid"],
        "called_at": payload.get("called_at", now),
        "outcome": payload["outcome"],
        "notes": payload.get("notes"),
        "call_hook_used": payload.get("call_hook_used"),
        "demo_scheduled": bool(payload.get("demo_scheduled", False)),
        "callback_date": payload.get("callback_date"),
        "growth_memory_id": payload.get("growth_memory_id"),
        "recording_url": payload.get("recording_url"),
        "transcript": payload.get("transcript"),
    }
    state["outbound_calls"].append(record)
    return {"inserted": True, "record": record}


def update_outbound_call_by_sid(twilio_call_sid: str, updates: dict[str, Any]) -> dict[str, Any]:
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "PATCH",
            "outbound_calls",
            params={"tenant_id": f"eq.{OUTBOUND_TENANT_ID}", "twilio_call_sid": f"eq.{twilio_call_sid}"},
            json=updates,
            prefer="return=representation",
        )
        return data[0]

    for row in _local_state()["outbound_calls"]:
        if row["tenant_id"] == OUTBOUND_TENANT_ID and row["twilio_call_sid"] == twilio_call_sid:
            row.update(deepcopy(updates))
            return row
    raise KeyError(f"Unknown outbound call sid: {twilio_call_sid}")


def list_outbound_calls(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    prospect_id: str | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "called_at.asc"}
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        return supabase_repository._request("GET", "outbound_calls", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["outbound_calls"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row["prospect_id"] == prospect_id]
    return sorted(rows, key=lambda row: row.get("called_at", ""))


def list_ranked_call_ready_prospects(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    prospects = [row for row in list_outbound_prospects(tenant_id=tenant_id, stages=["call_ready"])]
    prospects.sort(key=lambda row: (-int(row.get("total_score", 0)), row.get("business_name", "")))
    return prospects[:limit]

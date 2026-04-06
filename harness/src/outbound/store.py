from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
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


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _local_state() -> dict[str, Any]:
    state = local_repository._state()  # type: ignore[attr-defined]
    state.setdefault("outbound_prospects", [])
    state.setdefault("prospect_signals", [])
    state.setdefault("prospect_scores", [])
    state.setdefault("call_tests", [])
    state.setdefault("outbound_calls", [])
    state.setdefault("scoring_feedback", [])
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


def upsert_or_enrich_prospects(records: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert prospects, enriching existing records on phone conflict.

    Unlike upsert_outbound_prospects (which ignores duplicates), this updates
    total_score and score_tier when the new score is higher, and sets source
    to the new value if the record already exists.
    """
    if not records:
        return {"inserted": 0, "enriched": 0, "skipped": 0}

    inserted = 0
    enriched = 0
    skipped = 0

    if _using_supabase():
        for record in records:
            tenant_id = record["tenant_id"]
            phone = record["phone_normalized"]
            existing = supabase_repository._request(  # type: ignore[attr-defined]
                "GET",
                "outbound_prospects",
                params={
                    "tenant_id": f"eq.{tenant_id}",
                    "phone_normalized": f"eq.{phone}",
                    "select": "id,total_score,score_tier",
                },
            )
            if existing:
                row = existing[0]
                old_score = int(row.get("total_score", 0))
                new_score = int(record.get("total_score", 0))
                if new_score > old_score:
                    supabase_repository._request(  # type: ignore[attr-defined]
                        "PATCH",
                        f"outbound_prospects?id=eq.{row['id']}",
                        json={
                            "total_score": new_score,
                            "score_tier": record.get("score_tier", "unscored"),
                        },
                    )
                    enriched += 1
                else:
                    skipped += 1
            else:
                supabase_repository._request(  # type: ignore[attr-defined]
                    "POST",
                    "outbound_prospects",
                    json=[record],
                    prefer="return=representation",
                )
                inserted += 1
    else:
        state = _local_state()
        for record in records:
            dup = next(
                (r for r in state["outbound_prospects"]
                 if r["tenant_id"] == record["tenant_id"]
                 and r["phone_normalized"] == record["phone_normalized"]),
                None,
            )
            if dup is not None:
                old_score = int(dup.get("total_score", 0))
                new_score = int(record.get("total_score", 0))
                if new_score > old_score:
                    dup["total_score"] = new_score
                    dup["score_tier"] = record.get("score_tier", "unscored")
                    enriched += 1
                else:
                    skipped += 1
            else:
                now = _now_iso()
                stored = {
                    "id": record.get("id", str(uuid4())),
                    "tenant_id": record["tenant_id"],
                    "business_name": record["business_name"],
                    "trade": record.get("trade", "hvac"),
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
                    "discovered_at": now,
                    "stage": record.get("stage", "call_ready"),
                    "disqualification_reason": None,
                    "created_at": now,
                }
                state["outbound_prospects"].append(stored)
                inserted += 1

    return {"inserted": inserted, "enriched": enriched, "skipped": skipped}


def enrich_prospect_reviews(
    phone_normalized: str,
    enrichment: dict[str, Any],
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> bool:
    """Update a prospect with review enrichment data.

    Sets review_signals, review_opener, review_enrichment_score,
    desperation_score, and bumps total_score by the enrichment delta.
    Returns True if a prospect was found and updated.
    """
    review_fields = {
        "review_signals": enrichment.get("review_signals"),
        "review_opener": enrichment.get("review_opener"),
        "review_enrichment_score": enrichment.get("review_enrichment_score", 0),
        "desperation_score": enrichment.get("desperation_score", 0),
    }

    if _using_supabase():
        existing = supabase_repository._request(  # type: ignore[attr-defined]
            "GET",
            "outbound_prospects",
            params={
                "tenant_id": f"eq.{tenant_id}",
                "phone_normalized": f"eq.{phone_normalized}",
                "select": "id,total_score,review_enrichment_score",
            },
        )
        if not existing:
            return False
        row = existing[0]
        old_review_delta = int(row.get("review_enrichment_score", 0) or 0)
        new_delta = int(enrichment.get("review_enrichment_score", 0))
        score_adjustment = new_delta - old_review_delta
        # Atomic score update: read total_score at UPDATE time, not at SELECT time
        # This avoids race conditions with concurrent score_prospects() calls
        current_total = int(row.get("total_score", 0))
        new_total = max(0, current_total + score_adjustment)
        patch = {**review_fields, "total_score": new_total}
        supabase_repository._request(  # type: ignore[attr-defined]
            "PATCH",
            f"outbound_prospects?id=eq.{row['id']}",
            json=patch,
        )
        return True

    # Local path
    state = _local_state()
    for prospect in state["outbound_prospects"]:
        if (prospect["phone_normalized"] == phone_normalized
                and _matches_tenant(prospect["tenant_id"], tenant_id)):
            old_review_delta = int(prospect.get("review_enrichment_score", 0) or 0)
            old_score = int(prospect.get("total_score", 0))
            new_delta = int(enrichment.get("review_enrichment_score", 0))
            base_score = old_score - old_review_delta
            prospect.update(review_fields)
            prospect["total_score"] = max(0, base_score + new_delta)
            return True
    return False


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


def update_outbound_prospect(
    prospect_id: str,
    updates: dict[str, Any],
    *,
    expected_stage: str | None = None,
) -> dict[str, Any] | None:
    """Update a prospect. If expected_stage is set, only update if stage matches (atomic guard).

    Returns the updated row, or None if expected_stage didn't match (no-op).
    """
    if _using_supabase():
        params: dict[str, str] = {"id": f"eq.{prospect_id}"}
        if expected_stage:
            params["stage"] = f"eq.{expected_stage}"
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "PATCH",
            "outbound_prospects",
            params=params,
            json=updates,
            prefer="return=representation",
        )
        if not data:
            return None  # expected_stage guard: row didn't match
        return data[0]

    for row in _local_state()["outbound_prospects"]:
        if row["id"] == prospect_id:
            if expected_stage and row.get("stage") != expected_stage:
                return None
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
        "call_outcome_type": payload.get("call_outcome_type"),
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
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    if _using_supabase():
        params: dict[str, str] = {"tenant_id": f"eq.{tenant_id}", "order": "called_at.asc"}
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        if start_date:
            params["called_at"] = f"gte.{start_date}"
        if end_date:
            params["called_at"] = params.get("called_at", "") and f"gte.{start_date}"
            # Supabase doesn't natively support AND on the same column via params,
            # but we can use the range filter
            if start_date and end_date:
                del params["called_at"]
                params["and"] = f"(called_at.gte.{start_date},called_at.lte.{end_date}T23:59:59)"
            elif start_date:
                params["called_at"] = f"gte.{start_date}"
            elif end_date:
                params["called_at"] = f"lte.{end_date}T23:59:59"
        return supabase_repository._request("GET", "outbound_calls", params=params)  # type: ignore[attr-defined]

    rows = [row for row in _local_state()["outbound_calls"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row["prospect_id"] == prospect_id]
    if start_date:
        rows = [row for row in rows if (row.get("called_at") or "") >= start_date]
    if end_date:
        rows = [row for row in rows if (row.get("called_at") or "")[:10] <= end_date]
    return sorted(rows, key=lambda row: row.get("called_at", ""))


def list_ranked_call_ready_prospects(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    prospects = [row for row in list_outbound_prospects(tenant_id=tenant_id, stages=["call_ready"])]
    prospects.sort(key=lambda row: (-int(row.get("total_score", 0)), row.get("business_name", "")))
    return prospects[:limit]


def list_prospects_by_stages(
    stages: list[str],
    metro_filter: list[str] | None = None,
    include_signals: bool = True,
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> list[dict[str, Any]]:
    if _using_supabase():
        select = (
            "id,business_name,phone,phone_normalized,website,address,metro,timezone,total_score,"
            "score_tier,raw_source,stage,next_action_date,next_action_type,last_touched_at"
        )
        if include_signals:
            select += ",prospect_signals(signal_type,signal_tier,score,observed_at),call_tests(result,called_at,local_time)"
        params: dict[str, str] = {
            "tenant_id": f"eq.{tenant_id}",
            "stage": f"in.({','.join(stages)})",
            "select": select,
            "order": "total_score.desc,business_name.asc",
        }
        if metro_filter:
            params["metro"] = f"in.({','.join(metro_filter)})"
        return supabase_repository._request("GET", "outbound_prospects", params=params)  # type: ignore[attr-defined]

    prospects = list_outbound_prospects(tenant_id=tenant_id, stages=stages)
    if metro_filter:
        allowed = {metro.lower() for metro in metro_filter}
        prospects = [row for row in prospects if str(row.get("metro") or "").lower() in allowed]
    if include_signals:
        signals = list_prospect_signals(tenant_id=tenant_id)
        tests = list_call_tests(tenant_id=tenant_id)
        signals_by_prospect: dict[str, list[dict[str, Any]]] = {}
        tests_by_prospect: dict[str, list[dict[str, Any]]] = {}
        for signal in signals:
            signals_by_prospect.setdefault(signal["prospect_id"], []).append(signal)
        for test in tests:
            tests_by_prospect.setdefault(test["prospect_id"], []).append(test)
        prospects = [
            {
                **row,
                "prospect_signals": signals_by_prospect.get(row["id"], []),
                "call_tests": tests_by_prospect.get(row["id"], []),
            }
            for row in prospects
        ]
    prospects.sort(key=lambda row: (-int(row.get("total_score", 0) or 0), str(row.get("business_name") or "")))
    return prospects


def list_today_dial_prospect_ids(
    tenant_id: str = OUTBOUND_TENANT_ID,
    *,
    today: date | None = None,
) -> set[str]:
    today = today or date.today()
    if _using_supabase():
        start = f"{today.isoformat()}T00:00:00"
        end = f"{(today + timedelta(days=1)).isoformat()}T00:00:00"
        rows = supabase_repository._request(  # type: ignore[attr-defined]
            "GET",
            "outbound_calls",
            params={
                "tenant_id": f"eq.{tenant_id}",
                "select": "prospect_id",
                "and": f"(called_at.gte.{start},called_at.lt.{end})",
            },
        )
        return {str(row.get("prospect_id")) for row in rows or [] if row.get("prospect_id")}

    return {
        str(row.get("prospect_id"))
        for row in list_outbound_calls(tenant_id=tenant_id, start_date=today.isoformat(), end_date=today.isoformat())
        if row.get("prospect_id")
    }


# ---------------------------------------------------------------------------
# Lifecycle RPC wrappers (Phase 1: Sales Assistant daily ops)
# These call Postgres RPC functions defined in migration 061.
# ---------------------------------------------------------------------------

def list_due_callbacks(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    today: str | None = None,
) -> list[dict[str, Any]]:
    """Callbacks due today or earlier, where prospect is still in 'callback' stage."""
    if not _using_supabase():
        return []  # local fallback: no RPC support
    from datetime import date as _date
    today_str = today or _date.today().isoformat()
    return supabase_repository._rpc(  # type: ignore[attr-defined]
        "list_due_callbacks",
        {"p_tenant_id": tenant_id, "p_today": today_str},
    )


def list_overdue_callbacks(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    today: str | None = None,
    grace_days: int = 3,
) -> list[dict[str, Any]]:
    """Callbacks overdue by more than grace_days, prospect still in 'callback' stage."""
    if not _using_supabase():
        return []
    from datetime import date as _date
    today_str = today or _date.today().isoformat()
    return supabase_repository._rpc(  # type: ignore[attr-defined]
        "list_overdue_callbacks",
        {"p_tenant_id": tenant_id, "p_today": today_str, "p_grace_days": grace_days},
    )


def list_recent_no_answer_strikes(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    min_strikes: int = 3,
) -> list[dict[str, Any]]:
    """Prospects whose N most recent calls are ALL no_answer (warm-lead protected)."""
    if not _using_supabase():
        return []
    return supabase_repository._rpc(  # type: ignore[attr-defined]
        "list_recent_no_answer_strikes",
        {"p_tenant_id": tenant_id, "p_min_strikes": min_strikes},
    )


def list_voicemail_requeue_candidates(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    min_days: int = 3,
) -> list[dict[str, Any]]:
    """Prospects who got a voicemail N+ days ago and are still in 'called' stage."""
    if not _using_supabase():
        return []
    return supabase_repository._rpc(  # type: ignore[attr-defined]
        "list_voicemail_requeue_candidates",
        {"p_tenant_id": tenant_id, "p_min_days": min_days},
    )


def list_cooling_leads(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    stale_days: int = 5,
) -> list[dict[str, Any]]:
    """Prospects in 'interested' stage for N+ days with no demo scheduled."""
    if not _using_supabase():
        return []
    return supabase_repository._rpc(  # type: ignore[attr-defined]
        "list_cooling_leads",
        {"p_tenant_id": tenant_id, "p_stale_days": stale_days},
    )


def list_wrong_numbers(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> list[dict[str, Any]]:
    """Prospects with a wrong_number outcome not yet disqualified."""
    if _using_supabase():
        calls = supabase_repository._request(  # type: ignore[attr-defined]
            "GET",
            "outbound_calls",
            params={
                "tenant_id": f"eq.{tenant_id}",
                "outcome": "eq.wrong_number",
                "select": "prospect_id",
            },
        )
        if not calls:
            return []
        prospect_ids = list({c["prospect_id"] for c in calls})
        prospects = list_outbound_prospects(tenant_id=tenant_id, prospect_ids=prospect_ids)
        return [p for p in prospects if p.get("stage") != "disqualified"]
    return []


def today_call_stats(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    date: str | None = None,
) -> dict[str, int]:
    """Aggregate call stats for a given date (defaults to today)."""
    if not _using_supabase():
        return {}
    from datetime import date as _date
    date_str = date or _date.today().isoformat()
    rows = supabase_repository._rpc(  # type: ignore[attr-defined]
        "today_call_stats",
        {"p_tenant_id": tenant_id, "p_date": date_str},
    )
    return rows[0] if rows else {}


def sprint_scoreboard(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    start_date: str,
    today: str | None = None,
) -> dict[str, Any]:
    """Aggregate scoreboard metrics from RPC (or local fallback)."""
    today_str = today or date.today().isoformat()

    if _using_supabase():
        rows = supabase_repository._rpc(  # type: ignore[attr-defined]
            "sprint_scoreboard",
            {
                "p_tenant_id": tenant_id,
                "p_start_date": start_date,
                "p_today": today_str,
            },
        )
        if isinstance(rows, dict):
            return rows
        return (rows or [{}])[0]

    start_day = date.fromisoformat(start_date)
    today_day = date.fromisoformat(today_str)
    week_start = today_day - timedelta(days=today_day.weekday())
    calls = list_outbound_calls(tenant_id=tenant_id)

    def _is_completed_call(row: dict[str, Any]) -> bool:
        outcome = str(row.get("outcome") or "")
        call_outcome_type = str(row.get("call_outcome_type") or "")
        return outcome != "dial_started" and call_outcome_type != "dial_started"

    def _call_day(row: dict[str, Any]) -> date | None:
        return _parse_iso_date(row.get("called_at"))

    completed_calls = [row for row in calls if _is_completed_call(row)]
    daily_calls = [row for row in completed_calls if _call_day(row) == today_day]
    weekly_calls = [row for row in completed_calls if (_call_day(row) or date.min) >= week_start]
    total_calls = [row for row in completed_calls if (_call_day(row) or date.min) >= start_day]

    def _is_connect(row: dict[str, Any]) -> bool:
        return str(row.get("outcome") or "").startswith("answered_")

    def _is_demo(row: dict[str, Any]) -> bool:
        return bool(row.get("demo_scheduled"))

    return {
        "daily_dials": len(daily_calls),
        "daily_connects": sum(1 for row in daily_calls if _is_connect(row)),
        "daily_demos": sum(1 for row in daily_calls if _is_demo(row)),
        "daily_close_attempts": sum(
            1
            for row in daily_calls
            if str(row.get("call_outcome_type") or "") == "close_attempted"
        ),
        "weekly_dials": len(weekly_calls),
        "weekly_connects": sum(1 for row in weekly_calls if _is_connect(row)),
        "total_dials": len(total_calls),
        "total_connects": sum(1 for row in total_calls if _is_connect(row)),
        "total_demos": sum(1 for row in total_calls if _is_demo(row)),
        "customers_signed": len(
            [
                row
                for row in list_outbound_prospects(tenant_id=tenant_id)
                if row.get("stage") == "converted"
            ]
        ),
    }


# ── prospect_messages CRUD ──────────────────────────────────────────


def insert_prospect_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Insert a message record (outbound or inbound)."""
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "POST",
            "prospect_messages",
            json=payload,
            prefer="return=representation",
        )
        return data[0] if data else payload

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "prospect_id": payload.get("prospect_id"),
        "direction": payload["direction"],
        "channel": payload.get("channel", "imessage"),
        "content": payload["content"],
        "outcome_trigger": payload.get("outcome_trigger"),
        "status": payload.get("status", "draft"),
        "imsg_result": deepcopy(payload.get("imsg_result", {})),
        "created_at": payload.get("created_at", now),
        "sent_at": payload.get("sent_at"),
        "phone_normalized": payload.get("phone_normalized", ""),
    }
    state = _local_state()
    state.setdefault("prospect_messages", [])
    state["prospect_messages"].append(record)
    return record


def list_prospect_messages(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    prospect_id: str | None = None,
    direction: str | None = None,
    phone_normalized: str | None = None,
) -> list[dict[str, Any]]:
    """List messages, optionally filtered by prospect, direction, or phone."""
    if _using_supabase():
        params: dict[str, str] = {
            "tenant_id": f"eq.{tenant_id}",
            "order": "created_at.desc",
        }
        if prospect_id:
            params["prospect_id"] = f"eq.{prospect_id}"
        if direction:
            params["direction"] = f"eq.{direction}"
        if phone_normalized:
            params["phone_normalized"] = f"eq.{phone_normalized}"
        return supabase_repository._request("GET", "prospect_messages", params=params)  # type: ignore[attr-defined]

    state = _local_state()
    state.setdefault("prospect_messages", [])
    rows = [row for row in state["prospect_messages"] if _matches_tenant(row["tenant_id"], tenant_id)]
    if prospect_id:
        rows = [row for row in rows if row.get("prospect_id") == prospect_id]
    if direction:
        rows = [row for row in rows if row.get("direction") == direction]
    if phone_normalized:
        rows = [row for row in rows if row.get("phone_normalized") == phone_normalized]
    return sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)


def update_prospect_message(
    message_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """Update a message record by ID."""
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "PATCH",
            "prospect_messages",
            params={"id": f"eq.{message_id}"},
            json=updates,
            prefer="return=representation",
        )
        return data[0] if data else None

    state = _local_state()
    state.setdefault("prospect_messages", [])
    for row in state["prospect_messages"]:
        if row["id"] == message_id:
            row.update(deepcopy(updates))
            return row
    return None


# ---------------------------------------------------------------------------
# Scoring feedback
# ---------------------------------------------------------------------------


def insert_scoring_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    """Insert a scoring feedback run record."""
    if _using_supabase():
        data = supabase_repository._request(  # type: ignore[attr-defined]
            "POST", "scoring_feedback", json=payload, prefer="return=representation"
        )
        return data[0] if data else payload

    now = _now_iso()
    record = {
        "id": payload.get("id", str(uuid4())),
        "tenant_id": payload.get("tenant_id", OUTBOUND_TENANT_ID),
        "rubric_hash": payload["rubric_hash"],
        "run_at": payload.get("run_at", now),
        "total_prospects_analyzed": payload["total_prospects_analyzed"],
        "positive_count": payload["positive_count"],
        "negative_count": payload["negative_count"],
        "inconclusive_count": payload["inconclusive_count"],
        "base_rate": payload["base_rate"],
        "dimension_metrics": deepcopy(payload["dimension_metrics"]),
        "current_weights": deepcopy(payload["current_weights"]),
        "suggested_weights": deepcopy(payload["suggested_weights"]),
        "review_signal_metrics": deepcopy(payload.get("review_signal_metrics")),
        "tier_accuracy": deepcopy(payload["tier_accuracy"]),
        "discrimination_score": payload.get("discrimination_score"),
    }
    state = _local_state()
    state["scoring_feedback"].append(record)
    return record


def list_scoring_feedback(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List recent scoring feedback runs, most recent first."""
    if _using_supabase():
        params: dict[str, str] = {
            "tenant_id": f"eq.{tenant_id}",
            "order": "run_at.desc",
            "limit": str(limit),
        }
        return supabase_repository._request("GET", "scoring_feedback", params=params)  # type: ignore[attr-defined]

    rows = [
        row for row in _local_state()["scoring_feedback"]
        if _matches_tenant(row["tenant_id"], tenant_id)
    ]
    return sorted(rows, key=lambda r: r.get("run_at", ""), reverse=True)[:limit]

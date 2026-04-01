from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import sprint_state, store
from .constants import OUTBOUND_TENANT_ID
from .daily_plan import METRO_FILTERS
from .lifecycle import classify_lead_type


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _prospect_id(prospect: dict[str, Any]) -> str:
    return str(prospect.get("id") or prospect.get("prospect_id") or "")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _normalize_callback(prospect: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(prospect)
    normalized["id"] = _prospect_id(prospect)
    normalized.setdefault("stage", "callback")
    return normalized


def compute_needs_attention(prospect: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _now_utc()
    stage = str(prospect.get("stage") or "")
    next_action_date = _parse_iso(prospect.get("next_action_date"))
    last_touched_at = _parse_iso(prospect.get("last_touched_at"))

    if stage in {"interested", "callback"} and next_action_date is None:
        return True
    if stage in {"interested", "callback"} and last_touched_at is not None and (now - last_touched_at).total_seconds() > 48 * 3600:
        return True
    if next_action_date is not None and next_action_date < now:
        return True
    return False


def _with_attention(prospects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**prospect, "needs_attention": compute_needs_attention(prospect)} for prospect in prospects]


def _summary(breakdown: dict[str, int]) -> str:
    return (
        f"{breakdown['callbacks_due']} callbacks, "
        f"{breakdown['interested']} interested, "
        f"{breakdown['callback_stage']} follow-up, "
        f"{breakdown['fresh']} fresh"
    )


def _fresh_matches_segment(prospect: dict[str, Any], segment: str | None) -> bool:
    if not segment:
        return True
    allowed = {metro.lower() for metro in METRO_FILTERS.get(segment, [segment])}
    return str(prospect.get("metro") or "").lower() in allowed


def _single_queue(
    *,
    block: str,
    segment: str | None,
    exclude_dialed: bool,
    tenant_id: str,
) -> dict[str, Any]:
    callbacks = [_normalize_callback(row) for row in store.list_due_callbacks(tenant_id=tenant_id)]
    prospects = store.list_prospects_by_stages(
        stages=["interested", "callback", "call_ready"],
        include_signals=True,
        tenant_id=tenant_id,
    )
    dialed_today = store.list_today_dial_prospect_ids(tenant_id=tenant_id) if exclude_dialed else set()

    def eligible(prospect: dict[str, Any]) -> bool:
        return _prospect_id(prospect) not in dialed_today

    callbacks = [prospect for prospect in callbacks if eligible(prospect)]
    interested = [prospect for prospect in prospects if prospect.get("stage") == "interested" and eligible(prospect)]
    callback_stage = [prospect for prospect in prospects if prospect.get("stage") == "callback" and eligible(prospect)]
    fresh = [
        prospect
        for prospect in prospects
        if prospect.get("stage") == "call_ready" and eligible(prospect) and _fresh_matches_segment(prospect, segment)
    ]

    # Batch-load outbound calls for interested/callback prospects to avoid N+1 in classify_lead_type
    needs_calls = [p for p in interested + callback_stage if not p.get("outbound_calls")]
    if needs_calls:
        call_ids = [_prospect_id(p) for p in needs_calls]
        all_calls = store.list_outbound_calls(tenant_id=tenant_id)
        calls_by_prospect: dict[str, list[dict[str, Any]]] = {}
        for call in all_calls:
            pid = str(call.get("prospect_id") or "")
            if pid in set(call_ids):
                calls_by_prospect.setdefault(pid, []).append(call)
        for p in needs_calls:
            p["outbound_calls"] = calls_by_prospect.get(_prospect_id(p), [])

    interested.sort(key=lambda prospect: (classify_lead_type(prospect) != "hot", str(prospect.get("business_name") or "")))
    callback_stage.sort(key=lambda prospect: (classify_lead_type(prospect) != "warm", str(prospect.get("business_name") or "")))
    fresh.sort(key=lambda prospect: (-int(prospect.get("total_score", 0) or 0), str(prospect.get("business_name") or "")))

    ordered = _with_attention(callbacks + interested + callback_stage + fresh)
    breakdown = {
        "callbacks_due": len(callbacks),
        "interested": len(interested),
        "callback_stage": len(callback_stage),
        "fresh": len(fresh),
    }
    return {
        "block": block,
        "segment": segment,
        "total": len(ordered),
        "breakdown": breakdown,
        "prospects": ordered,
        "already_dialed_today": len(dialed_today),
        "summary": _summary(breakdown),
    }


def build_queue(
    block: str,
    segment: str | None = None,
    exclude_dialed: bool = True,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> dict[str, Any]:
    block = block.upper()
    if block == "ALL":
        state = sprint_state.get_current_state()
        return {
            "block": "all",
            "queues": [
                _single_queue(
                    block=entry["block"],
                    segment=(entry.get("segments") or [None])[0],
                    exclude_dialed=exclude_dialed,
                    tenant_id=tenant_id,
                )
                for entry in state.get("all_blocks", [])
            ],
        }

    return _single_queue(
        block=block,
        segment=segment,
        exclude_dialed=exclude_dialed,
        tenant_id=tenant_id,
    )

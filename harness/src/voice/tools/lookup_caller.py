"""lookup_caller tool handler — queries Supabase for caller history.

Returns caller's recent jobs, calls, and bookings. On any DB error,
returns {found: false} for graceful degradation — agent proceeds as new caller.

Limits per table prevent latency blowup (spec finding #20):
- Last 10 jobs
- Last 5 calls
- Last 5 bookings
"""

from __future__ import annotations

import logging
import re
from typing import Any

from voice.services.twilio_sms import mask_phone

logger = logging.getLogger(__name__)

_JOBS_LIMIT = 10
_CALLS_LIMIT = 5
_BOOKINGS_LIMIT = 5

_PLACEHOLDER_NAMES = {
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
    "not provided",
    "not sure",
    "customer",
    "caller",
}
_BUSINESS_NAME_TERMS = {
    "ac",
    "air",
    "cooling",
    "corp",
    "company",
    "electrical",
    "heating",
    "hvac",
    "inc",
    "llc",
    "plumbing",
    "service",
    "services",
}
_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr"}
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z-]*$")


def empty_lookup_response(*, lookup_status: str, message: str | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "found": False,
        "jobs": [],
        "calls": [],
        "bookings": [],
        "known_caller": None,
        "customerName": "",
        "zipCode": "",
        "lookupStatus": lookup_status,
    }
    if message:
        response["message"] = message
    return response


def _title_name(value: str) -> str:
    return value[:1].upper() + value[1:].lower()


def _extract_name_candidate(raw_name: Any, *, source: str, last_seen_at: Any) -> dict[str, Any] | None:
    if not isinstance(raw_name, str):
        return None

    name = " ".join(raw_name.strip().split())
    if not name:
        return None

    lowered = name.lower().rstrip(".")
    if lowered in _PLACEHOLDER_NAMES or " from" in lowered:
        return None

    tokens = [token.strip(".,") for token in name.split()]
    if not tokens:
        return None
    if tokens[0].lower().rstrip(".") in _HONORIFICS:
        return None
    if any(token.lower().rstrip(".,") in _BUSINESS_NAME_TERMS for token in tokens):
        return None

    first = tokens[0]
    if not _NAME_RE.match(first):
        return None

    clean_tokens = [token for token in tokens if _NAME_RE.match(token)]
    if len(clean_tokens) != len(tokens):
        return None
    if len(first) < 2:
        return None

    return {
        "first_name": _title_name(first),
        "full_name": " ".join(_title_name(token) for token in clean_tokens),
        "is_full_name": len(clean_tokens) >= 2,
        "source": source,
        "last_seen_at": last_seen_at if isinstance(last_seen_at, str) else None,
    }


def _row_timestamp(row: dict[str, Any]) -> Any:
    return row.get("created_at") or row.get("updated_at") or row.get("scheduled_at")


def _name_from_call(row: dict[str, Any]) -> Any:
    extracted_fields = row.get("extracted_fields")
    if isinstance(extracted_fields, dict):
        return extracted_fields.get("customer_name") or extracted_fields.get("customerName")
    return row.get("customer_name") or row.get("customerName")


def _collect_name_candidates(
    *,
    jobs: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    bookings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in calls:
        if isinstance(row, dict):
            candidate = _extract_name_candidate(
                _name_from_call(row),
                source="call_records",
                last_seen_at=_row_timestamp(row),
            )
            if candidate:
                candidates.append(candidate)

    for source, rows in (("jobs", jobs), ("bookings", bookings)):
        for row in rows:
            if not isinstance(row, dict):
                continue
            candidate = _extract_name_candidate(
                row.get("customer_name") or row.get("customerName"),
                source=source,
                last_seen_at=_row_timestamp(row),
            )
            if candidate:
                candidates.append(candidate)
    return candidates


def _select_known_caller(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    first_names = {candidate["first_name"] for candidate in candidates}
    if len(first_names) != 1:
        return None

    full_name_candidate = next((candidate for candidate in candidates if candidate["is_full_name"]), None)
    if full_name_candidate is None and len(candidates) < 2:
        return None

    selected = full_name_candidate or candidates[0]
    last_seen_values = [candidate["last_seen_at"] for candidate in candidates if candidate.get("last_seen_at")]
    last_seen_at = max(last_seen_values) if last_seen_values else selected.get("last_seen_at")
    sources = {candidate["source"] for candidate in candidates}

    return {
        "first_name": selected["first_name"],
        "full_name": selected["full_name"],
        "confidence": "high",
        "source": selected["source"] if len(sources) == 1 else "multiple",
        "last_seen_at": last_seen_at,
    }


def _extract_zip_code(
    *,
    jobs: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    bookings: list[dict[str, Any]],
) -> str:
    for row in [*calls, *jobs, *bookings]:
        if not isinstance(row, dict):
            continue
        extracted_fields = row.get("extracted_fields")
        values: list[Any] = [
            row.get("zip_code"),
            row.get("zipCode"),
        ]
        if isinstance(extracted_fields, dict):
            values.extend([extracted_fields.get("zip_code"), extracted_fields.get("zipCode")])
        for value in values:
            if isinstance(value, str) and re.fullmatch(r"\d{5}", value.strip()):
                return value.strip()
    return ""


def lookup_caller(
    *,
    phone_number: str,
    tenant_id: str,
    db: Any,
) -> dict[str, Any]:
    """Look up caller history by phone number, scoped to tenant.

    Args:
        phone_number: Caller's phone (E.164 format).
        tenant_id: Tenant UUID — required for data isolation.
        db: Database client with get_caller_history(tenant_id, phone) method.

    Returns:
        Dict with found, jobs, calls, bookings keys. On DB failure,
        returns {found: false} with empty lists.
    """
    logger.info("lookup_caller.start", extra={"phone": mask_phone(phone_number), "tenant_id": tenant_id})

    try:
        history = db.get_caller_history(tenant_id, phone_number)
        jobs = history.get("jobs", [])[:_JOBS_LIMIT]
        calls = history.get("calls", [])[:_CALLS_LIMIT]
        bookings = history.get("bookings", [])[:_BOOKINGS_LIMIT]
    except Exception:
        logger.warning(
            "lookup_caller.query_error",
            extra={"phone": mask_phone(phone_number), "tenant_id": tenant_id},
            exc_info=True,
        )
        return empty_lookup_response(lookup_status="error")

    found = bool(jobs or calls or bookings)
    known_caller = _select_known_caller(_collect_name_candidates(jobs=jobs, calls=calls, bookings=bookings))

    logger.info(
        "lookup_caller.complete",
        extra={
            "phone": mask_phone(phone_number),
            "found": found,
            "job_count": len(jobs),
            "call_count": len(calls),
            "booking_count": len(bookings),
            "known_caller": bool(known_caller),
        },
    )

    return {
        "found": found,
        "jobs": jobs,
        "calls": calls,
        "bookings": bookings,
        "known_caller": known_caller,
        "customerName": known_caller["first_name"] if known_caller else "",
        "zipCode": _extract_zip_code(jobs=jobs, calls=calls, bookings=bookings),
        "lookupStatus": "found" if found else "not_found",
    }


__all__ = ["empty_lookup_response", "lookup_caller"]

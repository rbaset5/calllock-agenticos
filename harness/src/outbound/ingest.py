from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .constants import OUTBOUND_TENANT_ID
from .metro import extract_zip, zip_to_metro, zip_to_timezone
from . import store


DEFAULT_DB_PATH = "~/conductor/workspaces/CallLock-Leads/missoula/emtoss_downloader/data/leads.db"
NON_DIGIT_RE = re.compile(r"\D+")

# ---------------------------------------------------------------------------
# ICP scoring: computed at ingest from raw leads DB fields
# Max 100 — weighted toward signals that predict dispatch pain
# ---------------------------------------------------------------------------
ICP_WEIGHTS = {
    "paid_demand": 25,       # spending on ads → aware of lead-gen problem
    "owner_operated": 20,    # no franchise, named owner → decision-maker picks up
    "review_pain": 20,       # low rating or few reviews → operational gaps
    "small_operation": 15,   # low review count → likely 1-3 trucks
    "has_website": 10,       # can research before calling
    "hours_mismatch": 10,    # business-hours-only → missing after-hours calls
}


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    stripped = phone.strip()
    if stripped.startswith("+"):
        digits = "+" + NON_DIGIT_RE.sub("", stripped)
        return digits if 8 <= len(digits) <= 16 else None

    digits = NON_DIGIT_RE.sub("", stripped)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if 8 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def _expanded_db_path(db_path: str | None) -> Path:
    return Path(db_path or DEFAULT_DB_PATH).expanduser()


def _coerce_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _trade_value(raw_trade: str) -> str:
    lower = raw_trade.strip().lower()
    return "plumbing" if "plumb" in lower else "hvac"


def compute_icp_score(row: dict[str, Any]) -> tuple[int, str, dict[str, int]]:
    """Score a raw lead row against ICP criteria. Returns (total, tier, breakdown)."""
    signals: dict[str, int] = {}

    # Paid demand: actively spending on ads
    if str(row.get("is_spending_on_ads") or "").lower() == "true":
        signals["paid_demand"] = ICP_WEIGHTS["paid_demand"]

    # Owner-operated: not franchise + has named owner
    owner = str(row.get("owner_name") or "").strip()
    is_franchise = row.get("is_franchise")
    if not is_franchise and owner:
        signals["owner_operated"] = ICP_WEIGHTS["owner_operated"]

    # Review pain: low rating or few reviews → operational gaps
    rating = float(row.get("rating") or 0)
    reviews = int(row.get("reviews") or 0)
    if reviews > 0 and (rating < 4.2 or reviews < 20):
        signals["review_pain"] = ICP_WEIGHTS["review_pain"]

    # Small operation: low review count signals 1-3 truck shop
    if 0 < reviews <= 50:
        signals["small_operation"] = ICP_WEIGHTS["small_operation"]

    # Has website: can research before calling
    if str(row.get("website") or "").strip():
        signals["has_website"] = ICP_WEIGHTS["has_website"]

    # Hours mismatch: only open during business hours
    timing = str(row.get("workday_timing") or "").lower()
    if any(kw in timing for kw in ("weekday", "business", "8-5", "8 am", "9-5", "9 am")):
        signals["hours_mismatch"] = ICP_WEIGHTS["hours_mismatch"]

    total = min(sum(signals.values()), 100)

    from .constants import TIER_THRESHOLDS
    if total >= TIER_THRESHOLDS["a_lead"]:
        tier = "a_lead"
    elif total >= TIER_THRESHOLDS["b_lead"]:
        tier = "b_lead"
    elif total >= TIER_THRESHOLDS["c_lead"]:
        tier = "c_lead"
    else:
        tier = "unscored"

    return total, tier, signals


def run_batch(db_path: str = DEFAULT_DB_PATH, metros: list[str] | None = None, trades: list[str] | None = None, batch_size: int = 5000) -> dict[str, int]:
    selected_trades = [trade.strip().lower() for trade in (trades or []) if trade.strip()]
    configured_metros = metros or []
    if not selected_trades:
        return {"ingested": 0, "skipped_dedup": 0, "skipped_no_phone": 0, "skipped_no_metro": 0}

    connection = sqlite3.connect(_expanded_db_path(db_path))
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in selected_trades)
    # Filter franchises out at the SQL level for speed on 4.5M rows
    query = (
        f"SELECT * FROM leads "
        f"WHERE lower(source_category) IN ({placeholders}) "
        f"AND (is_franchise = 0 OR is_franchise IS NULL) "
        f"AND phone <> ''"
    )

    skipped_no_phone = 0
    skipped_no_metro = 0
    inserted = 0
    skipped_dedup = 0
    batch: list[dict[str, Any]] = []

    try:
        cursor = connection.execute(query, tuple(selected_trades))
        for sqlite_row in cursor:
            row = {key: _coerce_jsonable(sqlite_row[key]) for key in sqlite_row.keys()}

            phone_normalized = normalize_phone(str(_row_value(row, "phone", "phone_number", "Phone") or ""))
            if phone_normalized is None:
                skipped_no_phone += 1
                continue

            address = str(_row_value(row, "address", "Address", "formatted_address") or "")
            zip_code = extract_zip(address)
            metro = zip_to_metro(zip_code or "", configured_metros)
            if metro is None:
                skipped_no_metro += 1
                continue

            # Compute ICP score from raw fields
            total_score, score_tier, _signals = compute_icp_score(row)

            timezone = zip_to_timezone(zip_code or "")
            source_category = str(_row_value(row, "source_category") or "")
            batch.append(
                {
                    "tenant_id": OUTBOUND_TENANT_ID,
                    "business_name": str(_row_value(row, "business_name", "name", "company", "title") or "Unknown Business"),
                    "trade": _trade_value(source_category),
                    "metro": metro,
                    "website": _row_value(row, "website", "domain", "url"),
                    "address": address or None,
                    "phone": _row_value(row, "phone", "phone_number", "Phone"),
                    "phone_normalized": phone_normalized,
                    "source": "leads_db",
                    "source_listing_id": _row_value(row, "source_listing_id", "listing_id", "id", "lead_id", "place_id"),
                    "timezone": timezone,
                    "raw_source": row,
                    # Direct to call_ready with pre-computed ICP score
                    "stage": "call_ready",
                    "total_score": total_score,
                    "score_tier": score_tier,
                }
            )

            if len(batch) >= batch_size:
                result = store.upsert_outbound_prospects(batch)
                inserted += int(result["inserted"])
                skipped_dedup += int(result["skipped_dedup"])
                batch.clear()

        if batch:
            result = store.upsert_outbound_prospects(batch)
            inserted += int(result["inserted"])
            skipped_dedup += int(result["skipped_dedup"])
    finally:
        connection.close()

    return {
        "ingested": inserted,
        "skipped_dedup": skipped_dedup,
        "skipped_no_phone": skipped_no_phone,
        "skipped_no_metro": skipped_no_metro,
    }

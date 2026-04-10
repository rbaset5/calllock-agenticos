"""Google Maps scraper ingest — Week 1 Cohort A HVAC discovery pipeline.

Takes JSON output from gosom/google-maps-scraper, filters to Cohort A
(4.0-4.5 stars, 50-100 reviews, listed after-hours coverage), and upserts
into outbound_prospects with source='maps_scraper', stage='call_ready'.

Bypasses scoring.py and queue_builder.py entirely — Cohort A prospects
are retrieved via the dedicated --list command for Tuesday's dialing.

Pipeline:

    ┌────────────────────────────────────────────────┐
    │ 1. Load scraper JSON (NDJSON fallback)         │
    │ 2. Normalize + flag toll-free phones           │
    │ 3. Pre-check dedup (existing tenant phones)    │
    │ 4. Cohort A filter (rating, reviews, hours)    │
    │ 5. Build records (explicit stage='call_ready') │
    │ 6. upsert_or_enrich_prospects + timing         │
    │ 7. Print summary stats                         │
    └────────────────────────────────────────────────┘
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from .constants import OUTBOUND_TENANT_ID
from .ingest import normalize_phone
from .lsa_db import DEFAULT_DB as LSA_DB_PATH
from . import store


# Cohort A ICP — loosened after Monday 2026-04-06 smoke test against real
# Farmington Hills HVAC data showed the original 4.0-4.5 + 50-100 filter
# produced zero matches. Michigan HVAC ratings cluster at 4.5-5.0 (review
# inflation), review counts are bimodal (<10 or >300), and zero shops list
# 24-hour coverage. The loosened filter sacrifices the "pain from complaints"
# and "pays for answering service" signals in exchange for a non-empty list.
COHORT_A_MIN_RATING = 4.0
COHORT_A_MIN_REVIEWS = 0
COHORT_A_MAX_REVIEWS = 200

TOLL_FREE_PREFIXES = ("+1800", "+1888", "+1877", "+1866", "+1855", "+1844", "+1833")

# Category keywords that signal the listing is NOT a field-service contractor.
# Rejected on first match, case-insensitive substring in the joined category string.
CATEGORY_BLACKLIST = (
    "wholesale",
    "wholesaler",
    "supply",
    "supplier",
    "supplies",
    "parts",
    "warehouse",
    "distributor",
    "distribution",
    "manufacturer",
)

STATE_TIMEZONE = {
    "MI": "America/Detroit",
    "FL": "America/New_York",
    "TX": "America/Chicago",
    "IL": "America/Chicago",
    "AZ": "America/Phoenix",
}


def load_scraper_output(path: str) -> list[dict[str, Any]]:
    """Parse gosom JSON output. Falls back to NDJSON line-by-line if truncated."""
    text = Path(path).read_text(encoding="utf-8")

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
    except json.JSONDecodeError:
        pass

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        raise ValueError(f"could not parse {path} as JSON or NDJSON")
    return rows


def _get_field(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, "", []):
            return row[key]
    return None


def extract_name(row: dict[str, Any]) -> str | None:
    val = _get_field(row, "title", "name", "business_name")
    return str(val) if val else None


def extract_phone(row: dict[str, Any]) -> str | None:
    val = _get_field(row, "phone", "phone_number")
    return str(val) if val else None


def extract_rating(row: dict[str, Any]) -> float | None:
    val = _get_field(row, "rating", "review_rating", "stars")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def extract_review_count(row: dict[str, Any]) -> int | None:
    val = _get_field(row, "review_count", "reviews_count", "reviews")
    if val is None:
        return None
    if isinstance(val, list):
        return len(val)
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def extract_hours(row: dict[str, Any]) -> Any:
    val = _get_field(row, "open_hours", "hours", "opening_hours")
    return val if val is not None else {}


def extract_address(row: dict[str, Any]) -> str | None:
    val = _get_field(row, "address", "complete_address", "full_address")
    return str(val) if val else None


def extract_website(row: dict[str, Any]) -> str | None:
    val = _get_field(row, "website", "web_site", "site", "url")
    return str(val) if val else None


def extract_categories(row: dict[str, Any]) -> list[str]:
    """Return a flat list of category strings from gosom's `category` (str) and
    `categories` (list[str]) fields."""
    out: list[str] = []
    cat = row.get("category")
    if cat:
        out.append(str(cat))
    cats = row.get("categories") or []
    if isinstance(cats, list):
        out.extend(str(c) for c in cats if c)
    return out


def is_blacklisted_category(row: dict[str, Any]) -> bool:
    """True if any category contains a blacklisted keyword (wholesaler, parts, etc)."""
    joined = " ".join(extract_categories(row)).lower()
    if not joined:
        return False
    return any(word in joined for word in CATEGORY_BLACKLIST)


def extract_timezone(row: dict[str, Any], state: str) -> str | None:
    """Prefer the scraper's own timezone if present, fall back to state map."""
    val = _get_field(row, "timezone", "tz")
    if val:
        return str(val)
    return STATE_TIMEZONE.get(state.upper())


def has_after_hours_coverage(hours: Any) -> bool | None:
    """Return True for 24-hour coverage, False for business-hours-only, None if unknown.

    Unknown hours (empty dict, missing, unparseable) are intentionally NOT dropped —
    we only drop when we can definitively say "no after-hours coverage".
    """
    if hours is None:
        return None
    if isinstance(hours, str):
        lower = hours.lower()
        if not lower.strip():
            return None
        if "24" in lower and "hour" in lower:
            return True
        return False
    if isinstance(hours, dict):
        if not hours:
            return None
        # gosom emits list-valued entries like {"Friday": ["8 AM-9 PM"]} — flatten.
        flat: list[str] = []
        for v in hours.values():
            if isinstance(v, list):
                flat.extend(str(x).lower() for x in v if x)
            elif v:
                flat.append(str(v).lower())
        if not flat:
            return None
        if any("24" in s and "hour" in s for s in flat):
            return True
        return False
    return None


def is_toll_free(phone_normalized: str | None) -> bool:
    if not phone_normalized:
        return False
    return phone_normalized.startswith(TOLL_FREE_PREFIXES)


def load_lsa_phone_set(db_path: Path | str | None = None) -> set[str]:
    """Load phones from lsa_discovery.db for exclusion (Cohort B overlap)."""
    path = Path(db_path) if db_path else Path(str(LSA_DB_PATH))
    if not path.exists():
        return set()
    conn = sqlite3.connect(str(path))
    try:
        try:
            rows = conn.execute("SELECT phone FROM lsa_businesses WHERE phone IS NOT NULL").fetchall()
        except sqlite3.OperationalError:
            return set()
    finally:
        conn.close()
    normalized: set[str] = set()
    for (raw,) in rows:
        n = normalize_phone(raw)
        if n:
            normalized.add(n)
    return normalized


def load_existing_phone_set(tenant_id: str = OUTBOUND_TENANT_ID) -> set[str]:
    """Single GET for all prospects in the tenant → phone set for dedup pre-check.

    For Week 1 volumes (<1000 existing rows) this is one HTTP round-trip, which
    beats the originally-planned batched IN-clause.
    """
    try:
        existing = store.list_outbound_prospects(tenant_id=tenant_id)
    except Exception:
        return set()
    return {row.get("phone_normalized") for row in existing if row.get("phone_normalized")}


def build_record(
    row: dict[str, Any],
    *,
    phone_normalized: str,
    state: str,
    rating: float,
    review_count: int,
    hours: Any,
    after_hours: bool | None,
    toll_free: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "tenant_id": OUTBOUND_TENANT_ID,
        "business_name": extract_name(row) or "(unknown)",
        "trade": "hvac",
        "phone": extract_phone(row),
        "phone_normalized": phone_normalized,
        "address": extract_address(row),
        "website": extract_website(row),
        "source": "maps_scraper",
        "timezone": extract_timezone(row, state),
        "raw_source": {
            "cohort": "a",
            "rating": rating,
            "review_count": review_count,
            "hours_of_operation": hours,
            "has_after_hours_coverage": after_hours,
            "scraper_source": "gosom/google-maps-scraper",
        },
        "total_score": 0,
        "score_tier": "unscored",
        "stage": "call_ready",
    }
    if toll_free:
        record["stage"] = "disqualified"
        record["disqualification_reason"] = "toll_free_gatekeeper"
    return record


def run_ingest(
    *,
    input_path: str,
    state: str,
    dry_run: bool = False,
    lsa_db_path: Path | str | None = None,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> dict[str, Any]:
    try:
        rows = load_scraper_output(input_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc), "raw_rows": 0}

    stats: dict[str, Any] = {
        "raw_rows": len(rows),
        "phone_valid": 0,
        "toll_free": 0,
        "category_blacklist": 0,
        "missing_fields_drop": 0,
        "rating_pass": 0,
        "review_count_pass": 0,
        "lsa_exclude": 0,
        "dedup_skip": 0,
        "disqualified": 0,
        "final_ingest": 0,
    }

    lsa_set = load_lsa_phone_set(lsa_db_path)
    existing_set = load_existing_phone_set(tenant_id=tenant_id)

    records: list[dict[str, Any]] = []

    for row in rows:
        phone_normalized = normalize_phone(extract_phone(row))
        if not phone_normalized:
            continue
        stats["phone_valid"] += 1

        if is_toll_free(phone_normalized):
            stats["toll_free"] += 1
            records.append(
                build_record(
                    row,
                    phone_normalized=phone_normalized,
                    state=state,
                    rating=extract_rating(row) or 0.0,
                    review_count=extract_review_count(row) or 0,
                    hours=extract_hours(row),
                    after_hours=None,
                    toll_free=True,
                )
            )
            stats["disqualified"] += 1
            continue

        if phone_normalized in existing_set:
            stats["dedup_skip"] += 1
            continue

        if phone_normalized in lsa_set:
            stats["lsa_exclude"] += 1
            continue

        if is_blacklisted_category(row):
            stats["category_blacklist"] += 1
            continue

        rating = extract_rating(row)
        review_count = extract_review_count(row)
        if rating is None or review_count is None:
            stats["missing_fields_drop"] += 1
            continue

        if rating < COHORT_A_MIN_RATING:
            continue
        stats["rating_pass"] += 1

        if not (COHORT_A_MIN_REVIEWS <= review_count <= COHORT_A_MAX_REVIEWS):
            continue
        stats["review_count_pass"] += 1

        # Hours are captured for raw_source metadata but no longer gate the
        # filter — zero shops in the Monday smoke sample listed 24-hour coverage,
        # and the outside-voice review flagged the "already pays for answering
        # service" signal as a tight proxy that was killing every match.
        hours = extract_hours(row)
        after_hours = has_after_hours_coverage(hours)

        records.append(
            build_record(
                row,
                phone_normalized=phone_normalized,
                state=state,
                rating=rating,
                review_count=review_count,
                hours=hours,
                after_hours=after_hours,
                toll_free=False,
            )
        )

    stats["final_ingest"] = len(records) - stats["disqualified"]

    if dry_run:
        stats["dry_run"] = True
        stats["sample_records"] = records[:5]
        stats["upsert_duration_sec"] = 0.0
        stats["per_record_ms"] = 0.0
        return stats

    if not records:
        stats["upsert_duration_sec"] = 0.0
        stats["per_record_ms"] = 0.0
        return stats

    t0 = time.perf_counter()
    upsert_result = store.upsert_or_enrich_prospects(records)
    elapsed = time.perf_counter() - t0

    stats["upsert_duration_sec"] = round(elapsed, 3)
    stats["per_record_ms"] = round((elapsed / len(records)) * 1000, 1)
    stats["upsert_result"] = upsert_result
    return stats


def list_cohort_a(
    *,
    limit: int = 50,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> list[dict[str, Any]]:
    """Dedicated retrieval for Tuesday's dialing — bypasses queue_builder entirely.

    Filters outbound_prospects to source='maps_scraper' AND stage='call_ready'.
    Sorted alphabetically by business name.
    """
    prospects = store.list_outbound_prospects(tenant_id=tenant_id, stages=["call_ready"])
    rows = [p for p in prospects if p.get("source") == "maps_scraper"]
    rows.sort(key=lambda p: str(p.get("business_name") or ""))
    return rows[:limit]


def _print_stats(stats: dict[str, Any]) -> None:
    print("Summary:")
    ordered_keys = [
        "raw_rows",
        "phone_valid",
        "toll_free",
        "category_blacklist",
        "missing_fields_drop",
        "rating_pass",
        "review_count_pass",
        "lsa_exclude",
        "dedup_skip",
        "disqualified",
        "final_ingest",
        "upsert_duration_sec",
        "per_record_ms",
    ]
    for key in ordered_keys:
        if key in stats:
            print(f"  {key}: {stats[key]}")
    if "sample_records" in stats and stats["sample_records"]:
        print("Sample records:")
        for rec in stats["sample_records"]:
            raw = rec.get("raw_source") or {}
            print(
                f"  - {rec.get('business_name')} | {rec.get('phone_normalized')} "
                f"| {raw.get('rating')}⭐ ({raw.get('review_count')}) "
                f"| stage={rec.get('stage')}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="outbound.maps_scraper_ingest",
        description="Ingest Google Maps scraper output into outbound_prospects",
    )
    parser.add_argument("--input", help="Path to gosom scraper JSON output")
    parser.add_argument("--state", default="MI", help="Two-letter state code (MI, FL, TX, IL, AZ)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and filter without writing to Supabase")
    parser.add_argument("--list", action="store_true", dest="list_mode", help="List current Cohort A prospects instead of ingesting")
    parser.add_argument("--limit", type=int, default=50, help="Max rows for --list mode")
    args = parser.parse_args(argv)

    if args.list_mode:
        rows = list_cohort_a(limit=args.limit)
        if not rows:
            print("(no Cohort A prospects found)")
            return 0
        print(f"Cohort A prospects ({len(rows)} of max {args.limit}):")
        for row in rows:
            raw = row.get("raw_source") or {}
            rating = raw.get("rating", "?")
            rc = raw.get("review_count", "?")
            print(
                f"  - {row.get('business_name')} | {row.get('phone_normalized')} "
                f"| {rating}⭐ ({rc}) | {row.get('address') or ''}"
            )
        return 0

    if not args.input:
        parser.error("--input is required unless --list is passed")

    result = run_ingest(
        input_path=args.input,
        state=args.state,
        dry_run=args.dry_run,
    )
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1
    _print_stats(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

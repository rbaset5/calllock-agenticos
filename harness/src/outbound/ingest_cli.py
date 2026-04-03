"""CLI to run lead ingest from SQLite leads DB → Supabase outbound_prospects.

Usage:
    python -m outbound.ingest_cli --metros Phoenix,Houston --trades hvac,plumbing --dry-run
    python -m outbound.ingest_cli --metros Phoenix --trades hvac  # live run
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .ingest import DEFAULT_DB_PATH, compute_icp_score, normalize_phone, run_batch, _expanded_db_path, _coerce_jsonable, _row_value
from .metro import extract_zip, zip_to_metro


def _dry_run(db_path: str, metros: list[str], trades: list[str], limit: int = 500) -> None:
    """Score leads without writing to Supabase — shows distribution."""
    connection = sqlite3.connect(_expanded_db_path(db_path))
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in trades)
    query = (
        f"SELECT * FROM leads "
        f"WHERE lower(source_category) IN ({placeholders}) "
        f"AND (is_franchise = 0 OR is_franchise IS NULL) "
        f"AND phone <> '' "
        f"LIMIT {limit}"
    )

    tiers: dict[str, int] = {"a_lead": 0, "b_lead": 0, "c_lead": 0, "unscored": 0}
    signal_counts: dict[str, int] = {}
    matched_metro = 0
    skipped_metro = 0
    skipped_phone = 0
    samples: dict[str, list[dict]] = {"a_lead": [], "b_lead": [], "c_lead": []}

    cursor = connection.execute(query, tuple(trades))
    for sqlite_row in cursor:
        row = {key: _coerce_jsonable(sqlite_row[key]) for key in sqlite_row.keys()}

        phone = str(_row_value(row, "phone", "phone_number") or "")
        if not normalize_phone(phone):
            skipped_phone += 1
            continue

        address = str(_row_value(row, "address") or "")
        zip_code = extract_zip(address)
        metro = zip_to_metro(zip_code or "", metros)
        if metro is None:
            skipped_metro += 1
            continue
        matched_metro += 1

        total, tier, signals = compute_icp_score(row)
        tiers[tier] += 1
        for sig in signals:
            signal_counts[sig] = signal_counts.get(sig, 0) + 1

        if tier in samples and len(samples[tier]) < 3:
            samples[tier].append({
                "name": _row_value(row, "business_name", "name") or "?",
                "metro": metro,
                "score": total,
                "signals": list(signals.keys()),
            })

    connection.close()

    print(f"\n{'='*60}")
    print(f"DRY RUN — {limit} rows scanned from leads DB")
    print(f"Metros: {', '.join(metros)}")
    print(f"Trades: {', '.join(trades)}")
    print(f"{'='*60}")
    print(f"\nMatched metro: {matched_metro}")
    print(f"Skipped (no metro match): {skipped_metro}")
    print(f"Skipped (bad phone): {skipped_phone}")
    print(f"\n--- Tier Distribution ---")
    for tier, count in tiers.items():
        pct = (count / matched_metro * 100) if matched_metro else 0
        print(f"  {tier:12s}: {count:5d}  ({pct:.1f}%)")
    print(f"\n--- Signal Frequency (among metro-matched) ---")
    for sig, count in sorted(signal_counts.items(), key=lambda x: -x[1]):
        pct = (count / matched_metro * 100) if matched_metro else 0
        print(f"  {sig:20s}: {count:5d}  ({pct:.1f}%)")
    print(f"\n--- Sample A-leads ---")
    for s in samples.get("a_lead", []):
        print(f"  {s['name'][:40]:40s} | {s['metro']:12s} | score={s['score']} | {', '.join(s['signals'])}")
    print(f"\n--- Sample B-leads ---")
    for s in samples.get("b_lead", []):
        print(f"  {s['name'][:40]:40s} | {s['metro']:12s} | score={s['score']} | {', '.join(s['signals'])}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest leads from SQLite DB")
    parser.add_argument("--source", default="leads_db", choices=["leads_db", "lsa"],
                        help="Data source: leads_db (default) or lsa (LSA discovery DB)")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to leads.db")
    parser.add_argument("--metros", help="Comma-separated metro names (required for leads_db)")
    parser.add_argument("--trades", default="hvac,plumbing", help="Comma-separated trades")
    parser.add_argument("--dry-run", action="store_true", help="Score without writing to Supabase")
    parser.add_argument("--limit", type=int, default=500, help="Row limit for dry run (default 500)")
    parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for live run")
    parser.add_argument("--lsa-db", help="Path to lsa_discovery.db (for --source lsa)")
    parser.add_argument("--min-reviews", type=int, default=10, help="Min review count for LSA filter")
    parser.add_argument("--max-reviews", type=int, default=100, help="Max review count for LSA filter")
    args = parser.parse_args()

    if args.source == "lsa":
        from .ingest import ingest_from_lsa
        print(f"Running LSA ingest: reviews {args.min_reviews}-{args.max_reviews}")
        result = ingest_from_lsa(
            lsa_db_path=args.lsa_db,
            min_reviews=args.min_reviews,
            max_reviews=args.max_reviews,
        )
        print(f"\nResults:")
        for key, val in result.items():
            print(f"  {key}: {val}")
        return

    if not args.metros:
        parser.error("--metros is required for leads_db source")

    metros = [m.strip() for m in args.metros.split(",") if m.strip()]
    trades = [t.strip().lower() for t in args.trades.split(",") if t.strip()]

    if args.dry_run:
        _dry_run(args.db, metros, trades, limit=args.limit)
    else:
        print(f"Running live ingest: metros={metros}, trades={trades}")
        result = run_batch(args.db, metros=metros, trades=trades, batch_size=args.batch_size)
        print(f"\nResults:")
        for key, val in result.items():
            print(f"  {key}: {val}")


if __name__ == "__main__":
    main()

"""LSA discovery for small-market HVAC shops via SerpAPI.

Usage:
    # Dry run (validate 5 towns, no writes)
    python -m outbound.lsa_discovery --validate

    # Full run
    python -m outbound.lsa_discovery

    # Export CSV only (from existing DB)
    python -m outbound.lsa_discovery --export-only

    # Specify output path
    python -m outbound.lsa_discovery --output mi_hvac_lsa.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests

from outbound.ingest import normalize_phone
from outbound.lsa_db import (
    DEFAULT_DB,
    export_csv,
    init_db,
    query_completed,
    save_query,
    upsert_business,
)

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"
MARKETS_FILE = Path(__file__).parent / "data" / "small_markets.json"
LEADS_DB_PATH = Path.home() / "conductor/workspaces/CallLock-Leads/missoula/emtoss_downloader/data/leads.db"
REQUEST_DELAY = 20  # seconds between requests (Starter plan: 200/hr = 18s floor + 2s buffer)
MAX_RETRIES = 3


def load_markets(states: list[str] | None = None) -> list[dict]:
    with open(MARKETS_FILE) as f:
        data = json.load(f)
    markets = data if isinstance(data, list) else data.get("michigan", [])
    if states:
        upper = {s.upper() for s in states}
        markets = [m for m in markets if m.get("state", "").upper() in upper]
    return [m for m in markets if m.get("data_cid") and m["data_cid"] != "TBD"]


def query_hash(town: str, state: str) -> str:
    key = f"lsa|hvac|{town}|{state}".lower()
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def fetch_lsa(town: str, data_cid: str) -> dict:
    resp = requests.get(SERPAPI_URL, params={
        "engine": "google_local_services",
        "q": "hvac",
        "data_cid": data_cid,
        "api_key": SERPAPI_KEY,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_lsa_results(data: dict, town: str, state: str) -> list[dict]:
    ads = data.get("local_ads", [])
    businesses = []
    for ad in ads:
        phone_raw = ad.get("phone")
        phone = normalize_phone(phone_raw)
        if not phone:
            continue
        businesses.append({
            "business_name": ad.get("title", ""),
            "phone": phone,
            "address": ad.get("address"),
            "town": town,
            "state": state,
            "rating": ad.get("rating"),
            "review_count": ad.get("reviews"),
            "years_in_business": ad.get("years_in_business"),
            "service_area": ad.get("service_area"),
            "lsa_badge": ad.get("badge"),
        })
    return businesses


def cross_reference_leads_db(businesses: list[dict]) -> list[dict]:
    if not LEADS_DB_PATH.exists():
        print(f"  leads.db not found at {LEADS_DB_PATH}, skipping cross-ref")
        return businesses

    leads_conn = sqlite3.connect(str(LEADS_DB_PATH))
    leads_phones = set()
    for row in leads_conn.execute("SELECT phone FROM leads WHERE phone IS NOT NULL"):
        p = normalize_phone(row[0])
        if p:
            leads_phones.add(p)
    leads_conn.close()

    for biz in businesses:
        biz["leads_db_match"] = 1 if biz["phone"] in leads_phones else 0
    return businesses


def run_discovery(conn: sqlite3.Connection, markets: list[dict], validate_only: bool = False):
    if validate_only:
        markets = markets[:5]
        print(f"VALIDATION MODE: testing {len(markets)} towns\n")

    total_businesses = 0
    towns_with_results = 0

    for i, market in enumerate(markets):
        town = market["town"]
        state = market["state"]
        cid = market["data_cid"]
        qhash = query_hash(town, state)

        if query_completed(conn, qhash):
            print(f"[{i+1}/{len(markets)}] {town}, {state} — already completed, skipping")
            continue

        print(f"[{i+1}/{len(markets)}] {town}, {state} (cid={cid})")

        for attempt in range(MAX_RETRIES):
            try:
                data = fetch_lsa(town, cid)

                if "error" in data:
                    error_msg = data["error"]
                    if "out of searches" in error_msg.lower():
                        print(f"  OUT OF SEARCHES — stopping. Export what we have.")
                        save_query(conn, qhash, town, state, "permanent_error",
                                   error_text=error_msg)
                        return
                    elif "429" in str(error_msg) or "throughput" in error_msg.lower():
                        print(f"  Throttled, waiting {REQUEST_DELAY}s...")
                        time.sleep(REQUEST_DELAY)
                        continue
                    else:
                        print(f"  API error: {error_msg}")
                        save_query(conn, qhash, town, state, "retryable_error",
                                   error_text=error_msg)
                        break

                businesses = parse_lsa_results(data, town, state)
                businesses = cross_reference_leads_db(businesses)

                for biz in businesses:
                    upsert_business(conn, biz)

                save_query(conn, qhash, town, state, "success",
                           result_count=len(businesses),
                           raw_response=json.dumps(data))

                count = len(businesses)
                total_businesses += count
                if count > 0:
                    towns_with_results += 1
                print(f"  → {count} businesses found ({sum(1 for b in businesses if b.get('leads_db_match'))} matched leads.db)")
                break

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = REQUEST_DELAY * (attempt + 1)
                    print(f"  429 — waiting {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                elif e.response is not None and e.response.status_code >= 500:
                    wait = 2 ** (attempt + 1)
                    print(f"  {e.response.status_code} — retrying in {wait}s")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  HTTP error: {e}")
                    save_query(conn, qhash, town, state, "retryable_error",
                               error_text=str(e))
                    break
            except requests.exceptions.RequestException as e:
                wait = 2 ** (attempt + 1)
                print(f"  Connection error — retrying in {wait}s: {e}")
                time.sleep(wait)
                continue

        # Rate limit between requests
        if i < len(markets) - 1:
            print(f"  Waiting {REQUEST_DELAY}s...")
            time.sleep(REQUEST_DELAY)

    print(f"\nDone. {total_businesses} businesses from {towns_with_results}/{len(markets)} towns.")

    if validate_only:
        if towns_with_results >= 3:
            print("VALIDATION PASSED: 3+ towns returned results. Safe to run full sweep.")
        else:
            print(f"VALIDATION CONCERN: only {towns_with_results}/5 towns had results. Consider pivoting.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="LSA discovery for small-market HVAC")
    parser.add_argument("--validate", action="store_true", help="Test 5 towns only")
    parser.add_argument("--export-only", action="store_true", help="Export CSV from existing DB")
    parser.add_argument("--output", default="lsa_hvac.csv", help="CSV output path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--states", help="Comma-separated state codes to filter (e.g., FL,TX,IL,AZ)")
    args = parser.parse_args(argv)

    if not args.export_only and not SERPAPI_KEY:
        print("Error: SERPAPI_KEY environment variable not set")
        sys.exit(1)

    conn = init_db(args.db)

    if args.export_only:
        count = export_csv(conn, args.output)
        print(f"Exported {count} businesses to {args.output}")
        return

    states = [s.strip() for s in args.states.split(",")] if args.states else None
    markets = load_markets(states=states)
    if not markets:
        print("No markets with valid data_cid found")
        sys.exit(1)

    print(f"Loaded {len(markets)} markets")
    run_discovery(conn, markets, validate_only=args.validate)

    count = export_csv(conn, args.output)
    print(f"Exported {count} businesses to {args.output}")


if __name__ == "__main__":
    main()

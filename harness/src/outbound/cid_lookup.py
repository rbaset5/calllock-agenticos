"""Look up Google Maps data_cid values for towns in small_markets.json.

Usage:
    SERPAPI_KEY=xxx python -m outbound.cid_lookup
    SERPAPI_KEY=xxx python -m outbound.cid_lookup --dry-run  # show what needs lookup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"
MARKETS_FILE = Path(__file__).parent / "data" / "small_markets.json"
REQUEST_DELAY = 20  # seconds between requests (Starter plan: 200/hr = 18s floor + 2s buffer)


def lookup_cid(town: str, state: str) -> str | None:
    """Look up data_cid for a town via SerpAPI Google Maps."""
    resp = requests.get(SERPAPI_URL, params={
        "engine": "google_maps",
        "q": f"{town}, {state}",
        "type": "search",
        "api_key": SERPAPI_KEY,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # The place_results or local_results contain data_cid
    place = data.get("place_results", {})
    if place and place.get("data_cid"):
        return str(place["data_cid"])

    # Try local_results (list of places)
    local = data.get("local_results", [])
    if local and local[0].get("data_cid"):
        return str(local[0]["data_cid"])

    # Try search_information for the place
    search_info = data.get("search_information", {})
    if search_info.get("place_id"):
        return str(search_info["place_id"])

    return None


def main():
    parser = argparse.ArgumentParser(description="Look up data_cid values for towns")
    parser.add_argument("--dry-run", action="store_true", help="Show what needs lookup")
    parser.add_argument("--states", help="Comma-separated states to filter")
    args = parser.parse_args()

    if not args.dry_run and not SERPAPI_KEY:
        print("Error: SERPAPI_KEY not set")
        sys.exit(1)

    with open(MARKETS_FILE) as f:
        markets = json.load(f)

    needs_lookup = [m for m in markets if m.get("data_cid") == "TBD"]
    if args.states:
        states = {s.strip().upper() for s in args.states.split(",")}
        needs_lookup = [m for m in needs_lookup if m["state"].upper() in states]

    print(f"Total markets: {len(markets)}")
    print(f"Need CID lookup: {len(needs_lookup)}")

    if args.dry_run:
        for m in needs_lookup:
            print(f"  {m['town']}, {m['state']}")
        return

    updated = 0
    failed = 0
    for i, market in enumerate(needs_lookup):
        town = market["town"]
        state = market["state"]
        print(f"[{i+1}/{len(needs_lookup)}] Looking up {town}, {state}...", end=" ")

        try:
            cid = lookup_cid(town, state)
            if cid:
                # Find and update in the full list
                for m in markets:
                    if m["town"] == town and m["state"] == state:
                        m["data_cid"] = cid
                        break
                updated += 1
                print(f"→ {cid}")
            else:
                failed += 1
                print("→ NOT FOUND")
        except Exception as e:
            failed += 1
            print(f"→ ERROR: {e}")

        if i < len(needs_lookup) - 1:
            time.sleep(REQUEST_DELAY)

    # Write back
    with open(MARKETS_FILE, "w") as f:
        json.dump(markets, f, indent=2)
        f.write("\n")

    print(f"\nDone. Updated: {updated}, Failed: {failed}")
    print(f"Written to {MARKETS_FILE}")


if __name__ == "__main__":
    main()

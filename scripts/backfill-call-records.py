#!/usr/bin/env python3
"""Backfill call_records by replaying recent Retell calls through the harness webhook.

Each call is fetched from the Retell API, wrapped in the call-ended payload format,
HMAC-signed with the Retell API key, and POST'd to the live harness endpoint.
The harness runs the full extraction pipeline and writes to Supabase.

Usage:
    RETELL_API_KEY=key_xxx python3 scripts/backfill-call-records.py [--limit 10] [--dry-run]
    RETELL_API_KEY=key_xxx python3 scripts/backfill-call-records.py --harness-url https://calllock-harness.onrender.com
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

RETELL_API = "https://api.retellai.com"
DEFAULT_HARNESS_URL = "https://calllock-harness.onrender.com"
DEFAULT_AGENT_ID = "agent_4fb753a447e714064e71fadc6d"


def sign_payload(body: bytes, api_key: str) -> str:
    """Generate x-retell-signature header value matching Retell's format.

    Format: v=<timestamp_ms>,d=<hex_digest>
    HMAC: SHA256(body + timestamp_bytes, api_key)
    """
    ts = str(int(time.time() * 1000))
    message = body + ts.encode()
    digest = hmac.new(api_key.encode(), message, hashlib.sha256).hexdigest()
    return f"v={ts},d={digest}"


def fetch_calls(api_key: str, agent_id: str, limit: int) -> list[dict[str, Any]]:
    """Fetch recent ended calls for the agent."""
    r = requests.post(
        f"{RETELL_API}/v2/list-calls",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"limit": limit, "filter_criteria": {"agent_id": [agent_id]}},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    calls = data if isinstance(data, list) else data.get("calls", data.get("items", []))
    return [c for c in calls if c.get("call_status") == "ended"]


def fetch_call_detail(api_key: str, call_id: str) -> dict[str, Any]:
    """Fetch full call details including transcript and tool_call_results."""
    r = requests.get(
        f"{RETELL_API}/v2/get-call/{call_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def build_call_ended_payload(call: dict[str, Any]) -> dict[str, Any]:
    """Build a Retell call-ended webhook payload from a call detail object."""
    return {
        "event": "call_ended",
        "call": {
            "call_id": call.get("call_id", ""),
            "call_status": "ended",
            "agent_id": call.get("agent_id", DEFAULT_AGENT_ID),
            "from_number": call.get("from_number", ""),
            "to_number": call.get("to_number", "+13126463816"),
            "start_timestamp": call.get("start_timestamp"),
            "end_timestamp": call.get("end_timestamp"),
            "duration_ms": call.get("duration_ms") or (
                (call.get("end_timestamp", 0) - call.get("start_timestamp", 0))
                if call.get("end_timestamp") and call.get("start_timestamp") else 0
            ),
            "transcript": call.get("transcript", ""),
            "transcript_object": call.get("transcript_object", []),
            "call_analysis": call.get("call_analysis", {}),
            "recording_url": call.get("recording_url"),
            "public_log_url": call.get("public_log_url"),
            "metadata": call.get("metadata", {}),
            "retell_llm_dynamic_variables": call.get("retell_llm_dynamic_variables", {}),
            "custom_metadata": call.get("custom_metadata") or {},
        },
    }


def replay_call(
    harness_url: str,
    api_key: str,
    payload: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send a signed call-ended webhook to the harness."""
    endpoint = f"{harness_url}/webhook/retell/call-ended"
    body = json.dumps(payload).encode()
    signature = sign_payload(body, api_key)

    call_id = payload.get("call", {}).get("call_id", "?")
    print(f"  POST {endpoint}  call_id={call_id}", end="  ")

    if dry_run:
        print("(dry-run, skipped)")
        return {"status": "dry-run"}

    r = requests.post(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-retell-signature": signature,
        },
        timeout=30,
    )
    result = {"http_status": r.status_code}
    try:
        result.update(r.json())
    except Exception:
        result["raw"] = r.text[:200]

    status_str = f"HTTP {r.status_code}"
    if r.status_code == 200:
        print(f"OK  extraction_status={result.get('extraction_status', '?')}")
    elif r.status_code == 409 or result.get("status") == "duplicate":
        print("SKIP (already in call_records)")
    else:
        print(f"FAIL  {result}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill call_records from Retell history")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    parser.add_argument("--harness-url", default=DEFAULT_HARNESS_URL)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't POST")
    args = parser.parse_args()

    api_key = os.environ.get("RETELL_API_KEY")
    if not api_key:
        print("Error: RETELL_API_KEY env var is required", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching last {args.limit} ended calls for agent {args.agent_id}...")
    calls = fetch_calls(api_key, args.agent_id, args.limit)
    print(f"Found {len(calls)} ended calls\n")

    success = skipped = failed = 0

    for i, call_summary in enumerate(calls, 1):
        call_id = call_summary.get("call_id", "?")
        from_num = call_summary.get("from_number", "?")
        start = call_summary.get("start_timestamp", 0)
        dur_s = call_summary.get("duration_ms", 0) // 1000
        print(f"[{i}/{len(calls)}] {call_id}  from={from_num}  duration={dur_s}s")

        try:
            detail = fetch_call_detail(api_key, call_id)
        except Exception as e:
            print(f"  ERROR fetching detail: {e}")
            failed += 1
            continue

        payload = build_call_ended_payload(detail)
        result = replay_call(args.harness_url, api_key, payload, dry_run=args.dry_run)

        status = result.get("http_status", 0)
        if status == 200:
            success += 1
        elif status in (409,) or result.get("status") == "duplicate":
            skipped += 1
        elif result.get("status") == "dry-run":
            skipped += 1
        else:
            failed += 1

        # small delay to avoid overwhelming Render cold-start
        if i < len(calls):
            time.sleep(0.5)

    print(f"\nDone: {success} inserted, {skipped} skipped/duplicate, {failed} failed")
    if not args.dry_run and success > 0:
        print(f"\nCall records should now appear at the app.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import uuid

import httpx


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    response = httpx.get(url, headers=headers, timeout=15.0)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def main() -> int:
    harness_base = require("HARNESS_BASE_URL").rstrip("/")
    inngest_base = os.getenv("INNGEST_BASE_URL", "").rstrip("/")
    supabase_url = require("SUPABASE_URL").rstrip("/")
    supabase_key = require("SUPABASE_SERVICE_ROLE_KEY")
    tenant_slug = os.getenv("TENANT_SLUG", "tenant-alpha")

    print("Checking harness health...")
    harness_health = get_json(f"{harness_base}/health")
    print(json.dumps(harness_health, indent=2))

    if inngest_base:
        print("Checking inngest health...")
        inngest_health = get_json(f"{inngest_base}/health")
        print(json.dumps(inngest_health, indent=2))

        print("Checking inngest function metadata...")
        metadata = get_json(f"{inngest_base}/api/inngest")
        print(json.dumps(metadata, indent=2))

    print("Dispatching test event to harness event endpoint...")
    auth_headers = {}
    if os.getenv("HARNESS_EVENT_SECRET"):
      auth_headers["Authorization"] = f"Bearer {os.environ['HARNESS_EVENT_SECRET']}"

    result = post_json(
        f"{harness_base}/events/process-call",
        {
            "name": "harness/process-call",
            "data": {
                "call_id": f"check-{uuid.uuid4()}",
                "tenant_id": tenant_slug,
                "problem_description": "System-generated deployment check.",
                "transcript": "Customer says there is no heat and wants urgent help.",
            },
        },
        headers=auth_headers,
    )
    print(json.dumps(result, indent=2))

    print("Verifying persisted job in Supabase...")
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    persisted = get_json(
        f"{supabase_url}/rest/v1/jobs?select=origin_run_id,status&origin_run_id=eq.{result['run_id']}",
        headers=headers,
    )
    print(json.dumps(persisted, indent=2))

    if not persisted:
        raise SystemExit("No persisted job row found for dispatched run")

    print("Live stack check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

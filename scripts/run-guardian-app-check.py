#!/usr/bin/env python3
"""
Run eng-app guardian health check.

Loads app contract, queries test tenant data from Supabase, runs Playwright
checks, and outputs a JSON report suitable for agent_reports.

Usage:
    python scripts/run-guardian-app-check.py

Environment:
    APP_URL            - CallLock App URL (default: http://localhost:3000)
    SUPABASE_URL       - Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Supabase service role key

Output:
    JSON report to stdout with structure:
    {
        "agent_id": "eng-app",
        "report_type": "app-health-check",
        "status": "green|yellow|red",
        "pages_checked": N,
        "fields_passing": N,
        "fields_failing": N,
        "failures": [...],
        "warnings": [...]
    }
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TENANT_ID = "a0000000-0000-0000-0000-000000000001"


def run_playwright() -> dict:
    """Run Playwright tests and return parsed results."""
    app_url = os.getenv("APP_URL", "http://localhost:3000")
    result = subprocess.run(
        ["npx", "playwright", "test", "e2e/guardian-health-check.spec.ts", "--reporter=json"],
        cwd=str(REPO_ROOT / "web"),
        capture_output=True,
        text=True,
        env={**os.environ, "APP_URL": app_url, "TEST_TENANT_ID": TEST_TENANT_ID},
        timeout=120,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "error": "Playwright output not valid JSON",
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "returncode": result.returncode,
        }


def build_report(playwright_result: dict) -> dict:
    """Build agent_reports-compatible report from Playwright output."""
    if "error" in playwright_result:
        return {
            "agent_id": "eng-app",
            "report_type": "app-health-check",
            "status": "red",
            "pages_checked": 0,
            "fields_passing": 0,
            "fields_failing": 0,
            "failures": [playwright_result["error"]],
            "warnings": [],
            "violations": [playwright_result["error"]],
        }

    suites = playwright_result.get("suites", [])
    passing = 0
    failing = 0
    failures = []

    for suite in suites:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                if test.get("status") == "expected":
                    passing += 1
                else:
                    failing += 1
                    failures.append(f"{spec.get('title', 'unknown')}: {test.get('status', 'unknown')}")

    status = "green"
    if failing > 0:
        status = "red"
    elif not suites:
        status = "yellow"

    return {
        "agent_id": "eng-app",
        "report_type": "app-health-check",
        "status": status,
        "pages_checked": len(suites),
        "fields_passing": passing,
        "fields_failing": failing,
        "failures": failures,
        "warnings": [],
        **({"violations": failures} if failures else {}),
    }


def main() -> None:
    playwright_result = run_playwright()
    report = build_report(playwright_result)
    json.dump(report, sys.stdout, indent=2)
    sys.exit(0 if report["status"] != "red" else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_SRC = REPO_ROOT / "harness" / "src"
sys.path.insert(0, str(HARNESS_SRC))

from db import supabase_repository  # noqa: E402


def main() -> int:
    if not supabase_repository.is_configured():
        print("Supabase env vars are not configured.")
        return 1

    checks = [
        ("tenants", lambda: supabase_repository.get_tenant("tenant-alpha")),
        ("tenant_configs", lambda: supabase_repository.get_tenant_config("tenant-alpha")),
        ("compliance_rules", lambda: supabase_repository.get_compliance_rules("tenant-alpha")),
    ]

    failed = False
    for label, fn in checks:
        try:
            result = fn()
            if isinstance(result, list):
                print(f"{label}: ok ({len(result)} rows)")
            else:
                print(f"{label}: ok")
        except Exception as exc:  # pragma: no cover
            failed = True
            print(f"{label}: error -> {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

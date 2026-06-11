#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_harness_src() -> None:
    harness_src = REPO_ROOT / "harness" / "src"
    if str(harness_src) not in sys.path:
        sys.path.insert(0, str(harness_src))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the weekly Retell production report.")
    parser.add_argument("--tenant-id", default=None, help="Optional tenant ID to filter the report.")
    parser.add_argument("--days", type=int, default=7, help="Reporting window in days.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ensure_harness_src()
    from voice.services.production_report import build_voice_production_report

    report = build_voice_production_report(tenant_id=args.tenant_id, days=args.days)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

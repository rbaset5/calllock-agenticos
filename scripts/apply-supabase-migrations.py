#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install it into the local virtualenv first.")
        return 1

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 1

    migration_dir = REPO_ROOT / "supabase" / "migrations"
    seed_path = REPO_ROOT / "supabase" / "seed.sql"
    migration_files = sorted(migration_dir.glob("*.sql"))

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for migration in migration_files:
                print(f"Applying {migration.name}")
                cur.execute(migration.read_text())
            print(f"Applying {seed_path.name}")
            cur.execute(seed_path.read_text())

    print("Migrations and seed applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

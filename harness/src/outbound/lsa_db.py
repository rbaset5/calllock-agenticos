"""SQLite schema and helpers for LSA discovery."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "data" / "lsa_discovery.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash TEXT UNIQUE NOT NULL,
    town TEXT NOT NULL,
    state TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    result_count INTEGER,
    raw_response TEXT,
    error_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS place_ids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    data_id TEXT,
    lookup_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lsa_businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    town TEXT,
    state TEXT,
    rating REAL,
    review_count INTEGER,
    years_in_business INTEGER,
    service_area TEXT,
    google_guaranteed INTEGER DEFAULT 1,
    lsa_badge TEXT,
    leads_db_match INTEGER DEFAULT 0,
    source TEXT DEFAULT 'lsa_discovery',
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phone)
);
"""


def init_db(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def query_completed(conn: sqlite3.Connection, query_hash: str) -> bool:
    row = conn.execute(
        "SELECT status FROM queries WHERE query_hash = ?", (query_hash,)
    ).fetchone()
    return row is not None and row["status"] == "success"


def save_query(conn: sqlite3.Connection, query_hash: str, town: str, state: str,
               status: str, result_count: int = 0, raw_response: str = "",
               error_text: str = ""):
    conn.execute(
        """INSERT INTO queries (query_hash, town, state, status, result_count,
           raw_response, error_text, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(query_hash) DO UPDATE SET
             status=excluded.status, result_count=excluded.result_count,
             raw_response=excluded.raw_response, error_text=excluded.error_text,
             completed_at=excluded.completed_at""",
        (query_hash, town, state, status, result_count, raw_response, error_text),
    )
    conn.commit()


def upsert_business(conn: sqlite3.Connection, biz: dict):
    conn.execute(
        """INSERT INTO lsa_businesses
           (business_name, phone, address, town, state, rating, review_count,
            years_in_business, service_area, google_guaranteed, lsa_badge,
            leads_db_match, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(phone) DO UPDATE SET
             google_guaranteed=1,
             lsa_badge=COALESCE(excluded.lsa_badge, lsa_businesses.lsa_badge),
             leads_db_match=MAX(excluded.leads_db_match, lsa_businesses.leads_db_match)""",
        (
            biz["business_name"], biz["phone"], biz.get("address"),
            biz["town"], biz["state"], biz.get("rating"), biz.get("review_count"),
            biz.get("years_in_business"), biz.get("service_area"),
            1, biz.get("lsa_badge"),
            biz.get("leads_db_match", 0), "lsa_discovery",
        ),
    )
    conn.commit()


def get_place_id(conn: sqlite3.Connection, phone: str) -> str | None:
    """Return cached data_id for a phone, or None if not cached."""
    row = conn.execute(
        "SELECT data_id FROM place_ids WHERE phone = ? AND lookup_status = 'success'",
        (phone,),
    ).fetchone()
    return row["data_id"] if row else None


def save_place_id(conn: sqlite3.Connection, phone: str, data_id: str | None,
                  status: str = "success"):
    conn.execute(
        """INSERT INTO place_ids (phone, data_id, lookup_status)
           VALUES (?, ?, ?)
           ON CONFLICT(phone) DO UPDATE SET
             data_id=excluded.data_id, lookup_status=excluded.lookup_status""",
        (phone, data_id, status),
    )
    conn.commit()


def export_csv(conn: sqlite3.Connection, output_path: str):
    import csv
    rows = conn.execute(
        """SELECT business_name, phone, town, state, rating, review_count,
                  years_in_business, service_area, google_guaranteed,
                  leads_db_match, source
           FROM lsa_businesses
           WHERE phone IS NOT NULL
           ORDER BY review_count ASC"""
    ).fetchall()
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "business_name", "phone", "town", "state", "rating", "review_count",
            "years_in_business", "service_area", "google_guaranteed",
            "leads_db_match", "source",
        ])
        for row in rows:
            writer.writerow(list(row))
    return len(rows)

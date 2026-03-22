from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


ZIP_RE = re.compile(r"\b\d{5}\b")
DATA_DIR = Path(__file__).resolve().parent / "data"


def extract_zip(address: str) -> str | None:
    match = ZIP_RE.search(address or "")
    return match.group(0) if match else None


@lru_cache(maxsize=1)
def _zip_timezones() -> dict[str, str]:
    return json.loads((DATA_DIR / "zip_timezones.json").read_text())


@lru_cache(maxsize=1)
def _zip_metros() -> dict[str, str]:
    return json.loads((DATA_DIR / "zip_metros.json").read_text())


def zip_to_timezone(zip_code: str) -> str | None:
    if not zip_code:
        return None
    return _zip_timezones().get(zip_code)


def zip_to_metro(zip_code: str, configured_metros: list[str]) -> str | None:
    if not zip_code:
        return None
    metro = _zip_metros().get(zip_code)
    if metro is None:
        return None
    if not configured_metros:
        return metro
    allowed = {item.strip().lower() for item in configured_metros if item.strip()}
    return metro if metro.lower() in allowed else None

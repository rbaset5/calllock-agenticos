from __future__ import annotations

from db.repository import acquire_lock, heartbeat_lock, release_lock


def lock_surface(mutation_surface: str, ttl_seconds: int) -> dict:
    return acquire_lock({"mutation_surface": mutation_surface, "ttl_seconds": ttl_seconds})


def refresh_lock(mutation_surface: str, ttl_seconds: int) -> dict:
    return heartbeat_lock(mutation_surface, ttl_seconds)


def unlock_surface(mutation_surface: str) -> None:
    release_lock(mutation_surface)

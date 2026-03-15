from __future__ import annotations

from typing import Any


class InMemoryRedisClient:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value


def build_cache_client() -> InMemoryRedisClient:
    return InMemoryRedisClient()

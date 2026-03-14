from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from harness.server import app


@pytest.fixture
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "growth-secret")
    return {"Authorization": "Bearer growth-secret"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

from __future__ import annotations

import pytest

from db.local_repository import reset_local_state


@pytest.fixture(autouse=True)
def _reset_local_state() -> None:
    reset_local_state()

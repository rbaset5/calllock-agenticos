from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from harness.concurrency import check_agent_available, check_department_capacity


class FakeSupabaseQuery:
    def __init__(self, client: "FakeSupabaseClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: list[tuple[str, str, Any]] = []
        self.sort_field: str | None = None
        self.sort_desc = False

    def select(self, _columns: str = "*") -> "FakeSupabaseQuery":
        return self

    def eq(self, field: str, value: Any) -> "FakeSupabaseQuery":
        self.filters.append((field, "eq", value))
        return self

    def neq(self, field: str, value: Any) -> "FakeSupabaseQuery":
        self.filters.append((field, "neq", value))
        return self

    def order(self, field: str, desc: bool = False) -> "FakeSupabaseQuery":
        self.sort_field = field
        self.sort_desc = desc
        return self

    def execute(self) -> SimpleNamespace:
        rows = [dict(row) for row in self.client.tables.get(self.table_name, [])]
        for field, operator, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif operator == "neq":
                rows = [row for row in rows if row.get(field) != value]
        if self.sort_field:
            rows.sort(key=lambda row: row.get(self.sort_field) or "", reverse=self.sort_desc)
        return SimpleNamespace(data=rows)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.tables = tables or {}

    def table(self, table_name: str) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, table_name)


def test_agent_available_when_idle() -> None:
    client = FakeSupabaseClient(
        {
            "agent_office_state": [
                {"agent_id": "eng-ai-voice", "current_state": "idle", "updated_at": "2026-03-18T10:00:00Z"},
            ]
        }
    )

    assert check_agent_available("eng-ai-voice", client) is True


def test_agent_unavailable_when_executing() -> None:
    client = FakeSupabaseClient(
        {
            "agent_office_state": [
                {"agent_id": "eng-ai-voice", "current_state": "execution", "updated_at": "2026-03-18T10:00:00Z"},
            ]
        }
    )

    assert check_agent_available("eng-ai-voice", client) is False


def test_department_capacity_under_limit() -> None:
    client = FakeSupabaseClient(
        {
            "agent_office_state": [
                {"department": "engineering", "current_state": "execution", "updated_at": "2026-03-18T10:00:00Z"},
                {"department": "engineering", "current_state": "verification", "updated_at": "2026-03-18T10:01:00Z"},
                {"department": "engineering", "current_state": "idle", "updated_at": "2026-03-18T10:02:00Z"},
            ]
        }
    )

    assert check_department_capacity("engineering", client) == 2


def test_department_capacity_at_limit() -> None:
    client = FakeSupabaseClient(
        {
            "agent_office_state": [
                {"department": "engineering", "current_state": "execution", "updated_at": "2026-03-18T10:00:00Z"},
                {"department": "engineering", "current_state": "verification", "updated_at": "2026-03-18T10:01:00Z"},
                {"department": "engineering", "current_state": "context_assembly", "updated_at": "2026-03-18T10:02:00Z"},
            ]
        }
    )

    assert check_department_capacity("engineering", client) == 3

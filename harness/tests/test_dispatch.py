from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from harness.dispatch import AGENT_DISPATCH_EVENT, RunTaskRequest, dispatch_job_requests


class FakeSupabaseQuery:
    def __init__(self, client: "FakeSupabaseClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.mode = "select"
        self.payload: Any = None
        self.filters: list[tuple[str, str, Any]] = []
        self.sort_field: str | None = None
        self.sort_desc = False
        self.limit_count: int | None = None

    def select(self, _columns: str = "*") -> "FakeSupabaseQuery":
        self.mode = "select"
        return self

    def insert(self, payload: Any) -> "FakeSupabaseQuery":
        self.mode = "insert"
        self.payload = payload
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

    def limit(self, count: int) -> "FakeSupabaseQuery":
        self.limit_count = count
        return self

    def execute(self) -> SimpleNamespace:
        if self.mode == "insert":
            rows = self.client.tables.setdefault(self.table_name, [])
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted: list[dict[str, Any]] = []
            for payload in payloads:
                row = dict(payload)
                row.setdefault("id", f"{self.table_name}-{len(rows) + 1}")
                rows.append(row)
                inserted.append(row)
            return SimpleNamespace(data=inserted)

        rows = [dict(row) for row in self.client.tables.get(self.table_name, [])]
        for field, operator, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif operator == "neq":
                rows = [row for row in rows if row.get(field) != value]
        if self.sort_field:
            rows.sort(key=lambda row: row.get(self.sort_field) or "", reverse=self.sort_desc)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return SimpleNamespace(data=rows)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.tables = tables or {}

    def table(self, table_name: str) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, table_name)


class FakeInngestClient:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def send_event(self, name: str, data: dict[str, Any]) -> None:
        self.events.append((name, data))


def test_dispatch_valid_requests() -> None:
    supabase = FakeSupabaseClient({"command_audit_log": [], "agent_office_state": []})
    inngest = FakeInngestClient()

    result = dispatch_job_requests(
        [
            RunTaskRequest(
                worker_id="eng-ai-voice",
                task_type="voice-health-check",
                task_context={"date": "2026-03-18"},
                idempotency_key="dispatch-1",
            ),
            RunTaskRequest(
                worker_id="eng-product-qa",
                task_type="seam-audit",
                task_context={"field": "caller_type"},
                idempotency_key="dispatch-2",
            ),
        ],
        origin_worker_id="eng-vp",
        tenant_id="tenant-alpha",
        inngest_client=inngest,
        supabase_client=supabase,
    )

    assert result.dispatched == ["eng-ai-voice", "eng-product-qa"]
    assert result.queued == []
    assert result.blocked == []
    assert [name for name, _data in inngest.events] == [AGENT_DISPATCH_EVENT, AGENT_DISPATCH_EVENT]
    assert len(supabase.tables["command_audit_log"]) == 2


def test_dispatch_cycle_detection() -> None:
    supabase = FakeSupabaseClient({"command_audit_log": [], "agent_office_state": []})
    inngest = FakeInngestClient()

    with pytest.raises(ValueError, match="Cycle detected"):
        dispatch_job_requests(
            [
                RunTaskRequest(
                    worker_id="eng-vp",
                    task_type="department-sweep",
                    task_context={},
                    idempotency_key="dispatch-self",
                )
            ],
            origin_worker_id="eng-vp",
            tenant_id="tenant-alpha",
            inngest_client=inngest,
            supabase_client=supabase,
        )


def test_dispatch_concurrency_cap() -> None:
    supabase = FakeSupabaseClient(
        {
            "command_audit_log": [],
            "agent_office_state": [
                {
                    "tenant_id": "tenant-alpha",
                    "agent_id": "eng-ai-voice",
                    "department": "engineering",
                    "current_state": "execution",
                    "updated_at": "2026-03-18T10:00:00Z",
                }
            ],
        }
    )
    inngest = FakeInngestClient()

    result = dispatch_job_requests(
        [
            RunTaskRequest(
                worker_id="eng-ai-voice",
                task_type="investigate-call",
                task_context={"call_id": "4821"},
                idempotency_key="dispatch-busy",
            )
        ],
        origin_worker_id="eng-vp",
        tenant_id="tenant-alpha",
        inngest_client=inngest,
        supabase_client=supabase,
    )

    assert result.dispatched == []
    assert result.queued == ["eng-ai-voice"]
    assert result.blocked == []
    assert inngest.events == []


def test_dispatch_department_cap() -> None:
    supabase = FakeSupabaseClient(
        {
            "command_audit_log": [],
            "agent_office_state": [
                {
                    "tenant_id": "tenant-alpha",
                    "agent_id": "eng-ai-voice",
                    "department": "engineering",
                    "current_state": "execution",
                    "updated_at": "2026-03-18T10:00:00Z",
                },
                {
                    "tenant_id": "tenant-alpha",
                    "agent_id": "eng-fullstack",
                    "department": "engineering",
                    "current_state": "verification",
                    "updated_at": "2026-03-18T10:01:00Z",
                },
                {
                    "tenant_id": "tenant-alpha",
                    "agent_id": "eng-vp",
                    "department": "engineering",
                    "current_state": "context_assembly",
                    "updated_at": "2026-03-18T10:02:00Z",
                },
            ],
        }
    )
    inngest = FakeInngestClient()

    result = dispatch_job_requests(
        [
            RunTaskRequest(
                worker_id="eng-product-qa",
                task_type="validate-pr",
                task_context={"pr_number": 17},
                idempotency_key="dispatch-cap",
            )
        ],
        origin_worker_id="eng-vp",
        tenant_id="tenant-alpha",
        inngest_client=inngest,
        supabase_client=supabase,
    )

    assert result.dispatched == []
    assert result.queued == ["eng-product-qa"]
    assert result.blocked == []
    assert inngest.events == []


def test_dispatch_requires_approval() -> None:
    supabase = FakeSupabaseClient({"command_audit_log": [], "agent_office_state": [], "quest_log": []})
    inngest = FakeInngestClient()

    result = dispatch_job_requests(
        [
            RunTaskRequest(
                worker_id="eng-ai-voice",
                task_type="deploy-retell-config",
                task_context={"llm_id": "retell-1"},
                idempotency_key="dispatch-approval",
                requires_approval=True,
                priority="high",
            )
        ],
        origin_worker_id="eng-vp",
        tenant_id="tenant-alpha",
        inngest_client=inngest,
        supabase_client=supabase,
    )

    assert result.dispatched == []
    assert result.queued == []
    assert result.blocked == ["eng-ai-voice"]
    assert len(supabase.tables["quest_log"]) == 1
    assert supabase.tables["quest_log"][0]["status"] == "pending"
    assert inngest.events == []


def test_dispatch_idempotency() -> None:
    supabase = FakeSupabaseClient(
        {
            "agent_office_state": [],
            "command_audit_log": [
                {
                    "tenant_id": "tenant-alpha",
                    "action_type": "agent.dispatch",
                    "payload": {"idempotency_key": "dispatch-dup"},
                    "created_at": "2026-03-18T10:00:00Z",
                }
            ],
        }
    )
    inngest = FakeInngestClient()

    result = dispatch_job_requests(
        [
            RunTaskRequest(
                worker_id="eng-ai-voice",
                task_type="voice-health-check",
                task_context={},
                idempotency_key="dispatch-dup",
            )
        ],
        origin_worker_id="eng-vp",
        tenant_id="tenant-alpha",
        inngest_client=inngest,
        supabase_client=supabase,
    )

    assert result.dispatched == []
    assert result.queued == []
    assert result.blocked == []
    assert inngest.events == []
    assert supabase.tables["command_audit_log"][-1]["action_type"] == "agent.dispatch.skipped"


def test_dispatch_unknown_worker() -> None:
    supabase = FakeSupabaseClient({"command_audit_log": [], "agent_office_state": []})
    inngest = FakeInngestClient()

    with pytest.raises(ValueError, match="Unknown worker_id"):
        dispatch_job_requests(
            [
                RunTaskRequest(
                    worker_id="totally-unknown-agent",
                    task_type="mystery-task",
                    task_context={},
                    idempotency_key="dispatch-unknown",
                )
            ],
            origin_worker_id="eng-vp",
            tenant_id="tenant-alpha",
            inngest_client=inngest,
            supabase_client=supabase,
        )

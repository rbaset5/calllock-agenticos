from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from uuid import uuid4

import httpx

from harness.concurrency import (
    _check_agent_available_for_tenant,
    _check_department_capacity_for_tenant,
)
from knowledge.pack_loader import load_json_yaml


AGENT_DISPATCH_EVENT = "calllock/agent.dispatch"
DEPARTMENT_CONCURRENCY_CAP = 3
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SPECS_DIR = REPO_ROOT / "knowledge" / "worker-specs"


@dataclass
class RunTaskRequest:
    worker_id: str
    task_type: str
    task_context: dict[str, Any]
    idempotency_key: str
    priority: str = "medium"
    requires_approval: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RunTaskRequest":
        worker_id = str(payload.get("worker_id", "")).strip()
        task_type = str(payload.get("task_type", "")).strip()
        idempotency_key = str(payload.get("idempotency_key", "")).strip()
        if not worker_id:
            raise ValueError("worker_id is required")
        if not task_type:
            raise ValueError("task_type is required")
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        task_context = payload.get("task_context") or {}
        if not isinstance(task_context, dict):
            raise ValueError("task_context must be a dict")
        priority = str(payload.get("priority", "medium") or "medium").strip().lower()
        if priority not in {"low", "medium", "high"}:
            raise ValueError(f"Invalid priority: {priority}")
        return cls(
            worker_id=worker_id,
            task_type=task_type,
            task_context=dict(task_context),
            idempotency_key=idempotency_key,
            priority=priority,
            requires_approval=bool(payload.get("requires_approval", False)),
        )


@dataclass
class DispatchResult:
    dispatched: list[str]
    queued: list[str]
    blocked: list[str]


class _SupabaseRestQuery:
    def __init__(self, client: "_SupabaseRestClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.columns = "*"
        self.filters: dict[str, str] = {}
        self.order_field: str | None = None
        self.order_desc = False
        self.limit_count: int | None = None
        self.payload: Any = None
        self.mode = "select"

    def select(self, columns: str = "*") -> "_SupabaseRestQuery":
        self.columns = columns
        self.mode = "select"
        return self

    def insert(self, payload: Any) -> "_SupabaseRestQuery":
        self.mode = "insert"
        self.payload = payload
        return self

    def eq(self, field: str, value: Any) -> "_SupabaseRestQuery":
        self.filters[field] = f"eq.{value}"
        return self

    def neq(self, field: str, value: Any) -> "_SupabaseRestQuery":
        self.filters[field] = f"neq.{value}"
        return self

    def order(self, field: str, desc: bool = False) -> "_SupabaseRestQuery":
        self.order_field = field
        self.order_desc = desc
        return self

    def limit(self, count: int) -> "_SupabaseRestQuery":
        self.limit_count = count
        return self

    def execute(self) -> SimpleNamespace:
        if self.mode == "insert":
            response = self.client.http_client.post(
                f"{self.client.base_url}/rest/v1/{self.table_name}",
                headers={
                    **self.client.headers,
                    "Prefer": "return=representation",
                },
                json=self.payload,
                timeout=10.0,
            )
            response.raise_for_status()
            return SimpleNamespace(data=response.json())

        params: dict[str, str] = {"select": self.columns, **self.filters}
        if self.order_field:
            params["order"] = f"{self.order_field}.{'desc' if self.order_desc else 'asc'}"
        if self.limit_count is not None:
            params["limit"] = str(self.limit_count)
        response = self.client.http_client.get(
            f"{self.client.base_url}/rest/v1/{self.table_name}",
            headers=self.client.headers,
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        return SimpleNamespace(data=response.json())


class _SupabaseRestClient:
    def __init__(self, *, base_url: str, service_role_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }
        self.http_client = httpx.Client()

    def table(self, table_name: str) -> _SupabaseRestQuery:
        return _SupabaseRestQuery(self, table_name)


class _InngestDispatchClient:
    def __init__(self, *, endpoint: str, event_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.event_key = event_key

    def send_event(self, name: str, data: dict[str, Any]) -> None:
        headers = {"Content-Type": "application/json"}
        if self.event_key:
            headers["Authorization"] = f"Bearer {self.event_key}"
        response = httpx.post(
            self.endpoint,
            json={"name": name, "data": data},
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()


def _response_data(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", result)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


@lru_cache(maxsize=1)
def _agent_registry() -> dict[str, dict[str, str | None]]:
    registry: dict[str, dict[str, str | None]] = {}
    for spec_path in sorted(WORKER_SPECS_DIR.glob("*.yaml")):
        if spec_path.name.startswith("_"):
            continue
        spec = load_json_yaml(spec_path)
        worker_id = str(spec.get("worker_id") or spec_path.stem)
        registry[worker_id] = {
            "department": str(spec.get("department") or "unknown"),
            "role": str(spec.get("role") or "worker"),
            "description": (
                spec.get("title")
                or spec.get("mission")
                or worker_id
            ),
        }
    return registry


def _default_supabase_client() -> _SupabaseRestClient:
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for dispatch")
    return _SupabaseRestClient(base_url=url, service_role_key=service_role_key)


def _default_inngest_client() -> _InngestDispatchClient:
    endpoint = os.getenv("INNGEST_EVENT_URL")
    if not endpoint:
        raise RuntimeError("INNGEST_EVENT_URL is required for dispatch")
    return _InngestDispatchClient(
        endpoint=endpoint,
        event_key=os.getenv("INNGEST_EVENT_KEY"),
    )


def _write_audit_log(
    *,
    supabase_client: Any,
    tenant_id: str,
    action_type: str,
    target_agent: str,
    payload: dict[str, Any],
) -> None:
    supabase_client.table("command_audit_log").insert(
        {
            "tenant_id": tenant_id,
            "user_id": SYSTEM_USER_ID,
            "action_type": action_type,
            "target_agent": target_agent,
            "payload": payload,
        }
    ).execute()


def _recent_dispatch_payloads(*, tenant_id: str, supabase_client: Any) -> list[dict[str, Any]]:
    rows = _response_data(
        supabase_client.table("command_audit_log")
        .select("action_type,payload,created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    payloads: list[dict[str, Any]] = []
    for row in rows:
        if not str(row.get("action_type", "")).startswith("agent.dispatch"):
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _has_recent_idempotency_key(*, tenant_id: str, idempotency_key: str, supabase_client: Any) -> bool:
    recent_payloads = _recent_dispatch_payloads(
        tenant_id=tenant_id,
        supabase_client=supabase_client,
    )
    return any(payload.get("idempotency_key") == idempotency_key for payload in recent_payloads)


def _create_quest(
    *,
    tenant_id: str,
    request: RunTaskRequest,
    target_department: str,
    supabase_client: Any,
) -> None:
    supabase_client.table("quest_log").insert(
        {
            "tenant_id": tenant_id,
            "agent_id": request.worker_id,
            "department": target_department,
            "call_id": request.task_context.get("call_id"),
            "rule_violated": "dispatch_requires_approval",
            "summary": f"Approval required before dispatching '{request.task_type}' to {request.worker_id}",
            "options": [
                {"label": "Approve", "value": "approve"},
                {"label": "Deny", "value": "deny"},
                {"label": "Escalate", "value": "escalate"},
            ],
            "urgency": request.priority,
            "status": "pending",
        }
    ).execute()


def dispatch_job_requests(
    requests: list[RunTaskRequest],
    origin_worker_id: str,
    tenant_id: str,
    inngest_client: Any,
    supabase_client: Any,
) -> DispatchResult:
    """
    Takes a list of RunTaskRequests from a director and:
    1. Validates each worker_id exists in the agent registry
    2. Checks concurrency: max 1 run per agent, max 3 per department
    3. If requires_approval: creates a quest_log entry instead of dispatching
    4. Otherwise: fires calllock/agent.dispatch Inngest event per request
    5. Logs each dispatch to command_audit_log
    6. Returns DispatchResult summary

    Cycle detection: reject if any request targets origin_worker_id.
    Idempotency: skip if idempotency_key already exists in recent dispatches.
    """
    supabase = supabase_client or _default_supabase_client()
    inngest = inngest_client or _default_inngest_client()
    registry = _agent_registry()
    dispatched: list[str] = []
    queued: list[str] = []
    blocked: list[str] = []
    seen_in_batch: set[str] = set()

    for raw_request in requests:
        request = raw_request if isinstance(raw_request, RunTaskRequest) else RunTaskRequest.from_mapping(raw_request)
        if request.worker_id == origin_worker_id:
            raise ValueError(f"Cycle detected: {origin_worker_id} cannot dispatch to itself")

        target_agent = registry.get(request.worker_id)
        if target_agent is None:
            raise ValueError(f"Unknown worker_id: {request.worker_id}")

        if request.idempotency_key in seen_in_batch or _has_recent_idempotency_key(
            tenant_id=tenant_id,
            idempotency_key=request.idempotency_key,
            supabase_client=supabase,
        ):
            _write_audit_log(
                supabase_client=supabase,
                tenant_id=tenant_id,
                action_type="agent.dispatch.skipped",
                target_agent=request.worker_id,
                payload={
                    "worker_id": request.worker_id,
                    "task_type": request.task_type,
                    "idempotency_key": request.idempotency_key,
                    "priority": request.priority,
                    "reason": "idempotent",
                },
            )
            continue

        seen_in_batch.add(request.idempotency_key)
        department = str(target_agent.get("department") or "unknown")
        role = str(target_agent.get("role") or "worker")
        description = target_agent.get("description")
        audit_payload = {
            "worker_id": request.worker_id,
            "origin_worker_id": origin_worker_id,
            "task_type": request.task_type,
            "task_context": request.task_context,
            "idempotency_key": request.idempotency_key,
            "priority": request.priority,
            "requires_approval": request.requires_approval,
            "department": department,
            "role": role,
        }

        if request.requires_approval:
            _create_quest(
                tenant_id=tenant_id,
                request=request,
                target_department=department,
                supabase_client=supabase,
            )
            blocked.append(request.worker_id)
            _write_audit_log(
                supabase_client=supabase,
                tenant_id=tenant_id,
                action_type="agent.dispatch.blocked",
                target_agent=request.worker_id,
                payload={**audit_payload, "reason": "approval_required"},
            )
            continue

        if not _check_agent_available_for_tenant(
            tenant_id=tenant_id,
            agent_id=request.worker_id,
            supabase_client=supabase,
        ):
            queued.append(request.worker_id)
            _write_audit_log(
                supabase_client=supabase,
                tenant_id=tenant_id,
                action_type="agent.dispatch.queued",
                target_agent=request.worker_id,
                payload={**audit_payload, "reason": "agent_busy"},
            )
            continue

        if (
            _check_department_capacity_for_tenant(
                tenant_id=tenant_id,
                department=department,
                supabase_client=supabase,
            )
            >= DEPARTMENT_CONCURRENCY_CAP
        ):
            queued.append(request.worker_id)
            _write_audit_log(
                supabase_client=supabase,
                tenant_id=tenant_id,
                action_type="agent.dispatch.queued",
                target_agent=request.worker_id,
                payload={**audit_payload, "reason": "department_capacity"},
            )
            continue

        inngest.send_event(
            AGENT_DISPATCH_EVENT,
            {
                "worker_id": request.worker_id,
                "tenant_id": tenant_id,
                "origin_worker_id": origin_worker_id,
                "task_type": request.task_type,
                "task_context": request.task_context,
                "idempotency_key": request.idempotency_key,
                "priority": request.priority,
                "requires_approval": request.requires_approval,
                "department": department,
                "role": role,
                "description": description,
            },
        )
        dispatched.append(request.worker_id)
        _write_audit_log(
            supabase_client=supabase,
            tenant_id=tenant_id,
            action_type="agent.dispatch",
            target_agent=request.worker_id,
            payload=audit_payload,
        )

    return DispatchResult(
        dispatched=dispatched,
        queued=queued,
        blocked=blocked,
    )

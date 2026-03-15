from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]

from cache.redis_client import build_cache_client
from db.repository import get_compliance_rules, get_tenant, get_tenant_config, using_supabase
from harness.graphs.supervisor import run_supervisor
from harness.models import HarnessEventEnvelope, ProcessCallRequest, ProcessCallResponse
from knowledge.file_reader import load_markdown
from knowledge.pack_loader import load_json_yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def load_worker_spec(worker_id: str) -> dict[str, Any]:
    spec_path = REPO_ROOT / "knowledge" / "worker-specs" / f"{worker_id}.yaml"
    return load_json_yaml(spec_path)


def build_task_payload(request: ProcessCallRequest, tenant: dict[str, Any]) -> dict[str, Any]:
    tenant_config = request.tenant_config or get_tenant_config(request.tenant_id)
    industry_pack_id = tenant_config.get("industry_pack_id") or tenant["industry_pack_id"]
    industry_pack = load_json_yaml(REPO_ROOT / "knowledge" / "industry-packs" / industry_pack_id / "pack.yaml")
    knowledge_node = load_markdown(REPO_ROOT / "knowledge" / "product" / "architecture.md")
    return {
        "worker_spec": load_worker_spec(request.worker_id),
        "tenant_config": tenant_config,
        "industry_pack": industry_pack,
        "knowledge_nodes": [{"summary": knowledge_node["body"]}],
        "problem_description": request.problem_description,
        "transcript": request.transcript,
        "feature_flags": request.feature_flags,
        "compliance_rules": request.compliance_rules or get_compliance_rules(request.tenant_id),
        "environment_allowed_tools": request.environment_allowed_tools,
    }


def health_dependencies() -> dict[str, Any]:
    cache = build_cache_client()
    redis_ok = cache.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": {"ok": redis_ok},
        "litellm": {"configured": bool(os.getenv("LITELLM_BASE_URL"))},
        "supabase": {"configured": using_supabase()},
        "langsmith": {"configured": bool(os.getenv("LANGSMITH_API_KEY"))},
        "event_secret": {"configured": bool(os.getenv("HARNESS_EVENT_SECRET"))},
    }


def validate_event_auth(request: Request) -> None:
    expected = os.getenv("HARNESS_EVENT_SECRET")
    if not expected:
        return
    authorization = request.headers.get("authorization", "")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid event secret")


if FastAPI:
    app = FastAPI(title="CallLock Harness")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return health_dependencies()

    @app.post("/process-call", response_model=ProcessCallResponse)
    def process_call(request: ProcessCallRequest) -> ProcessCallResponse:
        run_id = f"run-{uuid4()}"
        tenant = get_tenant(request.tenant_id)
        result = run_supervisor(
            {
                "tenant_id": tenant["id"],
                "run_id": run_id,
                "worker_id": request.worker_id,
                "task": build_task_payload(request, tenant),
            }
        )
        return ProcessCallResponse(
            run_id=run_id,
            policy_verdict=result["policy_decision"]["verdict"],
            verification_passed=result["verification"]["passed"],
            output=result["worker_output"],
        )

    @app.post("/events/process-call", response_model=ProcessCallResponse)
    def process_call_event(event: HarnessEventEnvelope, request: Request) -> ProcessCallResponse:
        validate_event_auth(request)
        if event.name != "harness/process-call":
            raise HTTPException(status_code=400, detail=f"Unsupported event name: {event.name}")
        return process_call(event.data)

    # --- Metrics snapshot endpoint ---

    from harness.metrics import VALID_CATEGORIES

    VALID_GROUP_BY = frozenset(["event_name", "worker_id", "tenant_id"])

    def _error_response(status_code: int, error: str, detail: str) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"error": error, "detail": detail})

    def _check_metrics_auth(request: Request) -> JSONResponse | None:
        expected = os.getenv("HARNESS_EVENT_SECRET")
        if not expected:
            return None
        authorization = request.headers.get("authorization", "")
        if authorization != f"Bearer {expected}":
            return _error_response(401, "auth_failed", "Invalid event secret")
        return None

    def _query_metric_snapshot(
        *,
        category: str,
        tenant_id: str | None,
        cutoff: datetime,
        group_by: str | None,
    ) -> dict[str, Any] | JSONResponse:
        """Query metric_events via single RPC call for correct transaction scope."""
        if not using_supabase():
            return {"total_count": 0, "groups": [], "oldest_event": None, "newest_event": None}

        import httpx as _httpx
        from db.supabase_repository import _base_url, _headers

        try:
            response = _httpx.post(
                f"{_base_url()}/rpc/get_metric_snapshot",
                headers=_headers(),
                json={
                    "p_category": category,
                    "p_tenant_id": tenant_id,
                    "p_cutoff": cutoff.isoformat(),
                    "p_group_by": group_by,
                },
                timeout=10.0,
            )
            response.raise_for_status()
        except (_httpx.TimeoutException, _httpx.HTTPStatusError, _httpx.ConnectError):
            return _error_response(503, "upstream_unavailable", "Metrics store temporarily unavailable")

        return response.json()

    @app.get("/metrics/snapshot")
    def metrics_snapshot(
        request: Request,
        category: str | None = None,
        tenant_id: str | None = None,
        window: int = 60,
        group_by: str | None = None,
    ):
        auth_error = _check_metrics_auth(request)
        if auth_error:
            return auth_error

        if not category:
            return _error_response(400, "missing_category", "category is required")
        if category not in VALID_CATEGORIES:
            return _error_response(400, "invalid_category", f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
        if group_by and group_by not in VALID_GROUP_BY:
            return _error_response(400, "invalid_group_by", f"group_by must be one of: {', '.join(sorted(VALID_GROUP_BY))}")
        if window < 1 or window > 1440:
            return _error_response(400, "invalid_window", "window must be between 1 and 1440 minutes")

        applied_filters: dict[str, Any] = {}
        if tenant_id:
            applied_filters["tenant_id"] = tenant_id
        if group_by:
            applied_filters["group_by"] = group_by

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)

        result = _query_metric_snapshot(
            category=category,
            tenant_id=tenant_id,
            cutoff=cutoff,
            group_by=group_by,
        )

        if isinstance(result, JSONResponse):
            return result

        return {
            "category": category,
            "window_minutes": window,
            "applied_filters": applied_filters,
            **result,
        }

else:  # pragma: no cover
    app = None

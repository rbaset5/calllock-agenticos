from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]

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

else:  # pragma: no cover
    app = None

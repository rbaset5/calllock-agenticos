from __future__ import annotations

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
    stream=__import__('sys').stderr,
)

import os
from datetime import date, datetime, timedelta, timezone
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
from db import repository as db_repository
from db.repository import (
    create_approval_request,
    get_compliance_rules,
    get_job,
    get_tenant,
    get_tenant_config,
    list_incidents,
    list_alerts,
    list_audit_logs,
    list_artifacts,
    list_jobs,
    list_kill_switches,
    update_artifact_lifecycle,
    update_alert,
    update_alert_and_sync_incident,
    update_incident_runbook_assignment,
    update_incident_runbook_progress,
    update_incident_workflow,
    update_job_status,
    using_supabase,
)
from growth.batch.growth_advisor import run_growth_advisor_batch
from growth.engine.allocator import allocate_experiment
from growth.events.belief_handler import handle_belief_event
from growth.events.lifecycle_handler import handle_lifecycle_transition
from growth.events.touchpoint_handler import handle_touchpoint
from growth.gate.health_gate import check_health_gate
from growth.memory import repository as growth_repository
from harness.alerts.evaluator import evaluate_alerts
from harness.alerts.escalation import auto_escalate_alerts
from harness.alerts.recovery import auto_resolve_recovered_alerts
from harness.alerts.thresholds import resolve_thresholds
from harness.approval_resume import continue_approved_request
from harness.approvals import approvals_for_api, resolve_approval_request
from harness.audit import log_audit_event
from harness.cockpit import cockpit_overview, cockpit_scheduler_view
from harness.content_pipeline.pipeline import process_customer_content
from harness.control_plane.kill_switches import upsert_kill_switch
from harness.evals.runner import list_eval_runs_for_api, run_eval_suite
from harness.graphs.supervisor import run_supervisor
from harness.improvement.experiments import run_experiment
from harness.incident_notifications import notify_incident
from harness.incident_reminders import send_incident_reminders
from harness.incident_routing import resolve_assignee
from harness.jobs.dispatch import dispatch_job_requests as dispatch_async_job_requests
from harness.incident_runbooks import (
    get_runbook_step,
    pending_runbook_steps,
    workflow_requires_completed_runbook,
)
from harness.incidents import record_incident_from_alert
from harness.incident_runbooks import workflow_requires_approval
from harness.models import (
    AlertDecisionRequest,
    AlertEscalationRequest,
    AlertEvaluationRequest,
    AlertRecoveryRequest,
    ApprovalDecisionRequest,
    ArtifactLifecycleRequest,
    ContentPipelineRequest,
    DueTenantScheduleRequest,
    EvalRunRequest,
    GrowthAdvisorWeeklyRequest,
    GrowthAllocationResponse,
    GrowthBeliefInferenceRequest,
    GrowthGateCheckRequest,
    GrowthGateCheckResponse,
    GrowthLifecycleRequest,
    GrowthTouchpointRequest,
    InboundPollRequest,
    InboundPollResponse,
    InboundProcessRequest,
    InboundProcessResponse,
    HarnessJobCompleteEvent,
    HarnessProcessCallEvent,
    ImprovementExperimentRequest,
    IncidentWorkflowRequest,
    IncidentReminderRequest,
    IncidentRunbookProgressRequest,
    IncidentRunbookAssignmentRequest,
    KillSwitchRequest,
    OnboardTenantRequest,
    ProcessCallRequest,
    ProcessCallResponse,
    RetentionRunRequest,
    RecoveryReplayRequest,
    ScheduleClaimRequest,
    ScheduleFinalizeRequest,
    ScheduleHeartbeatRequest,
    ScheduleOverrideRequest,
    ScheduleSweepRequest,
    WedgeFitnessSnapshotResponse,
)
from harness.jobs.dispatch import dispatch_job_requests as dispatch_async_jobs
from harness.resilience.recovery_journal import list_recovery_entries
from harness.resilience.replayer import replay_recovery_entry
from harness.scheduling import (
    claim_due_tenants,
    due_tenants,
    finalize_scheduler_claim,
    heartbeat_scheduler_claim,
    list_scheduler_backlog_entries,
    override_scheduler_claim,
    reconcile_scheduler_backlog,
    sweep_stale_scheduler_claims,
)
from harness.retention import run_retention_pass
from harness.workflows.onboarding import onboard_tenant
from knowledge.file_reader import load_markdown
from knowledge.pack_loader import load_json_yaml
from observability.langsmith_tracer import submit_trace


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
        "task_context": request.task_context,
        "memory": request.memory,
        "history": request.history,
        "context_budget": request.context_budget,
        "feature_flags": request.feature_flags,
        "compliance_rules": request.compliance_rules or get_compliance_rules(request.tenant_id),
        "environment_allowed_tools": request.environment_allowed_tools,
    }


def _check_external_connectivity(url: str, timeout: float = 3.0) -> dict[str, Any]:
    """HEAD-request connectivity check for an external service."""
    try:
        import httpx as _httpx
        resp = _httpx.head(url, timeout=timeout, follow_redirects=True)
        return {"reachable": True, "status": resp.status_code}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)[:120]}


def health_dependencies() -> dict[str, Any]:
    cache = build_cache_client()
    redis_ok = cache.ping()

    calcom = _check_external_connectivity("https://api.cal.com")
    twilio = _check_external_connectivity("https://api.twilio.com")

    all_reachable = calcom.get("reachable", False) and twilio.get("reachable", False)
    base_status = "ok" if redis_ok else "degraded"
    status = base_status if all_reachable else "degraded"

    return {
        "status": status,
        "redis": {"ok": redis_ok},
        "litellm": {"configured": bool(os.getenv("LITELLM_BASE_URL"))},
        "supabase": {"configured": using_supabase()},
        "langsmith": {"configured": bool(os.getenv("LANGSMITH_API_KEY"))},
        "event_secret": {"configured": bool(os.getenv("HARNESS_EVENT_SECRET"))},
        "calcom": calcom,
        "twilio": twilio,
    }


def validate_event_auth(request: Request) -> None:
    expected = os.getenv("HARNESS_EVENT_SECRET")
    if not expected:
        return
    authorization = request.headers.get("authorization", "")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid event secret")


def actor_id_for(request: Request | None, fallback: str = "system") -> str:
    if request is None:
        return fallback
    return request.headers.get("x-actor-id") or fallback


def _tenant_lookup_values(tenant_id: str | None) -> list[str]:
    if not tenant_id:
        return []
    values = [tenant_id]
    try:
        tenant = get_tenant(tenant_id)
    except Exception:
        return values
    for candidate in (tenant.get("id"), tenant.get("slug")):
        if isinstance(candidate, str) and candidate and candidate not in values:
            values.append(candidate)
    return values


def _canonical_tenant_id(identifier: str) -> str:
    return get_tenant(identifier)["id"]


def _merge_records_by_id(*record_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for records in record_lists:
        for record in records:
            record_id = record.get("id")
            if isinstance(record_id, str):
                merged[record_id] = record
    return list(merged.values())


def _get_incident_or_404(incident_id: str) -> dict[str, Any]:
    for incident in list_incidents():
        if incident["id"] == incident_id:
            return incident
    raise HTTPException(status_code=404, detail=f"Unknown incident: {incident_id}")


if FastAPI:
    app = FastAPI(title="CallLock Harness")

    from voice.router import voice_router
    from voice.post_call_router import post_call_router
    from voice.booking_router import booking_router

    app.include_router(voice_router, prefix="/webhook/retell")
    app.include_router(post_call_router, prefix="/webhook/retell")
    app.include_router(booking_router, prefix="/api/bookings")

    # Start Discord Sales Assistant bot in background thread (only if token configured)
    if os.getenv("DISCORD_BOT_TOKEN", "").strip():
        try:
            from outbound.assistant import start_bot_background
            start_bot_background()
        except Exception:
            logging.getLogger(__name__).info("Discord bot not started (missing deps)")
    else:
        logging.getLogger(__name__).info("Discord bot not started (DISCORD_BOT_TOKEN not set)")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return health_dependencies()

    # --- NDJSON streaming endpoint for real-time run status ---
    # Protocol: application/x-ndjson — one JSON object per line.
    # Inspired by Antspace deployment status streaming.
    try:
        from fastapi.responses import StreamingResponse
    except Exception:  # pragma: no cover
        StreamingResponse = None  # type: ignore[assignment]

    if StreamingResponse is not None:
        from harness.streaming import subscribe_run

        @app.get("/runs/{run_id}/stream")
        async def stream_run_status(run_id: str) -> StreamingResponse:
            return StreamingResponse(
                subscribe_run(run_id),
                media_type="application/x-ndjson",
            )

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
        async_jobs = dispatch_async_jobs(
            request.job_requests,
            tenant_id=tenant["id"],
            origin_worker_id=request.worker_id,
            origin_run_id=run_id,
        ) if request.job_requests else []
        submit_trace(
            name="process-call",
            payload={
                "tenant_id": tenant["id"],
                "worker_id": request.worker_id,
                "trace_namespace": (request.tenant_config or get_tenant_config(request.tenant_id)).get("trace_namespace", request.tenant_id),
                "inputs": {
                    "call_id": request.call_id,
                    "problem_description": request.problem_description,
                    "transcript": request.transcript,
                },
                "outputs": {
                    "policy_verdict": result["policy_decision"]["verdict"],
                    "verification": result["verification"],
                    "output": result["worker_output"],
                },
            },
        )
        return ProcessCallResponse(
            run_id=run_id,
            policy_verdict=result["policy_decision"]["verdict"],
            verification_passed=result["verification"]["passed"],
            verification_verdict=result["verification"]["verdict"],
            output=result["worker_output"],
            jobs=[*result.get("jobs", []), *async_jobs],
        )

    @app.post("/events/process-call", response_model=ProcessCallResponse)
    def process_call_event(event: HarnessProcessCallEvent, request: Request) -> ProcessCallResponse:
        validate_event_auth(request)
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

    @app.post("/events/job-complete")
    def job_complete(event: HarnessJobCompleteEvent, request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        return update_job_status(event.data.job_id, event.data.status, result=event.data.result)

    @app.post("/growth/handle-touchpoint")
    def growth_handle_touchpoint(request_model: GrowthTouchpointRequest, request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        payload = request_model.model_dump()
        payload["tenant_id"] = _canonical_tenant_id(request_model.tenant_id)
        return handle_touchpoint(payload)

    @app.post("/growth/handle-lifecycle")
    def growth_handle_lifecycle(request_model: GrowthLifecycleRequest, request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        payload = request_model.model_dump()
        payload["tenant_id"] = _canonical_tenant_id(request_model.tenant_id)
        return handle_lifecycle_transition(payload)

    @app.post("/growth/handle-belief")
    def growth_handle_belief(request_model: GrowthBeliefInferenceRequest, request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        payload = request_model.model_dump()
        payload["tenant_id"] = _canonical_tenant_id(request_model.tenant_id)
        return handle_belief_event(payload)

    @app.post("/growth/gate/check", response_model=GrowthGateCheckResponse)
    def growth_gate_check(request_model: GrowthGateCheckRequest, request: Request) -> GrowthGateCheckResponse:
        validate_event_auth(request)
        result = check_health_gate([message.model_dump() for message in request_model.messages])
        return GrowthGateCheckResponse(**result)

    @app.get("/growth/experiment/{experiment_id}/allocate", response_model=GrowthAllocationResponse)
    def growth_allocate_experiment(experiment_id: str, tenant_id: str, request: Request) -> GrowthAllocationResponse:
        validate_event_auth(request)
        canonical_tenant_id = _canonical_tenant_id(tenant_id)
        experiment = growth_repository.get_experiment_history(experiment_id)
        if experiment.get("tenant_id") != canonical_tenant_id:
            raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
        allocation = allocate_experiment(experiment)
        return GrowthAllocationResponse(
            experiment_id=allocation.experiment_id,
            chosen_arm_id=allocation.chosen_arm_id,
            scores=allocation.scores,
            mode=allocation.mode,
        )

    @app.get("/growth/metrics/wedge-fitness/{wedge_id}", response_model=WedgeFitnessSnapshotResponse)
    def growth_wedge_fitness(wedge_id: str, tenant_id: str, request: Request) -> WedgeFitnessSnapshotResponse:
        validate_event_auth(request)
        snapshot = growth_repository.get_latest_wedge_fitness_snapshot(
            tenant_id=_canonical_tenant_id(tenant_id),
            wedge=wedge_id,
        )
        if snapshot is None:
            raise HTTPException(status_code=404, detail=f"No wedge fitness snapshot found for {wedge_id}")
        return WedgeFitnessSnapshotResponse(**snapshot)

    @app.post("/growth/growth-advisor/weekly")
    def growth_advisor_weekly(request_model: GrowthAdvisorWeeklyRequest, request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        now = None
        if request_model.now_iso:
            now = datetime.fromisoformat(request_model.now_iso.replace("Z", "+00:00"))
        return run_growth_advisor_batch(
            _canonical_tenant_id(request_model.tenant_id),
            source_version=request_model.source_version,
            wedges=request_model.wedges or None,
            context=request_model.context,
            now=now,
        )

    @app.post("/inbound/poll", response_model=InboundPollResponse)
    async def inbound_poll(request_model: InboundPollRequest, request: Request) -> InboundPollResponse:
        validate_event_auth(request)
        from inbound.pipeline import run_poll

        results = await run_poll(
            tenant_id=request_model.tenant_id,
            account_ids=request_model.account_ids,
            repository=db_repository,
        )
        return InboundPollResponse(
            results=results,
            fetched=len(results),
            processed=sum(1 for result in results if result.get("action") is not None),
            errors=sum(1 for result in results if result.get("action") is None),
        )

    @app.post("/inbound/process", response_model=InboundProcessResponse)
    async def inbound_process(request_model: InboundProcessRequest, request: Request) -> InboundProcessResponse:
        validate_event_auth(request)
        from inbound.pipeline import process_message
        from inbound.types import ParsedMessage

        msg_record = db_repository.get_inbound_message(request_model.tenant_id, request_model.message_id)
        if not msg_record:
            raise HTTPException(status_code=404, detail=f"Message {request_model.message_id} not found")

        received_at = msg_record.get("received_at")
        parsed_received_at = (
            datetime.fromisoformat(str(received_at).replace("Z", "+00:00"))
            if received_at
            else datetime.now(timezone.utc)
        )
        msg = ParsedMessage(
            rfc_message_id=msg_record["rfc_message_id"],
            thread_id=msg_record.get("thread_id", ""),
            imap_uid=int(msg_record.get("imap_uid", 0) or 0),
            from_addr=msg_record.get("from_addr", request_model.from_addr),
            from_domain=msg_record.get("from_domain", request_model.from_domain),
            to_addr=msg_record.get("to_addr", ""),
            subject=msg_record.get("subject", request_model.subject),
            received_at=parsed_received_at,
            body_html=msg_record.get("body_html", ""),
            body_text=msg_record.get("body_text", ""),
        )
        result = await process_message(
            msg=msg,
            tenant_id=request_model.tenant_id,
            repository=db_repository,
            source=request_model.source,
        )
        return InboundProcessResponse(
            message_id=result["message_id"],
            action=result["action"],
            total_score=result.get("total_score") or 0,
            stage=result.get("stage", ""),
            draft_generated=result.get("draft_generated", False),
            escalated=result.get("escalated", False),
            auto_archived=result.get("auto_archived", False),
        )

    @app.post("/outbound/extract")
    async def outbound_extract(request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        body = await request.json()
        transcript = body.get("transcript", "")
        prospect_context = body.get("prospect_context", {})

        from outbound.extraction import extract_from_transcript

        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, extract_from_transcript, transcript, prospect_context
        )
        return result

    @app.get("/outbound/daily-plan")
    def outbound_daily_plan(request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        from outbound.daily_plan import build_daily_plan
        return build_daily_plan()

    @app.get("/outbound/current-queue")
    def outbound_current_queue(
        request: Request,
        block: str,
        segment: str | None = None,
        exclude_dialed: bool = True,
    ) -> dict[str, Any]:
        validate_event_auth(request)
        normalized_block = block.upper()
        if normalized_block not in {"AM", "MID", "EOD", "ALL"}:
            raise HTTPException(status_code=400, detail=f"Invalid block: {block}")

        from outbound import queue_builder, sprint_state

        state = sprint_state.get_current_state()
        queue = queue_builder.build_queue(
            block=normalized_block,
            segment=segment or state.get("active_segment"),
            exclude_dialed=exclude_dialed,
        )
        return {"state": state, "queue": queue}

    @app.post("/outbound/lifecycle-run")
    def outbound_lifecycle_run(request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        from outbound.lifecycle import run_lifecycle_sweep
        return run_lifecycle_sweep()

    @app.get("/outbound/scoreboard")
    def outbound_scoreboard(request: Request, include_tactical: bool = False) -> dict[str, Any]:
        validate_event_auth(request)
        from outbound.scoreboard import sprint_scoreboard, tactical_recommendations

        metrics = sprint_scoreboard()
        if include_tactical:
            metrics["tactical_recommendations"] = tactical_recommendations()
        return metrics

    @app.post("/outbound/dial-started")
    async def outbound_dial_started(request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        body = await request.json()
        prospect_id = body.get("prospect_id")
        if not prospect_id:
            raise HTTPException(status_code=400, detail="prospect_id is required")

        from outbound import store as outbound_store
        from outbound.constants import OUTBOUND_TENANT_ID

        twilio_call_sid = f"dial-started-{uuid4()}"
        result = outbound_store.insert_outbound_call(
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "prospect_id": prospect_id,
                "twilio_call_sid": twilio_call_sid,
                "called_at": datetime.now(timezone.utc).isoformat(),
                "outcome": "dial_started",
                "call_outcome_type": "dial_started",
            }
        )
        if not result.get("inserted"):
            raise HTTPException(status_code=500, detail="failed to insert dial_started event")
        record = result.get("record") or {}
        return {"id": record.get("id"), "twilio_call_sid": twilio_call_sid}

    @app.get("/outbound/pipeline-review")
    def outbound_pipeline_review(request: Request) -> dict[str, Any]:
        validate_event_auth(request)
        from outbound import store as outbound_store
        from outbound.constants import OUTBOUND_TENANT_ID
        from outbound.daily_plan import current_week_number, is_calling_day, load_schedule
        from outbound.scoreboard import sprint_scoreboard

        schedule = load_schedule()
        today = date.today()
        week_num = current_week_number(schedule, today) if schedule else 0
        calling_day = bool(schedule and week_num > 0 and is_calling_day(schedule, week_num, today))

        metrics = sprint_scoreboard(OUTBOUND_TENANT_ID, today)
        warm_leads = outbound_store.list_outbound_prospects(
            tenant_id=OUTBOUND_TENANT_ID,
            stages=["callback", "interested"],
        )
        missing_next_step = [
            {
                "prospect_id": row.get("id"),
                "business_name": row.get("business_name"),
                "stage": row.get("stage"),
                "metro": row.get("metro"),
            }
            for row in warm_leads
            if not row.get("next_action_date")
        ]

        return {
            "date": today.isoformat(),
            "week": week_num,
            "calling_day": calling_day,
            "scoreboard": metrics,
            "zero_dials_alert": calling_day and int(metrics.get("daily_dials", 0) or 0) == 0,
            "warm_leads_missing_next_step": missing_next_step,
            "sections": {
                "engaged_with_ai_followup": [],
                "recommended_actions": [
                    f"Set next action date for {len(missing_next_step)} warm lead(s)"
                    if missing_next_step
                    else "Warm leads all have next steps assigned"
                ],
            },
        }

    @app.get("/outbound/digest")
    def outbound_digest(request: Request, date: str | None = None) -> dict[str, Any]:
        validate_event_auth(request)
        from outbound import store as outbound_store
        from outbound.ceo_tools import outbound_funnel_summary
        stats = outbound_store.today_call_stats(date=date)
        funnel = outbound_funnel_summary(days=1)
        return {"stats": stats, "funnel": funnel, "date": date}

    @app.post("/discord/ask")
    async def discord_ask(request: Request) -> dict[str, Any]:
        """Direct API for testing the Sales Assistant without Discord."""
        validate_event_auth(request)
        body = await request.json()
        question = str(body.get("question", "")).strip()
        if not question:
            return {"error": "missing question"}
        from outbound.assistant import answer_question
        return {"answer": answer_question(question)}

    @app.post("/onboard-tenant")
    def onboard_tenant_endpoint(request: OnboardTenantRequest, http_request: Request) -> dict[str, Any]:
        return onboard_tenant({**request.model_dump(), "actor_id": actor_id_for(http_request, "operator")})

    @app.post("/control/kill-switch")
    def set_kill_switch(request: KillSwitchRequest, http_request: Request) -> dict[str, Any]:
        result = upsert_kill_switch(request.model_dump())
        log_audit_event(
            action_type="control.kill_switch.updated",
            actor_id=actor_id_for(http_request, request.created_by),
            reason=request.reason,
            tenant_id=request.scope_id if request.scope == "tenant" else None,
            target_type=request.scope,
            target_id=request.scope_id,
            payload=result,
        )
        return result

    @app.get("/control/kill-switches")
    def get_kill_switches() -> list[dict[str, Any]]:
        return list_kill_switches()

    @app.get("/alerts")
    def get_alerts(tenant_id: str = None, status: str = None) -> list[dict[str, Any]]:
        if not tenant_id:
            return list_alerts(tenant_id=None, status=status)
        return _merge_records_by_id(*(list_alerts(tenant_id=value, status=status) for value in _tenant_lookup_values(tenant_id)))

    @app.get("/incidents")
    def get_incidents(tenant_id: str = None, status: str = None) -> list[dict[str, Any]]:
        if not tenant_id:
            return list_incidents(tenant_id=None, status=status)
        return _merge_records_by_id(*(list_incidents(tenant_id=value, status=status) for value in _tenant_lookup_values(tenant_id)))

    @app.post("/incidents/{incident_id}/workflow")
    def update_incident_workflow_endpoint(incident_id: str, request: IncidentWorkflowRequest, http_request: Request) -> dict[str, Any]:
        actor_id = actor_id_for(http_request, "operator")
        current = _get_incident_or_404(incident_id)
        tenant_config = get_tenant_config(current["tenant_id"]) if current.get("tenant_id") else {}
        timestamp = datetime.now(timezone.utc).isoformat()
        assigned_to = request.assigned_to
        assignment_reason = None
        if assigned_to and request.workflow_status in {"acknowledged", "investigating"}:
            assigned_to, assignment_reason = resolve_assignee(
                assigned_to,
                tenant_config,
                incident_type=current.get("alert_type"),
                incident_category=current.get("incident_category"),
                remediation_category=current.get("remediation_category"),
                incident_domain=current.get("incident_domain"),
                alert_type=current.get("alert_type"),
                current_incident_id=incident_id,
            )
        assignment_history = list(current.get("assignment_history", []))
        assignment_history_entry = None
        if assigned_to and assigned_to != current.get("assigned_to"):
            assignment_history_entry = {
                "at": timestamp,
                "from": current.get("assigned_to"),
                "to": assigned_to,
                "reason": assignment_reason or "manual_assignment",
            }
            assignment_history.append(assignment_history_entry)
        pending_updates = {
            "workflow_status": request.workflow_status,
            "assigned_to": assigned_to,
            "operator_notes": request.operator_notes,
            "last_reviewed_at": timestamp,
            "last_reviewed_by": actor_id,
            "last_assignment_reason": assignment_reason,
            "assignment_history": assignment_history,
        }
        if workflow_requires_completed_runbook(current, request.workflow_status):
            pending_steps = pending_runbook_steps(current)
            if pending_steps:
                detail = {
                    "message": f"Runbook steps must be completed before workflow status '{request.workflow_status}'",
                    "pending_steps": [
                        {"step_index": step.get("step_index"), "title": step.get("title")}
                        for step in pending_steps
                    ],
                }
                log_audit_event(
                    action_type="incident.workflow.blocked_incomplete_runbook",
                    actor_id=actor_id,
                    reason=request.operator_notes or detail["message"],
                    tenant_id=current.get("tenant_id"),
                    target_type="incident",
                    target_id=incident_id,
                    payload=detail,
                )
                raise HTTPException(status_code=400, detail=detail)
        if workflow_requires_approval(current, request.workflow_status):
            approval_request = create_approval_request(
                {
                    "tenant_id": current.get("tenant_id"),
                    "status": "pending",
                    "reason": f"Runbook approval required before workflow status '{request.workflow_status}'",
                    "requested_by": actor_id,
                    "request_type": "incident_workflow",
                    "payload": {
                        "incident_id": incident_id,
                        "incident_updates": pending_updates,
                        "runbook_id": current.get("runbook_id"),
                        "runbook_title": current.get("runbook_title"),
                        "approval_policy": current.get("approval_policy", {}),
                    },
                }
            )
            log_audit_event(
                action_type="incident.workflow.approval_requested",
                actor_id=actor_id,
                reason=request.operator_notes or f"Approval required for incident workflow change to {request.workflow_status}",
                tenant_id=current.get("tenant_id"),
                target_type="incident",
                target_id=incident_id,
                payload={"approval_request_id": approval_request["id"], "requested_workflow_status": request.workflow_status},
            )
            return {**current, "approval_required": True, "approval_request": approval_request}
        result = update_incident_workflow(
            incident_id,
            workflow_status=request.workflow_status,
            actor_id=actor_id,
            assigned_to=assigned_to,
            operator_notes=request.operator_notes,
            last_assignment_reason=assignment_reason,
            assignment_history_entry=assignment_history_entry,
            now_iso=timestamp,
        )
        if assigned_to and request.workflow_status in {"acknowledged", "investigating"}:
            result["notification"] = notify_incident(result, tenant_config, reminder=False)
        log_audit_event(
            action_type=f"incident.{request.workflow_status}",
            actor_id=actor_id,
            reason=request.operator_notes or f"Incident marked {request.workflow_status}",
            tenant_id=result.get("tenant_id"),
            target_type="incident",
            target_id=incident_id,
            payload=result,
        )
        return result

    @app.post("/incidents/{incident_id}/runbook-progress")
    def update_incident_runbook_progress_endpoint(
        incident_id: str,
        request: IncidentRunbookProgressRequest,
        http_request: Request,
    ) -> dict[str, Any]:
        actor_id = actor_id_for(http_request, "operator")
        current = _get_incident_or_404(incident_id)
        if not current.get("runbook_steps"):
            raise HTTPException(status_code=400, detail="Incident does not have a bound runbook")
        expected_revision = request.expected_revision or int(current.get("incident_revision", 1))
        expected_step_revision = request.expected_step_revision or int((get_runbook_step(current, request.step_index) or {}).get("step_revision", 1))
        try:
            result = update_incident_runbook_progress(
                incident_id,
                step_index=request.step_index,
                status=request.status,
                actor_id=actor_id,
                note=request.note,
                expected_revision=expected_revision,
                expected_step_revision=expected_step_revision,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except IndexError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            status_code = 409 if "revision conflict" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        log_audit_event(
            action_type="incident.runbook_progress.updated",
            actor_id=actor_id,
            reason=request.note or f"Marked runbook step {request.step_index} as {request.status}",
            tenant_id=result.get("tenant_id"),
            target_type="incident",
            target_id=incident_id,
            payload={"step_index": request.step_index, "status": request.status},
        )
        return result

    @app.post("/incidents/{incident_id}/runbook-assignment")
    def update_incident_runbook_assignment_endpoint(
        incident_id: str,
        request: IncidentRunbookAssignmentRequest,
        http_request: Request,
    ) -> dict[str, Any]:
        actor_id = actor_id_for(http_request, "operator")
        current = _get_incident_or_404(incident_id)
        if not current.get("runbook_steps"):
            raise HTTPException(status_code=400, detail="Incident does not have a bound runbook")
        expected_revision = request.expected_revision or int(current.get("incident_revision", 1))
        expected_step_revision = request.expected_step_revision or int((get_runbook_step(current, request.step_index) or {}).get("step_revision", 1))
        try:
            result = update_incident_runbook_assignment(
                incident_id,
                step_index=request.step_index,
                actor_id=actor_id,
                action=request.action,
                assigned_to=request.assigned_to,
                claim_ttl_seconds=request.claim_ttl_seconds,
                now_iso=request.now_iso,
                expected_revision=expected_revision,
                expected_step_revision=expected_step_revision,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (IndexError, ValueError) as exc:
            status_code = 409 if "revision conflict" in str(exc) else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        log_audit_event(
            action_type="incident.runbook_assignment.updated",
            actor_id=actor_id,
            reason=f"{request.action} runbook step {request.step_index}",
            tenant_id=result.get("tenant_id"),
            target_type="incident",
            target_id=incident_id,
            payload={"step_index": request.step_index, "action": request.action, "assigned_to": request.assigned_to},
        )
        return result

    @app.get("/incidents/{incident_id}/runbook-plan")
    def get_incident_runbook_plan_endpoint(incident_id: str) -> dict[str, Any]:
        current = _get_incident_or_404(incident_id)
        return {
            "incident_id": incident_id,
            "incident_revision": current.get("incident_revision"),
            "runbook_id": current.get("runbook_id"),
            "runbook_title": current.get("runbook_title"),
            "runbook_progress_summary": current.get("runbook_progress_summary", {}),
            "runbook_execution_plan": current.get("runbook_execution_plan", {}),
        }

    @app.post("/incidents/remind-stale")
    def remind_stale_incidents_endpoint(request: IncidentReminderRequest) -> list[dict[str, Any]]:
        return send_incident_reminders(tenant_id=request.tenant_id, now_iso=request.now_iso)

    @app.post("/alerts/{alert_id}/status")
    def update_alert_endpoint(alert_id: str, request: AlertDecisionRequest, http_request: Request) -> dict[str, Any]:
        actor_id = actor_id_for(http_request, "operator")
        now_iso = datetime.now(timezone.utc).isoformat()
        patch: dict[str, Any] = {"status": request.status, "resolution_notes": request.resolution_notes}
        if request.status == "acknowledged":
            patch["acknowledged_at"] = now_iso
            patch["acknowledged_by"] = actor_id
        elif request.status == "escalated":
            patch["escalated_at"] = now_iso
            patch["escalated_by"] = actor_id
        elif request.status == "resolved":
            patch["resolved_at"] = now_iso
            patch["resolved_by"] = actor_id
        result = update_alert_and_sync_incident(alert_id, patch)
        log_audit_event(
            action_type=f"alert.{request.status}",
            actor_id=actor_id,
            reason=request.resolution_notes or f"Alert marked {request.status}",
            tenant_id=result.get("tenant_id"),
            target_type="alert",
            target_id=alert_id,
            payload=result,
        )
        return result

    @app.get("/jobs")
    def get_jobs(tenant_id: str = None, run_id: str = None) -> list[dict[str, Any]]:
        resolved_tenant_id = get_tenant(tenant_id)["id"] if tenant_id else None
        return list_jobs(tenant_id=resolved_tenant_id, run_id=run_id)

    @app.get("/artifacts")
    def get_artifacts(tenant_id: str) -> list[dict[str, Any]]:
        return list_artifacts(get_tenant(tenant_id)["id"])

    @app.post("/artifacts/{artifact_id}/lifecycle")
    def update_artifact_lifecycle_endpoint(artifact_id: str, request: ArtifactLifecycleRequest, http_request: Request) -> dict[str, Any]:
        tenant_id = get_tenant(request.tenant_id)["id"]
        result = update_artifact_lifecycle(artifact_id, request.target_state, tenant_id=tenant_id)
        log_audit_event(
            action_type="artifact.lifecycle.updated",
            actor_id=actor_id_for(http_request, "operator"),
            reason=f"Transition artifact to {request.target_state}",
            tenant_id=tenant_id,
            target_type="artifact",
            target_id=artifact_id,
            payload=result,
        )
        return result

    @app.post("/alerts/evaluate")
    def evaluate_alerts_endpoint(request: AlertEvaluationRequest) -> list[dict[str, Any]]:
        return evaluate_alerts(tenant_id=request.tenant_id, window_minutes=request.window_minutes)

    @app.post("/alerts/escalate-stale")
    def escalate_alerts_endpoint(request: AlertEscalationRequest) -> list[dict[str, Any]]:
        return auto_escalate_alerts(tenant_id=request.tenant_id, now_iso=request.now_iso)

    @app.post("/alerts/resolve-recovered")
    def resolve_recovered_alerts_endpoint(request: AlertRecoveryRequest) -> list[dict[str, Any]]:
        tenant_config = get_tenant_config(request.tenant_id) if request.tenant_id else {}
        thresholds = resolve_thresholds(tenant_config)
        return auto_resolve_recovered_alerts(
            metrics=request.metrics,
            thresholds=thresholds,
            tenant_id=request.tenant_id,
            tenant_config=tenant_config,
            now_iso=request.now_iso,
        )

    @app.post("/improvement/run-experiment")
    def run_experiment_endpoint(request: ImprovementExperimentRequest, http_request: Request) -> dict[str, Any]:
        result = run_experiment(request.model_dump())
        log_audit_event(
            action_type="improvement.experiment.run",
            actor_id=actor_id_for(http_request, "operator"),
            reason=request.proposal,
            tenant_id=get_tenant(request.tenant_id)["id"] if request.tenant_id else None,
            target_type="mutation_surface",
            target_id=request.mutation_surface,
            payload=result,
        )
        return result

    @app.post("/content/process")
    def process_content_endpoint(request: ContentPipelineRequest) -> dict[str, Any]:
        return process_customer_content(request.model_dump())

    @app.post("/evals/run")
    def run_eval_endpoint(request: EvalRunRequest, http_request: Request) -> dict[str, Any]:
        tenant_id = get_tenant(request.tenant_id)["id"] if request.tenant_id else None
        result = run_eval_suite(level=request.level, tenant_id=tenant_id, target=request.target)
        log_audit_event(
            action_type="eval.run",
            actor_id=actor_id_for(http_request, "operator"),
            reason=f"Run {request.level} eval suite",
            tenant_id=tenant_id,
            target_type="eval",
            target_id=request.target,
            payload={"eval_run_id": result["id"], "overall_score": result["overall_score"]},
        )
        return result

    @app.get("/evals/results")
    def list_eval_results(level: str = None, tenant_id: str = None) -> list[dict[str, Any]]:
        resolved_tenant_id = get_tenant(tenant_id)["id"] if tenant_id else None
        return list_eval_runs_for_api(tenant_id=resolved_tenant_id, level=level)

    @app.get("/recovery/entries")
    def get_recovery_entries(entry_type: str = None) -> list[dict[str, Any]]:
        return list_recovery_entries(entry_type=entry_type)

    @app.post("/recovery/replay")
    def replay_recovery(request: RecoveryReplayRequest, http_request: Request) -> dict[str, Any]:
        result = replay_recovery_entry(request.entry_id)
        log_audit_event(
            action_type="recovery.replayed",
            actor_id=actor_id_for(http_request, "operator"),
            reason="Replay recovery entry",
            tenant_id=result["persisted"].get("tenant_id"),
            target_type="recovery_entry",
            target_id=request.entry_id,
            payload={"run_id": result["persisted"].get("run_id")},
        )
        return result

    @app.get("/audit-logs")
    def get_audit_logs(tenant_id: str = None, action_type: str = None) -> list[dict[str, Any]]:
        resolved_tenant_id = get_tenant(tenant_id)["id"] if tenant_id else None
        return list_audit_logs(tenant_id=resolved_tenant_id, action_type=action_type)

    @app.get("/approvals")
    def get_approvals(tenant_id: str = None, status: str = None) -> list[dict[str, Any]]:
        resolved_tenant_id = get_tenant(tenant_id)["id"] if tenant_id else None
        return approvals_for_api(tenant_id=resolved_tenant_id, status=status)

    @app.post("/approvals/{approval_id}")
    def decide_approval(approval_id: str, request: ApprovalDecisionRequest, http_request: Request) -> dict[str, Any]:
        result = resolve_approval_request(
            approval_id,
            status=request.status,
            actor_id=actor_id_for(http_request, "operator"),
            resolution_notes=request.resolution_notes,
        )
        continuation = None
        if request.status == "approved":
            continuation = continue_approved_request(
                result,
                actor_id=actor_id_for(http_request, "operator"),
                resolution_notes=request.resolution_notes,
            )
        log_audit_event(
            action_type="approval.request.resolved",
            actor_id=actor_id_for(http_request, "operator"),
            reason=request.resolution_notes,
            tenant_id=result.get("tenant_id"),
            target_type="approval_request",
            target_id=approval_id,
            payload={"status": request.status, "continuation": continuation},
        )
        return {**result, "continuation": continuation}

    @app.post("/retention/run")
    def run_retention(request: RetentionRunRequest, http_request: Request) -> dict[str, Any]:
        resolved_tenant_id = get_tenant(request.tenant_id)["id"] if request.tenant_id else None
        result = run_retention_pass(tenant_id=resolved_tenant_id, dry_run=request.dry_run)
        log_audit_event(
            action_type="retention.run",
            actor_id=actor_id_for(http_request, "operator"),
            reason="Run retention maintenance",
            tenant_id=resolved_tenant_id,
            target_type="retention",
            target_id=resolved_tenant_id,
            payload={"dry_run": request.dry_run, "result": result},
        )
        return result

    @app.post("/schedules/due-tenants")
    def get_due_tenants(request: DueTenantScheduleRequest) -> list[dict[str, Any]]:
        return due_tenants(job_type=request.job_type, utc_iso=request.utc_iso, max_tenants=request.max_tenants)

    @app.post("/schedules/claim")
    def claim_schedule_backlog(request: ScheduleClaimRequest, http_request: Request) -> list[dict[str, Any]]:
        claimed = claim_due_tenants(
            job_type=request.job_type,
            utc_iso=request.utc_iso,
            max_tenants=request.max_tenants,
            claimer_id=request.claimer_id or actor_id_for(http_request, "scheduler"),
            claim_ttl_seconds=request.claim_ttl_seconds,
        )
        log_audit_event(
            action_type="schedule.claimed",
            actor_id=actor_id_for(http_request, request.claimer_id),
            reason=f"Claim {request.job_type} scheduler backlog",
            target_type="scheduler_backlog",
            target_id=request.job_type,
            payload={"count": len(claimed)},
        )
        return claimed

    @app.post("/schedules/finalize")
    def finalize_schedule_backlog(request: ScheduleFinalizeRequest, http_request: Request) -> dict[str, Any]:
        finalized = finalize_scheduler_claim(
            entry_id=request.entry_id,
            action=request.action,
            actor_id=request.actor_id or actor_id_for(http_request, "scheduler"),
            utc_iso=request.utc_iso,
            note=request.note,
        )
        log_audit_event(
            action_type="schedule.finalized",
            actor_id=actor_id_for(http_request, request.actor_id),
            reason=request.note or f"{request.action} scheduler backlog",
            tenant_id=finalized.get("tenant_id"),
            target_type="scheduler_backlog",
            target_id=request.entry_id,
            payload={"action": request.action, "status": finalized["status"]},
        )
        return finalized

    @app.post("/schedules/heartbeat")
    def heartbeat_schedule_backlog(request: ScheduleHeartbeatRequest, http_request: Request) -> dict[str, Any]:
        heartbeat = heartbeat_scheduler_claim(
            entry_id=request.entry_id,
            actor_id=request.actor_id or actor_id_for(http_request, "scheduler"),
            utc_iso=request.utc_iso,
            claim_ttl_seconds=request.claim_ttl_seconds,
        )
        log_audit_event(
            action_type="schedule.heartbeat",
            actor_id=actor_id_for(http_request, request.actor_id),
            reason="Extend scheduler claim",
            tenant_id=heartbeat.get("tenant_id"),
            target_type="scheduler_backlog",
            target_id=request.entry_id,
            payload={"claim_expires_at": heartbeat.get("claim_expires_at")},
        )
        return heartbeat

    @app.post("/schedules/sweep")
    def sweep_schedule_backlog(request: ScheduleSweepRequest, http_request: Request) -> dict[str, Any]:
        sweep = sweep_stale_scheduler_claims(utc_iso=request.utc_iso, dry_run=request.dry_run)
        log_audit_event(
            action_type="schedule.swept",
            actor_id=actor_id_for(http_request, "scheduler"),
            reason="Sweep stale scheduler claims",
            target_type="scheduler_backlog",
            target_id="stale-claims",
            payload={"released_count": sweep["released_count"], "dry_run": request.dry_run},
        )
        return sweep

    @app.post("/schedules/override")
    def override_schedule_backlog(request: ScheduleOverrideRequest, http_request: Request) -> dict[str, Any]:
        overridden = override_scheduler_claim(
            entry_id=request.entry_id,
            action=request.action,
            actor_id=request.actor_id or actor_id_for(http_request, "operator"),
            utc_iso=request.utc_iso,
            note=request.note,
            new_claimer_id=request.new_claimer_id,
            claim_ttl_seconds=request.claim_ttl_seconds,
        )
        log_audit_event(
            action_type="schedule.overridden",
            actor_id=actor_id_for(http_request, request.actor_id),
            reason=request.note or request.action,
            tenant_id=overridden.get("tenant_id"),
            target_type="scheduler_backlog",
            target_id=request.entry_id,
            payload={
                "action": request.action,
                "status": overridden["status"],
                "claimed_by": overridden.get("claimed_by"),
            },
        )
        return overridden

    @app.get("/schedules/backlog")
    def get_schedule_backlog(
        tenant_id: str = None,
        job_type: str = None,
        status: str = None,
        utc_iso: str = None,
    ) -> list[dict[str, Any]]:
        resolved_tenant_id = get_tenant(tenant_id)["id"] if tenant_id else None
        if utc_iso and job_type:
            reconcile_scheduler_backlog(job_type=job_type, utc_iso=utc_iso)
        return list_scheduler_backlog_entries(tenant_id=resolved_tenant_id, job_type=job_type, status=status)

    @app.get("/cockpit/overview")
    def cockpit_overview_endpoint() -> dict[str, Any]:
        return cockpit_overview()

    @app.get("/cockpit/scheduler")
    def cockpit_scheduler_endpoint(now_iso: str = None) -> dict[str, Any]:
        return cockpit_scheduler_view(now_iso=now_iso)
else:  # pragma: no cover
    app = None

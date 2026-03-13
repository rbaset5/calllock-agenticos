from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcessCallRequest(StrictModel):
    call_id: str
    tenant_id: str
    transcript: str = ""
    problem_description: str = ""
    worker_id: str = "customer-analyst"
    call_source: Literal["retell", "manual", "test"] = "retell"
    received_at: Optional[str] = None
    call_metadata: dict[str, Any] = Field(default_factory=dict)
    context_budget: int = 1200
    feature_flags: dict[str, bool] = Field(default_factory=lambda: {"harness_enabled": True})
    compliance_rules: list[dict[str, Any]] = Field(default_factory=list)
    tenant_config: dict[str, Any] = Field(default_factory=dict)
    environment_allowed_tools: list[str] = Field(default_factory=list)
    task_context: dict[str, Any] = Field(default_factory=dict)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    job_requests: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> "ProcessCallRequest":
        if not self.transcript and not self.problem_description:
            raise ValueError("Either transcript or problem_description is required")
        if self.context_budget <= 0:
            raise ValueError("context_budget must be positive")
        return self


class ProcessCallResponse(StrictModel):
    run_id: str
    policy_verdict: str
    verification_passed: bool
    verification_verdict: str
    output: dict[str, Any]
    jobs: list[dict[str, Any]] = Field(default_factory=list)


class HarnessProcessCallEvent(StrictModel):
    name: Literal["harness/process-call"]
    data: ProcessCallRequest


class JobDispatchRequest(StrictModel):
    tenant_id: str
    origin_worker_id: str
    origin_run_id: str
    job_type: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source_call_id: Optional[str] = None
    supersedes_job_id: Optional[str] = None
    created_by: str = "harness"


class JobCompleteEvent(StrictModel):
    job_id: str
    tenant_id: str
    status: Literal["completed", "failed", "cancelled", "superseded"]
    result: dict[str, Any] = Field(default_factory=dict)


class HarnessJobCompleteEvent(StrictModel):
    name: Literal["harness/job-complete"]
    data: JobCompleteEvent


class OnboardTenantRequest(StrictModel):
    slug: str
    name: str
    industry_pack_id: str = "hvac"
    tenant_id: Optional[str] = None
    allowed_tools: list[str] = Field(default_factory=list)
    tone_profile: dict[str, Any] = Field(default_factory=lambda: {"formality": "direct", "banned_words": []})
    feature_flags: dict[str, bool] = Field(default_factory=lambda: {"harness_enabled": True})
    configure_voice_agent: bool = True
    provision_automations: bool = True


class KillSwitchRequest(StrictModel):
    scope: Literal["global", "worker", "tenant"]
    scope_id: Optional[str] = None
    active: bool = True
    reason: str
    created_by: str = "operator"


class AlertEvaluationRequest(StrictModel):
    tenant_id: Optional[str] = None
    window_minutes: int = 15


class AlertDecisionRequest(StrictModel):
    status: Literal["acknowledged", "escalated", "resolved"]
    resolution_notes: str = ""


class AlertEscalationRequest(StrictModel):
    tenant_id: Optional[str] = None
    now_iso: Optional[str] = None


class AlertRecoveryRequest(StrictModel):
    tenant_id: Optional[str] = None
    now_iso: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class IncidentWorkflowRequest(StrictModel):
    workflow_status: Literal["new", "acknowledged", "investigating", "closed"]
    assigned_to: Optional[str] = None
    operator_notes: str = ""


class IncidentRunbookProgressRequest(StrictModel):
    step_index: int = Field(ge=1)
    status: Literal["pending", "completed"]
    note: str = ""
    expected_revision: Optional[int] = Field(default=None, ge=1)
    expected_step_revision: Optional[int] = Field(default=None, ge=1)


class IncidentRunbookAssignmentRequest(StrictModel):
    step_index: int = Field(ge=1)
    action: Literal["assign", "claim", "heartbeat", "release"]
    assigned_to: Optional[str] = None
    claim_ttl_seconds: int = Field(default=600, ge=1)
    now_iso: Optional[str] = None
    expected_revision: Optional[int] = Field(default=None, ge=1)
    expected_step_revision: Optional[int] = Field(default=None, ge=1)


class IncidentReminderRequest(StrictModel):
    tenant_id: Optional[str] = None
    now_iso: Optional[str] = None


class ImprovementExperimentRequest(StrictModel):
    tenant_id: Optional[str] = None
    mutation_surface: str
    proposal: str
    baseline_score: float
    candidate_score: float
    ttl_seconds: int = 900


class ContentPipelineRequest(StrictModel):
    tenant_id: str
    call_id: str
    transcript: str
    consent_granted: bool = False


class ArtifactLifecycleRequest(StrictModel):
    tenant_id: str
    target_state: Literal["created", "active", "archived", "deleted"]


class EvalRunRequest(StrictModel):
    level: Literal["core", "industry", "tenant"]
    tenant_id: Optional[str] = None
    target: Optional[str] = None


class RecoveryReplayRequest(StrictModel):
    entry_id: str


class ApprovalDecisionRequest(StrictModel):
    status: Literal["approved", "rejected", "cancelled"]
    resolution_notes: str


class RetentionRunRequest(StrictModel):
    tenant_id: Optional[str] = None
    dry_run: bool = False


class DueTenantScheduleRequest(StrictModel):
    job_type: Literal["retention", "tenant_eval"]
    utc_iso: Optional[str] = None
    max_tenants: Optional[int] = Field(default=None, ge=1)


class ScheduleClaimRequest(StrictModel):
    job_type: Literal["retention", "tenant_eval"]
    utc_iso: Optional[str] = None
    max_tenants: Optional[int] = Field(default=None, ge=1)
    claimer_id: str = "scheduler"
    claim_ttl_seconds: int = Field(default=600, ge=1)


class ScheduleFinalizeRequest(StrictModel):
    entry_id: str
    action: Literal["complete", "release"]
    actor_id: str = "scheduler"
    utc_iso: Optional[str] = None
    note: str = ""


class ScheduleHeartbeatRequest(StrictModel):
    entry_id: str
    actor_id: str = "scheduler"
    utc_iso: Optional[str] = None
    claim_ttl_seconds: int = Field(default=600, ge=1)


class ScheduleSweepRequest(StrictModel):
    utc_iso: Optional[str] = None
    dry_run: bool = False


class ScheduleOverrideRequest(StrictModel):
    entry_id: str
    action: Literal["force_release", "force_claim"]
    actor_id: str = "operator"
    utc_iso: Optional[str] = None
    note: str = ""
    new_claimer_id: Optional[str] = None
    claim_ttl_seconds: int = Field(default=600, ge=1)

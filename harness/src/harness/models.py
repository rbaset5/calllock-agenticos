from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessCallRequest(BaseModel):
    call_id: str
    tenant_id: str
    transcript: str = ""
    problem_description: str = ""
    worker_id: str = "customer-analyst"
    feature_flags: dict[str, bool] = Field(default_factory=lambda: {"harness_enabled": True})
    compliance_rules: list[dict[str, Any]] = Field(default_factory=list)
    tenant_config: dict[str, Any] = Field(default_factory=dict)
    environment_allowed_tools: list[str] = Field(default_factory=list)


class ProcessCallResponse(BaseModel):
    run_id: str
    policy_verdict: str
    verification_passed: bool
    output: dict[str, Any]


class HarnessEventEnvelope(BaseModel):
    name: str
    data: ProcessCallRequest

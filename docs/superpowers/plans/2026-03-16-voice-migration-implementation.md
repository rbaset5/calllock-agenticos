# Voice Agent Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Valencia v10-simplified Express voice agent backend into rabat as `harness/src/voice/`, enabling real-time Retell tool calls via FastAPI and post-call processing via Inngest fan-out.

**Architecture:** Three FastAPI routers (voice tools, post-call webhook, booking management) mount on the existing harness app. Pure-function extraction/classification pipeline runs synchronously on call-ended webhooks. Async fan-out via Inngest handles CallLock App sync, growth touchpoints, alerts, and emergency SMS. Multi-tenant via existing RLS + Redis-cached VoiceConfig.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, twilio, pytest, Supabase (Postgres + RLS), Redis, Inngest (TypeScript thin proxies)

**Spec:** `docs/superpowers/specs/2026-03-16-voice-agent-migration-design.md`

**Source code to port:** `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/`

**Agent config source:** `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/voice-agent/retell-llm-v10-simplified.json`

---

## File Structure

```
harness/src/voice/
  __init__.py                    # Public exports: voice_router, post_call_router, booking_router
  models.py                      # Pydantic models: RetellToolCallRequest, CallEndedEvent, VoiceConfig, CalcomConfig, etc.
  auth.py                        # HMAC-SHA256 verification middleware + API key auth for bookings
  config.py                      # VoiceConfig/CalcomConfig resolution with Redis caching + AES-256-GCM decryption
  crypto.py                      # AES-256-GCM encrypt/decrypt for credential JSONB (VOICE_CREDENTIAL_KEY)
  router.py                      # FastAPI router: /webhook/retell/{tool} endpoints
  post_call_router.py            # FastAPI router: /webhook/retell/call-ended
  booking_router.py              # FastAPI router: /api/bookings/*
  tools/
    __init__.py
    lookup_caller.py             # lookup_caller tool handler (Supabase query, LIMIT 10/5/5)
    create_callback.py           # create_callback_request tool handler (Twilio SMS)
    sales_lead_alert.py          # send_sales_lead_alert tool handler (Twilio SMS)
  services/
    __init__.py
    twilio_sms.py                # Twilio SMS client (callback, sales lead, emergency)
    calcom.py                    # Cal.com API client (lookup, cancel, reschedule — NOT booking)
    app_sync.py                  # CallLock App webhook payload transform + HMAC signing
  extraction/
    __init__.py                  # Pipeline runner: run_extraction(transcript, raw_payload) -> dict
    post_call.py                 # Name, address, safety, problem duration extraction
    urgency.py                   # Urgency keyword inference -> UrgencyTier enum
    call_scorecard.py            # Weighted quality scoring (0-100)
    tags.py                      # 117-tag taxonomy engine (loads YAML, negation-aware)
    hvac_issue.py                # HVAC issue type inference
  classification/
    __init__.py
    call_type.py                 # Urgency -> dashboard level + priority color mapping
    revenue.py                   # Revenue tier classification
    traffic.py                   # Traffic controller: spam/vendor/legitimate routing

harness/tests/voice/
  __init__.py
  conftest.py                    # Voice-specific fixtures: mock_retell_payload, mock_voice_config, mock_redis, etc.
  test_crypto.py                 # AES-256-GCM encrypt/decrypt + key rotation tests
  test_models.py                 # Model validation tests
  test_auth.py                   # HMAC verification + API key auth tests
  test_config.py                 # VoiceConfig resolution + caching tests
  test_lookup_caller.py          # lookup_caller tool tests
  test_create_callback.py        # create_callback tool tests
  test_sales_lead_alert.py       # send_sales_lead_alert tool tests
  test_twilio_sms.py             # Twilio SMS service tests
  test_calcom.py                 # Cal.com service tests
  test_app_sync.py               # CallLock App sync tests
  extraction/
    __init__.py
    test_post_call.py            # Name, address, safety extraction tests (port V2 Vitest fixtures)
    test_urgency.py              # Urgency inference tests (port V2 11 test cases)
    test_call_scorecard.py       # Scorecard tests (port V2 10 test cases)
    test_tags.py                 # 117-tag taxonomy tests (port V2 fixtures)
    test_hvac_issue.py           # HVAC issue type tests
  classification/
    __init__.py
    test_call_type.py            # Call type classification tests
    test_revenue.py              # Revenue tier tests
    test_traffic.py              # Traffic controller tests
  test_post_call_pipeline.py     # Full pipeline integration test (the 2am Friday test)
  test_booking_router.py         # Booking management API tests

knowledge/industry-packs/hvac/
  _moc.md                        # MODIFY: add link to voice/ and taxonomy.yaml
  taxonomy.yaml                  # 117-tag HVAC taxonomy (ported from V2 tags.ts)
  voice/
    _moc.md                      # NEW: map-of-content for voice knowledge nodes
    retell-agent-v10.yaml        # v10-simplified agent config (ported from retell-llm-v10-simplified.json)

supabase/migrations/
  048_voice_config.sql           # voice_config + calcom_config columns, call_records table, voice_api_keys table

inngest/src/events/
  schemas.ts                     # MODIFY: add CallEndedPayload schema + validation
inngest/src/functions/
  voice.ts                       # NEW: 5 Inngest functions (process-voice-call, sync-app, send-emergency-sms, app-sync-retry, call-records-retention)

harness/src/harness/
  server.py                      # MODIFY: mount 3 voice routers via include_router
harness/src/db/
  repository.py                  # MODIFY: add voice CRUD operations (call_records, voice_api_keys)
  supabase_repository.py         # MODIFY: implement voice CRUD with tenant scoping
  local_repository.py            # MODIFY: implement voice CRUD with in-memory fallback
harness/
  requirements.txt               # MODIFY: add twilio dependency
```

---

## Chunk 1: Foundation — Models, Auth, Config, Migration

This chunk establishes the data layer and authentication before any business logic. Everything else depends on these.

### Task 1: Database Migration

**Files:**
- Create: `supabase/migrations/048_voice_config.sql`

- [ ] **Step 1: Write the migration SQL**

Port directly from spec Section 5. This creates:
- `voice_config` and `calcom_config` JSONB columns on `tenant_configs`
- `call_records` table with RLS
- `voice_api_keys` table with RLS
- `set_updated_at()` trigger function
- Indexes for phone lookup and unsynced records

```sql
-- Migration 048: Voice agent configuration and call records
--
-- Adds voice-specific config to tenant_configs and creates tables for
-- call record persistence and booking API key management.

-- Add voice config and Cal.com config columns to tenant_configs
ALTER TABLE public.tenant_configs
  ADD COLUMN voice_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN calcom_config jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Call records table for voice call persistence
CREATE TABLE public.call_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_call_id text NOT NULL,
  phone_number text,
  transcript text,
  raw_retell_payload jsonb NOT NULL,
  extracted_fields jsonb DEFAULT '{}'::jsonb,
  extraction_status text NOT NULL DEFAULT 'pending',
  quality_score numeric(5,2),
  tags text[] DEFAULT '{}',
  route text,
  urgency_tier text,
  caller_type text,
  primary_intent text,
  revenue_tier text,
  booking_id text,
  callback_scheduled boolean DEFAULT false,
  call_duration_seconds integer,
  end_call_reason text,
  call_recording_url text,
  synced_to_app boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER call_records_updated_at
  BEFORE UPDATE ON public.call_records
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.voice_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  api_key_hash text NOT NULL,
  label text NOT NULL DEFAULT 'default',
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE(api_key_hash)
);

ALTER TABLE public.call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_records FORCE ROW LEVEL SECURITY;
CREATE POLICY call_records_tenant ON public.call_records
  USING (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_api_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_api_keys_tenant ON public.voice_api_keys
  USING (tenant_id = public.current_tenant_id());

CREATE INDEX idx_call_records_phone ON public.call_records(tenant_id, phone_number);
CREATE INDEX idx_call_records_unsynced ON public.call_records(tenant_id, synced_to_app)
  WHERE synced_to_app = false;

-- Phone indexes for lookup_caller cross-table queries (prevents latency blowup at scale)
-- Only add these if the tables exist; skip if they don't yet.
CREATE INDEX IF NOT EXISTS idx_jobs_phone ON public.jobs(tenant_id, customer_phone);
CREATE INDEX IF NOT EXISTS idx_bookings_phone ON public.bookings(tenant_id, customer_phone);
```

- [ ] **Step 2: Verify migration ordering**

Run: `ls supabase/migrations/ | tail -5`
Expected: 048_voice_config.sql appears after 047_inbound_pipeline.sql

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/048_voice_config.sql
git commit -m "feat(voice): add migration 048 — voice_config, call_records, voice_api_keys"
```

### Task 2: Pydantic Models

**Files:**
- Create: `harness/src/voice/__init__.py`
- Create: `harness/src/voice/models.py`
- Create: `harness/tests/voice/__init__.py`
- Create: `harness/tests/voice/test_models.py`

- [ ] **Step 1: Create package init**

```python
# harness/src/voice/__init__.py
"""Voice agent module — Retell webhook handlers, extraction, classification."""
```

- [ ] **Step 2: Write model tests**

Test that models validate correctly and reject invalid data. Port enum values from V2 types.

```python
# harness/tests/voice/test_models.py
import pytest
from voice.models import (
    VoiceConfig,
    CalcomConfig,
    CallEndedEvent,
    RetellToolCallRequest,
    UrgencyTier,
    CallerType,
    PrimaryIntent,
    RevenueTier,
)


class TestVoiceConfig:
    def test_valid_config(self):
        config = VoiceConfig(
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_from_number="+15125551234",
            twilio_owner_phone="+15125555678",
            app_webhook_url="https://app.calllock.co/api/webhook",
            app_webhook_secret="secret",
            service_area_zips=["78701", "78702"],
            business_name="ACE Cooling",
            business_phone="+15125559999",
        )
        assert config.business_name == "ACE Cooling"

    def test_empty_zips_allowed(self):
        config = VoiceConfig(
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_from_number="+15125551234",
            twilio_owner_phone="+15125555678",
            app_webhook_url="https://app.calllock.co/api/webhook",
            app_webhook_secret="secret",
            service_area_zips=[],
            business_name="ACE Cooling",
            business_phone="+15125559999",
        )
        assert config.service_area_zips == []

    def test_missing_required_field_raises(self):
        with pytest.raises(Exception):
            VoiceConfig(twilio_account_sid="AC123")


class TestCalcomConfig:
    def test_valid_config(self):
        config = CalcomConfig(
            calcom_api_key="cal_live_xxx",
            calcom_event_type_id=12345,
            calcom_username="acecooling",
            calcom_timezone="America/Chicago",
        )
        assert config.calcom_timezone == "America/Chicago"


class TestCallEndedEvent:
    def test_minimal_valid_event(self):
        event = CallEndedEvent(
            tenant_id="t-123",
            call_id="c-456",
            call_source="retell",
            phone_number="+15125551234",
            transcript="Hello",
            urgency_tier=UrgencyTier.ROUTINE,
            caller_type=CallerType.RESIDENTIAL,
            primary_intent=PrimaryIntent.SERVICE,
            revenue_tier=RevenueTier.STANDARD_REPAIR,
            tags=[],
            quality_score=0.0,
            scorecard_warnings=[],
            route="legitimate",
            extraction_status="complete",
            retell_call_id="ret-789",
            call_duration_seconds=60,
            end_call_reason="agent_hangup",
        )
        assert event.call_source == "retell"

    def test_partial_extraction_allowed(self):
        event = CallEndedEvent(
            tenant_id="t-123",
            call_id="c-456",
            call_source="retell",
            phone_number="+15125551234",
            transcript="",
            urgency_tier=UrgencyTier.ROUTINE,
            caller_type=CallerType.UNKNOWN,
            primary_intent=PrimaryIntent.UNKNOWN,
            revenue_tier=RevenueTier.UNKNOWN,
            tags=[],
            quality_score=0.0,
            scorecard_warnings=["zero-tags", "callback-gap"],
            route="legitimate",
            extraction_status="partial",
            retell_call_id="ret-789",
            call_duration_seconds=5,
            end_call_reason="user_hangup",
        )
        assert event.extraction_status == "partial"


class TestUrgencyTier:
    def test_all_values(self):
        assert UrgencyTier.EMERGENCY == "emergency"
        assert UrgencyTier.URGENT == "urgent"
        assert UrgencyTier.ROUTINE == "routine"
        assert UrgencyTier.ESTIMATE == "estimate"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/test_models.py -v`
Expected: ImportError — voice.models does not exist yet

- [ ] **Step 4: Implement models**

Port enums from V2 `types/retell.ts` and build Pydantic models from spec Sections 4-5.

Also add a `DashboardPayload` Pydantic model that mirrors V2's `DashboardJobPayload` TypeScript interface field-for-field (~50 fields). This makes the CallLock App webhook contract explicit and testable. Reference: `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/services/dashboard.ts` (search for `DashboardJobPayload` interface).

Also add a `LooseModel` base class with a `@model_validator(mode="before")` that logs unexpected fields at WARNING level. Use this as the base for `RetellToolCallRequest` and `RetellCallEndedPayload` instead of raw `extra="allow"`.

```python
# harness/src/voice/models.py
"""Pydantic models for the voice agent module."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


# --- Enums (ported from Valencia V2 types/retell.ts) ---

class UrgencyTier(StrEnum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"
    ESTIMATE = "estimate"


class CallerType(StrEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    PROPERTY_MANAGER = "property_manager"
    THIRD_PARTY = "third_party"
    JOB_APPLICANT = "job_applicant"
    VENDOR = "vendor"
    SPAM = "spam"
    UNKNOWN = "unknown"


class PrimaryIntent(StrEnum):
    SERVICE = "service"
    MAINTENANCE = "maintenance"
    INSTALLATION = "installation"
    ESTIMATE = "estimate"
    COMPLAINT = "complaint"
    FOLLOWUP = "followup"
    SALES = "sales"
    UNKNOWN = "unknown"


class RevenueTier(StrEnum):
    REPLACEMENT = "replacement"
    MAJOR_REPAIR = "major_repair"
    STANDARD_REPAIR = "standard_repair"
    MINOR = "minor"
    DIAGNOSTIC = "diagnostic"
    UNKNOWN = "unknown"


class EndCallReason(StrEnum):
    CUSTOMER_HANGUP = "customer_hangup"
    AGENT_HANGUP = "agent_hangup"
    BOOKING_CONFIRMED = "booking_confirmed"
    CALLBACK_SCHEDULED = "callback_scheduled"
    SALES_LEAD = "sales_lead"
    OUT_OF_AREA = "out_of_area"
    SAFETY_EXIT = "safety_exit"
    WRONG_NUMBER = "wrong_number"
    VOICEMAIL = "voicemail"
    TRANSFER = "transfer"
    ERROR = "error"


# --- Config models ---

class VoiceConfig(BaseModel):
    """Per-tenant voice agent configuration. Stored encrypted in tenant_configs.voice_config."""
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_owner_phone: str
    app_webhook_url: str
    app_webhook_secret: str
    service_area_zips: list[str]
    business_name: str
    business_phone: str


class CalcomConfig(BaseModel):
    """Per-tenant Cal.com configuration. Stored encrypted in tenant_configs.calcom_config."""
    calcom_api_key: str
    calcom_event_type_id: int
    calcom_username: str
    calcom_timezone: str


# --- Retell webhook models ---

class RetellToolCallRequest(BaseModel):
    """Incoming Retell tool call webhook payload.

    Retell sends one request per tool call. The `args` field contains
    tool-specific arguments as a dict. We validate loosely (spec finding #4)
    because Retell is a trusted upstream — don't punish callers for Retell quirks.
    """
    call_id: str = Field(alias="call_id")
    tool_name: str | None = None
    args: dict = Field(default_factory=dict)
    # Retell includes custom_metadata from agent config
    metadata: dict = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Retell may add fields we don't know about

    # NOTE: Use a LooseModel base class with a @model_validator(mode="before")
    # that logs unexpected fields at WARNING level. This makes the deviation
    # from StrictModel explicit and auditable. See eng review Issue 2.


class RetellCallEndedPayload(BaseModel):
    """Incoming Retell call-ended webhook payload.

    Contains the full call transcript and tool call results.
    We persist the entire raw payload before extracting fields.
    """
    call_id: str
    transcript: str = ""
    transcript_object: list[dict] = Field(default_factory=list)
    call_summary: str | None = None
    custom_metadata: dict = Field(default_factory=dict)
    call_analysis: dict = Field(default_factory=dict)
    from_number: str | None = None
    to_number: str | None = None
    direction: str | None = None
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    duration_ms: int | None = None
    recording_url: str | None = None
    disconnection_reason: str | None = None
    # v10 dynamic variables collected during call
    dynamic_variables: dict = Field(default_factory=dict, alias="retell_llm_dynamic_variables")
    # Tool call results (includes book_service results from CallLock App)
    tool_call_results: list[dict] = Field(default_factory=list)

    class Config:
        extra = "allow"
        populate_by_name = True


# --- Event payload ---

class CallEndedEvent(BaseModel):
    """Inngest event payload for calllock/call.ended.

    Separate from ProcessCallRequest (which uses StrictModel with extra=forbid).
    The process-voice-call Inngest function maps this to ProcessCallRequest.
    """
    tenant_id: str
    call_id: str
    call_source: Literal["retell"] = "retell"
    phone_number: str
    transcript: str
    # Extracted fields (None if extraction failed for that field)
    customer_name: str | None = None
    service_address: str | None = None
    problem_description: str | None = None
    urgency_tier: UrgencyTier
    caller_type: CallerType
    primary_intent: PrimaryIntent
    revenue_tier: RevenueTier
    tags: list[str]
    quality_score: float
    scorecard_warnings: list[str]
    # Routing
    route: Literal["legitimate", "spam", "vendor", "recruiter"]
    # Booking state
    booking_id: str | None = None
    callback_scheduled: bool = False
    # Extraction metadata
    extraction_status: Literal["complete", "partial"]
    # Raw Retell data
    retell_call_id: str
    call_duration_seconds: int
    end_call_reason: str
    call_recording_url: str | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add harness/src/voice/__init__.py harness/src/voice/models.py \
  harness/tests/voice/__init__.py harness/tests/voice/test_models.py
git commit -m "feat(voice): add Pydantic models — VoiceConfig, CallEndedEvent, RetellToolCallRequest"
```

### Task 3: HMAC Auth + API Key Auth

**Files:**
- Create: `harness/src/voice/auth.py`
- Create: `harness/tests/voice/test_auth.py`

- [ ] **Step 1: Write auth tests**

```python
# harness/tests/voice/test_auth.py
import hashlib
import hmac
import time

import pytest

from voice.auth import verify_retell_hmac, verify_api_key, HMACVerificationError, InvalidAPIKeyError


class TestRetellHMAC:
    def test_valid_signature(self, monkeypatch):
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
        body = b'{"call_id": "123"}'
        timestamp = str(int(time.time()))
        message = timestamp.encode() + b"." + body
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()
        # Should not raise
        verify_retell_hmac(body, signature, timestamp)

    def test_invalid_signature_raises(self, monkeypatch):
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
        with pytest.raises(HMACVerificationError):
            verify_retell_hmac(b"body", "bad-sig", str(int(time.time())))

    def test_expired_timestamp_raises(self, monkeypatch):
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
        old_ts = str(int(time.time()) - 600)  # 10 minutes ago
        body = b"body"
        message = old_ts.encode() + b"." + body
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()
        with pytest.raises(HMACVerificationError, match="expired"):
            verify_retell_hmac(body, signature, old_ts)

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("RETELL_WEBHOOK_SECRET", raising=False)
        with pytest.raises(Exception):
            verify_retell_hmac(b"body", "sig", str(int(time.time())))


class TestAPIKeyAuth:
    def test_valid_key(self):
        """API key auth checks SHA-256 hash against stored hash."""
        plaintext_key = "test-api-key-12345"
        stored_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        # Mock DB lookup returning this hash + tenant_id
        result = verify_api_key(
            provided_key=plaintext_key,
            stored_records=[{"api_key_hash": stored_hash, "tenant_id": "t-1", "revoked_at": None}],
        )
        assert result == "t-1"

    def test_revoked_key_rejected(self):
        plaintext_key = "test-api-key-12345"
        stored_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(
                provided_key=plaintext_key,
                stored_records=[{"api_key_hash": stored_hash, "tenant_id": "t-1", "revoked_at": "2026-01-01"}],
            )

    def test_unknown_key_rejected(self):
        with pytest.raises(InvalidAPIKeyError):
            verify_api_key(provided_key="unknown", stored_records=[])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/test_auth.py -v`
Expected: ImportError

- [ ] **Step 3: Implement auth module**

```python
# harness/src/voice/auth.py
"""Authentication for voice webhooks and booking API.

Two auth mechanisms, exposed as FastAPI Depends() functions:
1. require_retell_hmac — verifies Retell webhook HMAC-SHA256 signatures
2. require_api_key — verifies booking API keys from CallLock App

Usage in routers:
  @voice_router.post("/lookup_caller", dependencies=[Depends(require_retell_hmac)])
  @booking_router.get("/lookup", dependencies=[Depends(require_api_key)])
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time


class HMACVerificationError(Exception):
    """Retell webhook signature verification failed."""


class InvalidAPIKeyError(Exception):
    """Booking API key is invalid, revoked, or unknown."""


# Timestamp tolerance: 5 minutes
_TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_retell_hmac(body: bytes, signature: str, timestamp: str) -> None:
    """Verify Retell webhook HMAC-SHA256 signature.

    Retell signs webhooks with: HMAC-SHA256(secret, timestamp + "." + body)
    The signature and timestamp arrive as headers.

    Raises HMACVerificationError if verification fails.
    """
    secret = os.environ.get("RETELL_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("RETELL_WEBHOOK_SECRET environment variable is not set")

    # Check timestamp freshness
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise HMACVerificationError("Invalid timestamp format")

    age = abs(time.time() - ts)
    if age > _TIMESTAMP_TOLERANCE_SECONDS:
        raise HMACVerificationError(f"Timestamp expired: {age:.0f}s old (max {_TIMESTAMP_TOLERANCE_SECONDS}s)")

    # Compute expected signature
    message = timestamp.encode() + b"." + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HMACVerificationError("HMAC signature mismatch")


def verify_api_key(provided_key: str, stored_records: list[dict]) -> str:
    """Verify a booking API key and return the associated tenant_id.

    Uses timing-safe comparison of SHA-256 hashes.

    Args:
        provided_key: The plaintext API key from X-API-Key header.
        stored_records: List of dicts with api_key_hash, tenant_id, revoked_at.

    Returns:
        tenant_id associated with the key.

    Raises:
        InvalidAPIKeyError if key is unknown or revoked.
    """
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()

    for record in stored_records:
        if hmac.compare_digest(record["api_key_hash"], provided_hash):
            if record.get("revoked_at") is not None:
                raise InvalidAPIKeyError("API key has been revoked")
            return record["tenant_id"]

    raise InvalidAPIKeyError("Unknown API key")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/test_auth.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/auth.py harness/tests/voice/test_auth.py
git commit -m "feat(voice): add HMAC + API key authentication"
```

### Task 4: VoiceConfig Resolution + Caching

**Files:**
- Create: `harness/src/voice/config.py`
- Create: `harness/tests/voice/test_config.py`

- [ ] **Step 1: Write config resolution tests**

```python
# harness/tests/voice/test_config.py
import json
import pytest
from unittest.mock import patch, MagicMock

from voice.config import resolve_voice_config, VoiceConfigError
from voice.models import VoiceConfig


class TestResolveVoiceConfig:
    def test_cache_hit(self):
        """Returns cached config without DB query."""
        cached = json.dumps({
            "twilio_account_sid": "AC123",
            "twilio_auth_token": "token",
            "twilio_from_number": "+15125551234",
            "twilio_owner_phone": "+15125555678",
            "app_webhook_url": "https://app.calllock.co",
            "app_webhook_secret": "secret",
            "service_area_zips": ["78701"],
            "business_name": "ACE",
            "business_phone": "+15125559999",
        })
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=cached)

        config = resolve_voice_config("tenant-1", redis_client=mock_redis)
        assert isinstance(config, VoiceConfig)
        assert config.business_name == "ACE"

    def test_cache_miss_fetches_db(self):
        """Fetches from DB on cache miss and populates cache."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        mock_redis.setex = MagicMock()

        db_config = {
            "twilio_account_sid": "AC123",
            "twilio_auth_token": "token",
            "twilio_from_number": "+15125551234",
            "twilio_owner_phone": "+15125555678",
            "app_webhook_url": "https://app.calllock.co",
            "app_webhook_secret": "secret",
            "service_area_zips": ["78701"],
            "business_name": "ACE",
            "business_phone": "+15125559999",
        }

        with patch("voice.config._fetch_voice_config_from_db", return_value=db_config):
            config = resolve_voice_config("tenant-1", redis_client=mock_redis)

        assert config.business_name == "ACE"
        mock_redis.setex.assert_called_once()

    def test_empty_config_raises(self):
        """Empty voice_config in DB raises VoiceConfigError."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)

        with patch("voice.config._fetch_voice_config_from_db", return_value={}):
            with pytest.raises(VoiceConfigError, match="missing required fields"):
                resolve_voice_config("tenant-1", redis_client=mock_redis)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/test_config.py -v`
Expected: ImportError

- [ ] **Step 3: Implement config resolution**

```python
# harness/src/voice/config.py
"""VoiceConfig resolution with Redis caching.

Fetches per-tenant voice config from tenant_configs, caches in Redis.
Cache key: t:{tenant_id}:voice:config (follows cache/keys.py pattern)
TTL: 5 minutes
"""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from voice.models import VoiceConfig, CalcomConfig

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes


class VoiceConfigError(Exception):
    """Voice configuration is missing or invalid for this tenant."""


def resolve_voice_config(
    tenant_id: str,
    *,
    redis_client=None,
    db_fetch=None,
) -> VoiceConfig:
    """Resolve VoiceConfig for a tenant, checking Redis cache first.

    Args:
        tenant_id: The tenant UUID from Retell call metadata.
        redis_client: Redis client instance (optional, for testing).
        db_fetch: Override DB fetch function (optional, for testing).

    Returns:
        Validated VoiceConfig.

    Raises:
        VoiceConfigError: If config is empty, missing, or invalid.
    """
    cache_key = f"t:{tenant_id}:voice:config"

    # Try cache
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug("voice.config_cache.hit", extra={"tenant_id": tenant_id})
                data = json.loads(cached)
                return VoiceConfig(**data)
        except Exception:
            logger.warning("voice.config_cache.error", extra={"tenant_id": tenant_id})

    logger.debug("voice.config_cache.miss", extra={"tenant_id": tenant_id})

    # Fetch from DB
    fetch_fn = db_fetch or _fetch_voice_config_from_db
    raw = await fetch_fn(tenant_id)

    if not raw:
        raise VoiceConfigError(f"Tenant {tenant_id}: voice_config is empty or missing required fields")

    try:
        config = VoiceConfig(**raw)
    except ValidationError as e:
        raise VoiceConfigError(f"Tenant {tenant_id}: voice_config missing required fields: {e}") from e

    # Populate cache
    if redis_client:
        try:
            redis_client.setex(cache_key, _CACHE_TTL_SECONDS, config.model_dump_json())
        except Exception:
            logger.warning("voice.config_cache.set_error", extra={"tenant_id": tenant_id})

    return config


def resolve_calcom_config(
    tenant_id: str,
    *,
    redis_client=None,
    db_fetch=None,
) -> CalcomConfig:
    """Resolve CalcomConfig for a tenant. Same caching pattern as VoiceConfig."""
    cache_key = f"t:{tenant_id}:calcom:config"

    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return CalcomConfig(**json.loads(cached))
        except Exception:
            pass

    fetch_fn = db_fetch or _fetch_calcom_config_from_db
    raw = await fetch_fn(tenant_id)

    if not raw:
        raise VoiceConfigError(f"Tenant {tenant_id}: calcom_config is empty")

    try:
        config = CalcomConfig(**raw)
    except ValidationError as e:
        raise VoiceConfigError(f"Tenant {tenant_id}: calcom_config invalid: {e}") from e

    if redis_client:
        try:
            redis_client.setex(cache_key, _CACHE_TTL_SECONDS, config.model_dump_json())
        except Exception:
            pass

    return config


def _fetch_voice_config_from_db(tenant_id: str) -> dict:
    """Fetch voice_config JSONB from tenant_configs via repository layer."""
    from db.repository import get_tenant_config
    result = get_tenant_config(tenant_id)
    return result.get("voice_config", {}) if result else {}


def _fetch_calcom_config_from_db(tenant_id: str) -> dict:
    """Fetch calcom_config JSONB from tenant_configs via repository layer."""
    from db.repository import get_tenant_config
    result = get_tenant_config(tenant_id)
    return result.get("calcom_config", {}) if result else {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/config.py harness/tests/voice/test_config.py
git commit -m "feat(voice): add VoiceConfig resolution with Redis caching"
```

### Task 4b: Credential Encryption (AES-256-GCM)

**Files:**
- Create: `harness/src/voice/crypto.py`
- Create: `harness/tests/voice/test_crypto.py`

The spec requires `VoiceConfig` and `CalcomConfig` JSONB to be encrypted at rest using AES-256-GCM. The encryption key comes from `VOICE_CREDENTIAL_KEY` env var. Key rotation: decrypt tries current key first, then `VOICE_CREDENTIAL_KEY_PREV`. This matches the inbound pipeline's `IMAP_CREDENTIAL_KEY` pattern.

- [ ] **Step 1: Write crypto tests**

```python
# harness/tests/voice/test_crypto.py
import os
import pytest
from voice.crypto import encrypt_config, decrypt_config, DecryptionError


class TestEncryptDecrypt:
    def test_round_trip(self, monkeypatch):
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        data = {"twilio_account_sid": "AC123", "twilio_auth_token": "secret"}
        encrypted = encrypt_config(data)
        assert encrypted != data  # not plaintext
        assert isinstance(encrypted, str)  # base64 string
        decrypted = decrypt_config(encrypted)
        assert decrypted == data

    def test_key_rotation(self, monkeypatch):
        old_key = os.urandom(32).hex()
        new_key = os.urandom(32).hex()
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", old_key)
        encrypted = encrypt_config({"key": "value"})
        # Rotate key
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", new_key)
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY_PREV", old_key)
        # Should decrypt with prev key
        decrypted = decrypt_config(encrypted)
        assert decrypted == {"key": "value"}

    def test_wrong_key_raises(self, monkeypatch):
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        encrypted = encrypt_config({"key": "value"})
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        monkeypatch.delenv("VOICE_CREDENTIAL_KEY_PREV", raising=False)
        with pytest.raises(DecryptionError):
            decrypt_config(encrypted)

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("VOICE_CREDENTIAL_KEY", raising=False)
        with pytest.raises(RuntimeError):
            encrypt_config({"key": "value"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/test_crypto.py -v`
Expected: ImportError

- [ ] **Step 3: Implement crypto module**

```python
# harness/src/voice/crypto.py
"""AES-256-GCM encryption for voice credential JSONB.

Credentials (Twilio tokens, Cal.com API keys, webhook secrets) are
encrypted before writing to tenant_configs JSONB columns and decrypted
on read. Key rotation: try current key, then VOICE_CREDENTIAL_KEY_PREV.
"""
import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(Exception):
    """Failed to decrypt credential JSONB with current or previous key."""


def _get_key(env_var: str = "VOICE_CREDENTIAL_KEY") -> bytes:
    hex_key = os.environ.get(env_var)
    if not hex_key:
        raise RuntimeError(f"{env_var} environment variable is not set")
    return bytes.fromhex(hex_key)


def encrypt_config(data: dict) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_config(encrypted: str) -> dict:
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]

    # Try current key
    try:
        key = _get_key()
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)
    except Exception:
        pass

    # Try previous key (rotation)
    prev_key_hex = os.environ.get("VOICE_CREDENTIAL_KEY_PREV")
    if prev_key_hex:
        try:
            prev_key = bytes.fromhex(prev_key_hex)
            aesgcm = AESGCM(prev_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext)
        except Exception:
            pass

    raise DecryptionError("Failed to decrypt with current or previous key")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/test_crypto.py -v`
Expected: All PASS

- [ ] **Step 5: Update config.py to use crypto**

Modify `voice/config.py`: the `_fetch_voice_config_from_db` function must call `decrypt_config()` on the raw JSONB value before passing to VoiceConfig validation.

- [ ] **Step 6: Commit**

```bash
git add harness/src/voice/crypto.py harness/tests/voice/test_crypto.py harness/src/voice/config.py
git commit -m "feat(voice): add AES-256-GCM credential encryption with key rotation"
```

### Task 4c: Test Conftest (Voice Fixtures)

**Files:**
- Create: `harness/tests/voice/conftest.py`

- [ ] **Step 1: Create conftest with shared fixtures**

```python
# harness/tests/voice/conftest.py
"""Shared fixtures for voice module tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from voice.models import VoiceConfig, CalcomConfig


@pytest.fixture
def mock_voice_config():
    return VoiceConfig(
        twilio_account_sid="AC_test_sid",
        twilio_auth_token="test_auth_token",
        twilio_from_number="+15125551234",
        twilio_owner_phone="+15125555678",
        app_webhook_url="https://app.calllock.co/api/webhook",
        app_webhook_secret="test_webhook_secret",
        service_area_zips=["78701", "78702", "78703"],
        business_name="ACE Cooling & Heating",
        business_phone="+15125559999",
    )


@pytest.fixture
def mock_calcom_config():
    return CalcomConfig(
        calcom_api_key="cal_live_test",
        calcom_event_type_id=12345,
        calcom_username="acecooling",
        calcom_timezone="America/Chicago",
    )


@pytest.fixture
def mock_retell_payload():
    """A realistic Retell call-ended webhook payload."""
    return {
        "call_id": "ret-call-001",
        "transcript": (
            "Agent: Thank you for calling ACE Cooling and Heating. "
            "User: Hi, my name is John Smith. My AC isn't cooling. "
            "I live at 123 Oak Street, Austin, TX 78701. "
            "It stopped working this morning."
        ),
        "transcript_object": [],
        "call_summary": "Customer reports AC not cooling at home.",
        "custom_metadata": {"tenant_id": "tenant-ace-001"},
        "from_number": "+15125550101",
        "to_number": "+15125559999",
        "direction": "inbound",
        "duration_ms": 120000,
        "recording_url": "https://retell.ai/recordings/ret-call-001.mp3",
        "disconnection_reason": "agent_hangup",
        "retell_llm_dynamic_variables": {
            "customer_name": "John Smith",
            "service_address": "123 Oak Street, Austin, TX 78701",
            "urgency_tier": "urgent",
            "booking_confirmed": "false",
        },
        "tool_call_results": [],
    }


@pytest.fixture
def mock_retell_tool_call_request():
    """A realistic Retell tool call webhook payload."""
    return {
        "call_id": "ret-call-001",
        "tool_name": "lookup_caller",
        "args": {"phone_number": "+15125550101"},
        "metadata": {"tenant_id": "tenant-ace-001"},
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client with async get/set."""
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.setex = MagicMock()
    return redis
```

- [ ] **Step 2: Verify conftest loads**

Run: `cd harness && python -c "import tests.voice.conftest"`
Expected: No error

- [ ] **Step 3: Commit**

```bash
git add harness/tests/voice/conftest.py
git commit -m "feat(voice): add test conftest with shared voice fixtures"
```

### Task 5: Add twilio dependency

**Files:**
- Modify: `harness/requirements.txt`

- [ ] **Step 1: Add twilio and cryptography to requirements**

Add to `harness/requirements.txt`:
- `twilio>=9.0` — Twilio SMS client for callback/sales lead/emergency alerts
- `cryptography>=42.0` — AES-256-GCM encryption for credential JSONB (Task 4b)

- [ ] **Step 2: Install and verify**

Run: `cd harness && pip install twilio>=9.0 cryptography>=42.0`
Expected: Successfully installed

- [ ] **Step 3: Commit**

```bash
git add harness/requirements.txt
git commit -m "feat(voice): add twilio dependency"
```

---

## Chunk 2: Extraction & Classification — Pure Functions

All extraction and classification logic is pure functions with no side effects. Port from V2 TypeScript to Python with exact test parity.

**Source files to port from:**
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/classification/tags.ts`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/extraction/urgency.ts`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/extraction/call-scorecard.ts`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/extraction/post-call.ts`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/extraction/hvac-issue.ts`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/classification/call-type.ts`

**Test files to port from:**
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/__tests__/extraction/`
- `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/__tests__/classification/`

### Task 6: HVAC Taxonomy YAML

**Files:**
- Create: `knowledge/industry-packs/hvac/taxonomy.yaml`
- Create: `knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml`

- [ ] **Step 1: Port 117-tag taxonomy from V2 tags.ts to YAML**

Read `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/classification/tags.ts` and extract all 117 tag definitions into structured YAML. Each tag needs: name, category, patterns (list of match strings), and whether it uses word-boundary matching (single words) or substring matching (multi-word phrases).

The YAML file must have standard knowledge node frontmatter per CLAUDE.md.

- [ ] **Step 2: Validate taxonomy YAML**

Write a quick validation script that loads the YAML and asserts:
- Exactly 9 categories exist (HAZARD, URGENCY, SERVICE_TYPE, REVENUE, RECOVERY, LOGISTICS, CUSTOMER, NON_CUSTOMER, CONTEXT)
- Total tag count across all categories is 117
- Each tag has `name` and `patterns` fields
- No duplicate tag names

Run: `cd harness && python -c "
import yaml
with open('../knowledge/industry-packs/hvac/taxonomy.yaml') as f:
    data = yaml.safe_load(f)
cats = data['categories']
assert len(cats) == 9, f'Expected 9 categories, got {len(cats)}'
total = sum(len(c['tags']) for c in cats)
assert total == 117, f'Expected 117 tags, got {total}'
names = [t['name'] for c in cats for t in c['tags']]
assert len(names) == len(set(names)), 'Duplicate tag names found'
print(f'OK: 9 categories, {total} tags, no duplicates')
"`
Expected: `OK: 9 categories, 117 tags, no duplicates`

- [ ] **Step 3: Port v10 agent config to YAML**

Read `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/voice-agent/retell-llm-v10-simplified.json` and convert to YAML with knowledge node frontmatter. Strip any secrets. Include: states, edges, tool definitions, prompts.

- [ ] **Step 4: Create _moc.md files**

Create `knowledge/industry-packs/hvac/voice/_moc.md` linking to `retell-agent-v10.yaml`. Update `knowledge/industry-packs/hvac/_moc.md` (if it exists) to include links to `taxonomy.yaml` and `voice/`. Per CLAUDE.md: "Each knowledge directory with child nodes must expose an `_moc.md` file."

- [ ] **Step 5: Commit**

```bash
git add knowledge/industry-packs/hvac/taxonomy.yaml \
  knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml \
  knowledge/industry-packs/hvac/voice/_moc.md \
  knowledge/industry-packs/hvac/_moc.md
git commit -m "feat(voice): add HVAC taxonomy YAML (117 tags) and v10 agent config"
```

### Task 7: Tag Classification Engine

**Files:**
- Create: `harness/src/voice/extraction/__init__.py`
- Create: `harness/src/voice/extraction/tags.py`
- Create: `harness/tests/voice/extraction/__init__.py`
- Create: `harness/tests/voice/extraction/test_tags.py`

- [ ] **Step 1: Write tag classification tests**

Port every test case from V2 `__tests__/classification/tags.test.ts` to pytest parametrized fixtures. The tests MUST produce identical results to V2 — this is the regression safety net.

Key test cases:
- Basic tag matching (single word, multi-word)
- Negation awareness ("no gas leak" should NOT match GAS_LEAK)
- Word boundary matching ("ice" should NOT match inside "service")
- Multiple tags from same transcript
- Empty transcript returns empty list
- All 9 categories produce expected tags

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/extraction/test_tags.py -v`

- [ ] **Step 3: Implement tag engine**

The tag engine loads `knowledge/industry-packs/hvac/taxonomy.yaml` at import time and raises `ImportError` if missing/malformed. Algorithm:
1. Load tags from YAML grouped by category
2. For each tag pattern, check transcript (lowercased)
3. Multi-word phrases: substring match
4. Single words: word-boundary regex (`\b{word}\b`)
5. Negation check: look 40 chars before match for "no", "not", "never", "don't", "isn't"
6. Return list of matched tag names

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/extraction/test_tags.py -v`
Expected: All PASS, exact parity with V2

- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/extraction/ harness/tests/voice/extraction/
git commit -m "feat(voice): add 117-tag taxonomy engine with negation-aware matching"
```

### Task 8: Urgency Inference

**Files:**
- Create: `harness/src/voice/extraction/urgency.py`
- Create: `harness/tests/voice/extraction/test_urgency.py`

- [ ] **Step 1: Write urgency tests**

Port all 11 test cases from V2 `__tests__/extraction/urgency.test.ts`:
- Emergency: gas leak, CO, fire, smoke, sparking, flood
- Urgent: water leak, no heat, no AC, ASAP
- Estimate: quote, how much, no rush, flexible
- Routine: maintenance, tune-up (default)
- Combined problem description + transcript

- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement urgency inference**

Port regex patterns from V2 `extraction/urgency.ts`. Return `UrgencyTier` enum.

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/extraction/urgency.py harness/tests/voice/extraction/test_urgency.py
git commit -m "feat(voice): add urgency inference (Emergency/Urgent/Routine/Estimate)"
```

### Task 9: Post-Call Extraction

**Files:**
- Create: `harness/src/voice/extraction/post_call.py`
- Create: `harness/tests/voice/extraction/test_post_call.py`

- [ ] **Step 1: Write extraction tests**

Port from V2 `__tests__/extraction/post-call.test.ts` (7 test groups):
- `extract_customer_name`: filters agent lines, detects "my name is", "I'm", "this is"
- `extract_safety_emergency`: gas leak, CO, fire, sparking, flooding
- `extract_address`: regex for street addresses
- `extract_problem_duration`: acute/recent/ongoing categorization
- `map_disconnection_reason`: Retell reason → EndCallReason enum

- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement extraction functions**

Port from V2 `extraction/post-call.ts`. All functions are pure — take transcript string, return extracted value or None.

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/extraction/post_call.py harness/tests/voice/extraction/test_post_call.py
git commit -m "feat(voice): add post-call extraction (name, address, safety, duration)"
```

### Task 10: Call Scorecard

**Files:**
- Create: `harness/src/voice/extraction/call_scorecard.py`
- Create: `harness/tests/voice/extraction/test_call_scorecard.py`

- [ ] **Step 1: Write scorecard tests**

Port 10 test cases from V2 `__tests__/extraction/call-scorecard.test.ts`:
- Zero score for empty state
- Full score (100) for complete state
- Partial scoring
- Warning: zero-tags, callback-gap

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/extraction/test_call_scorecard.py -v`
Expected: ImportError

- [ ] **Step 3: Implement scorecard**

Weights: name(15) + phone(15) + address(15) + problem(15) + urgency(10) + booking/callback(20) + tags(10) = 100

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/extraction/test_call_scorecard.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/extraction/call_scorecard.py harness/tests/voice/extraction/test_call_scorecard.py
git commit -m "feat(voice): add call scorecard (0-100 weighted scoring)"
```

### Task 11: HVAC Issue Type + Call Type + Revenue + Traffic

**Files:**
- Create: `harness/src/voice/extraction/hvac_issue.py`
- Create: `harness/src/voice/classification/__init__.py`
- Create: `harness/src/voice/classification/call_type.py`
- Create: `harness/src/voice/classification/revenue.py`
- Create: `harness/src/voice/classification/traffic.py`
- Create: `harness/tests/voice/extraction/test_hvac_issue.py`
- Create: `harness/tests/voice/classification/__init__.py`
- Create: `harness/tests/voice/classification/test_call_type.py`
- Create: `harness/tests/voice/classification/test_revenue.py`
- Create: `harness/tests/voice/classification/test_traffic.py`

- [ ] **Step 1: Write tests for all 4 modules**

Port from V2 test fixtures. Traffic controller test cases:
- Residential + service → legitimate
- Job applicant → vendor
- Spam → spam
- Unknown + unknown → legitimate (safe default)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/extraction/test_hvac_issue.py tests/voice/classification/ -v`
Expected: ImportError

- [ ] **Step 3: Implement all 4 modules**

Port from V2 source files:
- `extraction/hvac-issue.ts` → `extraction/hvac_issue.py`
- `classification/call-type.ts` → `classification/call_type.py`
- Revenue tier logic from `services/dashboard.ts` → `classification/revenue.py`
- Traffic controller from V3 pattern → `classification/traffic.py`

Note: `extract_problem_duration()` output (acute/recent/ongoing) goes into `call_records.extracted_fields` JSONB, not into `CallEndedEvent`. The pipeline runner stores it in extracted_fields for the CallLock App sync payload to use.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/extraction/test_hvac_issue.py tests/voice/classification/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/extraction/hvac_issue.py \
  harness/src/voice/classification/ \
  harness/tests/voice/extraction/test_hvac_issue.py \
  harness/tests/voice/classification/
git commit -m "feat(voice): add HVAC issue type, call type, revenue tier, traffic controller"
```

### Task 12: Extraction Pipeline Runner

**Files:**
- Modify: `harness/src/voice/extraction/__init__.py`

- [ ] **Step 1: Write pipeline runner test**

Test that `run_extraction()` calls all extraction/classification functions and handles partial failures gracefully.

- [ ] **Step 2: Implement pipeline runner**

```python
# harness/src/voice/extraction/__init__.py
"""Extraction pipeline — runs all extraction and classification steps.

If any step throws, the pipeline catches it, logs the error,
and continues with remaining steps. Returns extraction_status='partial'
if any step failed.
"""
```

The runner takes `transcript: str` and `raw_payload: dict` and returns a dict with all extracted fields plus `extraction_status`.

- [ ] **Step 3: Run all extraction tests**

Run: `cd harness && python -m pytest tests/voice/extraction/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add harness/src/voice/extraction/__init__.py harness/tests/voice/extraction/
git commit -m "feat(voice): add extraction pipeline runner with partial failure handling"
```

---

## Chunk 3: Twilio SMS Service + Tool Handlers

### Task 13: Twilio SMS Service

**Files:**
- Create: `harness/src/voice/services/__init__.py`
- Create: `harness/src/voice/services/twilio_sms.py`
- Create: `harness/tests/voice/test_twilio_sms.py`

- [ ] **Step 1: Write SMS service tests**

Test cases:
- Successful send returns SID
- Twilio error is caught and logged (returns None, doesn't raise)
- Phone number masking in logs
- Template-based SMS content (no raw user input in body — spec finding #5)
- Callback SMS format matches V2
- Sales lead SMS format matches V2

- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement SMS service**

Port from V2 `services/alerts.ts`. Use `twilio` Python SDK instead of raw HTTP. Two fixed templates:

```
CALLBACK: "{business_name} callback request\nCaller: {phone}\nReason: {reason}\nCallback within {minutes} min"
SALES_LEAD: "SALES LEAD: {equipment}\nCustomer: {name}\nPhone: {phone}\nAddress: {address}"
EMERGENCY: "URGENT: {description}\nCaller: {phone}\nAddress: {address}"
```

Sanitize `reason` field: truncate to 200 chars, strip non-printable characters.

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

```bash
git add harness/src/voice/services/ harness/tests/voice/test_twilio_sms.py
git commit -m "feat(voice): add Twilio SMS service with template-based messages"
```

### Task 14: lookup_caller Tool Handler

**Files:**
- Create: `harness/src/voice/tools/__init__.py`
- Create: `harness/src/voice/tools/lookup_caller.py`
- Create: `harness/tests/voice/test_lookup_caller.py`

- [ ] **Step 1: Write lookup_caller tests**

Test cases:
- Found caller with history → returns jobs, calls, bookings
- New caller → returns `{found: false}`
- DB timeout → returns `{found: false}` (graceful degradation)
- Results limited to 10 jobs, 5 calls, 5 bookings (spec finding #20)

- [ ] **Step 2-5: TDD cycle + commit**

```bash
git commit -m "feat(voice): add lookup_caller tool handler"
```

### Task 15: create_callback + send_sales_lead_alert Tool Handlers

**Files:**
- Create: `harness/src/voice/tools/create_callback.py`
- Create: `harness/src/voice/tools/sales_lead_alert.py`
- Create: `harness/tests/voice/test_create_callback.py`
- Create: `harness/tests/voice/test_sales_lead_alert.py`

- [ ] **Step 1: Write tests for both handlers**

Test cases per handler:
- Successful SMS send → returns success to Retell
- Twilio failure → returns success to Retell anyway, logs error
- VoiceConfig missing → returns graceful error message

- [ ] **Step 2-5: TDD cycle**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(voice): add create_callback and send_sales_lead_alert tool handlers"
```

---

## Chunk 4: FastAPI Routers + Post-Call Pipeline

### Task 16: Voice Tool Router

**Files:**
- Create: `harness/src/voice/router.py`
- Modify: `harness/src/harness/server.py` (add include_router)

- [ ] **Step 1: Write router integration test**

Test that POST to `/webhook/retell/lookup_caller` with valid HMAC returns expected response.

- [ ] **Step 2: Implement voice_router**

```python
# harness/src/voice/router.py
"""FastAPI router for Retell tool call webhooks.

Each tool has a dedicated endpoint (per-tool URLs, not a dispatcher).
Auth: Retell HMAC-SHA256 verification via middleware.
"""
```

Three endpoints:
- `POST /lookup_caller`
- `POST /create_callback`
- `POST /send_sales_lead_alert`

Each extracts `tenant_id` from `request.metadata.tenant_id`, resolves VoiceConfig, executes tool handler, returns JSON.

- [ ] **Step 3: Mount on server.py**

Add to `harness/src/harness/server.py`:
```python
from voice.router import voice_router
from voice.post_call_router import post_call_router
from voice.booking_router import booking_router

app.include_router(voice_router, prefix="/webhook/retell")
app.include_router(post_call_router, prefix="/webhook/retell")
app.include_router(booking_router, prefix="/api/bookings")
```

This is the FIRST use of `include_router` in the codebase (spec finding #14).

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(voice): add voice tool router + mount on server.py (first include_router)"
```

### Task 17: Repository Layer — Voice CRUD

**IMPORTANT:** This task MUST be completed before Task 18 (post-call router), which depends on these repository operations.

**Files:**
- Modify: `harness/src/db/repository.py`
- Modify: `harness/src/db/supabase_repository.py`
- Modify: `harness/src/db/local_repository.py`

- [ ] **Step 1: Write repository tests**

Test cases for new operations:
- `insert_call_record(tenant_id, call_id, retell_call_id, raw_payload)` → creates row
- `update_call_record_extraction(tenant_id, call_id, extracted_fields)` → updates row
- `get_caller_history(tenant_id, phone)` → returns jobs/calls/bookings with LIMIT
- `set_call_synced(tenant_id, call_id)` → sets synced_to_app = true
- `get_unsynced_calls(tenant_id, min_age_hours, max_age_days)` → returns unsynced rows
- `get_voice_api_keys()` → returns all non-revoked keys
- Duplicate insert (same tenant_id + call_id) → raises or returns None

- [ ] **Step 2: Add operations to repository.py facade**
- [ ] **Step 3: Implement in supabase_repository.py with tenant scoping**
- [ ] **Step 4: Implement in local_repository.py with in-memory fallback**
- [ ] **Step 5: Run tests**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(voice): add voice CRUD to repository layer (call_records, voice_api_keys)"
```

### Task 18: Post-Call Router + Pipeline

**Files:**
- Create: `harness/src/voice/post_call_router.py`

**Depends on:** Task 12 (extraction pipeline runner), Task 17 (repository CRUD)

- [ ] **Step 1: Write post-call handler test**

Test the full synchronous pipeline:
1. HMAC verification
2. Raw payload persist to call_records
3. Extraction pipeline runs
4. call_records updated with extracted fields
5. Inngest event fired

Test partial extraction: one extraction step throws, others succeed, event fires with `extraction_status: 'partial'`.

Test duplicate call: same call_id → skip, return 200.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/voice/test_post_call_router.py -v`
Expected: ImportError

- [ ] **Step 3: Implement post-call router**

```python
# harness/src/voice/post_call_router.py
"""FastAPI router for Retell call-ended webhook.

Synchronous pipeline (<2s):
1. Verify HMAC
2. Extract tenant_id
3. Generate call_id, persist raw payload
4. Run extraction pipeline
5. Update call_records with extracted fields
6. Fire Inngest calllock/call.ended event
7. Return 200
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/voice/test_post_call_router.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(voice): add post-call router with extraction pipeline"
```

---

## Chunk 5: CallLock App Sync + Booking Management

### Task 19: CallLock App Webhook Sync Service

**Files:**
- Create: `harness/src/voice/services/app_sync.py`
- Create: `harness/tests/voice/test_app_sync.py`

- [ ] **Step 1: Write sync tests**

Test cases:
- Transforms CallEndedEvent to dashboard payload format (must match V2's DashboardJobPayload)
- Signs payload with HMAC using app_webhook_secret
- Successful POST returns True
- 5xx response raises for Inngest retry
- Payload includes all V2 fields: customer_name, urgency, tags, revenue_tier, booking_status, etc.

Reference V2 payload structure: `/Users/rashidbaset/conductor/workspaces/retellai-calllock/valencia/V2/src/services/dashboard.ts`

- [ ] **Step 2: Create golden fixture from V2**

Extract a real `DashboardJobPayload` from V2 test fixtures or capture one from the V2 test suite. Save as `harness/tests/voice/fixtures/golden_dashboard_payload.json`. Add a test that runs `app_sync.transform_to_dashboard_payload()` with the same input and asserts the output matches the golden fixture field-for-field.

- [ ] **Step 3: Implement sync service**

Port the `transformToDashboardPayload()` function from V2 `services/dashboard.ts`. The payload format must be compatible with what the CallLock App expects. Use the `DashboardPayload` Pydantic model from `models.py` to validate the output.

- [ ] **Step 4: Run tests including golden fixture**

Run: `cd harness && python -m pytest tests/voice/test_app_sync.py -v`
Expected: All PASS, including golden fixture comparison

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(voice): add CallLock App webhook sync service"
```

### Task 20: Cal.com Service + Booking Router

**Files:**
- Create: `harness/src/voice/services/calcom.py`
- Create: `harness/src/voice/booking_router.py`
- Create: `harness/tests/voice/test_calcom.py`
- Create: `harness/tests/voice/test_booking_router.py`

- [ ] **Step 1: Write Cal.com service tests**

Test cases:
- lookup by phone → returns bookings
- cancel by UID → returns success
- reschedule by UID + new time → returns success
- Cal.com timeout → raises (propagates to caller)
- Cal.com 429 → raises (propagates to caller)

- [ ] **Step 2: Implement Cal.com service**

Uses httpx to call Cal.com v2 API. Credentials from CalcomConfig.

- [ ] **Step 3: Write booking router tests**

Test cases:
- Valid API key → 200 with data
- Invalid API key → 401
- Revoked API key → 401
- E.164 phone validation
- ISO 8601 datetime validation

- [ ] **Step 4: Implement booking router**

Three endpoints with API key auth:
- `GET /lookup?phone={phone}`
- `POST /cancel`
- `POST /reschedule`

- [ ] **Step 5: Run all tests**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(voice): add Cal.com service + booking management REST API"
```

---

## Chunk 6: Inngest Events + Functions

### Task 21: Inngest Event Schema

**Files:**
- Modify: `inngest/src/events/schemas.ts`

- [ ] **Step 1: Add all 3 event schemas**

Add to existing `inngest/src/events/schemas.ts`:
- `CallEndedPayload` interface matching Python `CallEndedEvent` fields
- `validateCallEndedPayload()` validation function
- Event name constants:
  - `CALL_ENDED = "calllock/call.ended"` — main post-call event
  - `CALL_APP_SYNC = "calllock/call.app.sync"` — CallLock App webhook delivery
  - `CALL_EMERGENCY_SMS = "calllock/call.emergency.sms"` — conditional emergency SMS

Follow existing patterns (ProcessCallPayload, JobCompletePayload).

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd inngest && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add inngest/src/events/schemas.ts
git commit -m "feat(voice): add 3 Inngest event schemas (call.ended, app.sync, emergency.sms)"
```

### Task 22: Inngest Functions

**Files:**
- Create: `inngest/src/functions/voice.ts`
- Create: `inngest/src/__tests__/voice.test.ts`

- [ ] **Step 1: Write tests for Inngest functions**

Test cases:
- `process-voice-call`: maps `CallEndedEvent` to `ProcessCallRequest` — verify `call_metadata` field name (NOT `metadata` — spec finding #13), verify `extra=forbid` won't reject the payload
- `send-emergency-sms`: only fires when safety emergency is flagged in extraction, idempotency key format is `{tenant_id}:{call_id}:emergency-sms`
- `sync-app`: sets `synced_to_app = true` on success, does NOT set on failure (triggers Inngest retry)

- [ ] **Step 2: Implement 5 Inngest functions**

```typescript
// inngest/src/functions/voice.ts
// 1. process-voice-call: maps CallEndedEvent → ProcessCallRequest, calls /process-call
// 2. sync-app: transforms payload, POSTs to CallLock App webhook
// 3. send-emergency-sms: conditional safety SMS via Twilio (idempotency key)
// 4. app-sync-retry: daily cron for unsynced call_records (1h-7d old)
// 5. call-records-retention: weekly cron for transcript purge + row deletion
```

All event-driven functions subscribe to `calllock/call.ended` except the crons.

Key: `process-voice-call` maps `CallEndedEvent` to `ProcessCallRequest` using `call_metadata` (not `metadata` — spec finding #13).

- [ ] **Step 3: Run tests**

Run: `cd inngest && npx vitest run src/__tests__/voice.test.ts`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add inngest/src/functions/voice.ts inngest/src/__tests__/voice.test.ts
git commit -m "feat(voice): add 5 Inngest functions (process, sync, emergency SMS, retry, retention)"
```

---

## Chunk 7: Integration Test + Health Check + Final Verification

### Task 23: Pipeline Integration Test (The 2am Friday Test)

**Files:**
- Create: `harness/tests/voice/test_post_call_pipeline.py`

- [ ] **Step 1: Write the integration test**

One test that fires a realistic Retell call-ended payload at the FastAPI endpoint and asserts:
1. `call_records` row created with correct `extraction_status: 'complete'`
2. Inngest event fired with correct `CallEndedEvent` schema
3. CallLock App webhook payload (captured via mock HTTP server) matches expected format

Uses:
- Real extraction pipeline (not mocked)
- Mock Inngest client (captures fired events)
- Mock HTTP server for CallLock App webhook (captures payload)
- Mock Redis for VoiceConfig cache

This is the single test that proves the full pipeline works.

- [ ] **Step 2: Run the integration test**

Run: `cd harness && python -m pytest tests/voice/test_post_call_pipeline.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(voice): add pipeline integration test (2am Friday confidence test)"
```

### Task 24: Health Check Extension

**Files:**
- Modify: `harness/src/harness/server.py`

- [ ] **Step 1: Extend /health/detailed**

Add two connectivity checks alongside existing Supabase check:
- Cal.com: `HEAD https://api.cal.com` (spec Section 8)
- Twilio: `HEAD https://api.twilio.com`

These are connectivity checks, not per-tenant credential checks — credential validity is verified on first use per call.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(voice): extend health check with Twilio connectivity"
```

### Task 25: Run Full Test Suite

- [ ] **Step 1: Run all voice tests**

Run: `cd harness && python -m pytest tests/voice/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run existing harness tests (regression check)**

Run: `cd harness && python -m pytest tests/ -v --tb=short --ignore=tests/voice/`
Expected: All existing tests still PASS (voice module didn't break anything)

- [ ] **Step 3: Final commit if any fixes needed**

---

## Dependency Graph

```
Task 1 (migration)
  └→ Task 2 (models) ──────────────────────────────────┐
      └→ Task 3 (auth) ────────────────────────────────┤
      └→ Task 4 (config) ──────────────────────────────┤
      └→ Task 4b (crypto) ◄── Task 4 ─────────────────┤
      └→ Task 4c (conftest) ◄── Task 2 ───────────────┤
      └→ Task 5 (twilio dep) ──────────────────────────┤
                                                        │
Task 6 (taxonomy YAML + validate) ─────────────────────┤
  └→ Task 7 (tag engine) ─────────┐                    │
  └→ Task 8 (urgency) ────────────┤                    │
  └→ Task 9 (post-call extract) ──┤                    │
  └→ Task 10 (scorecard) ─────────┤                    │
  └→ Task 11 (issue/type/rev/traffic) ┤               │
      └→ Task 12 (pipeline runner) ────┘               │
                                                        │
Task 13 (twilio sms) ──────────────────────────────────┤
  └→ Task 14 (lookup_caller) ──────────────────────────┤
  └→ Task 15 (callback + sales alert) ─────────────────┤
                                                        │
Task 16 (voice router + mount) ◄───────────────────────┘
  └→ Task 17 (repository CRUD) ◄── Task 1
  └→ Task 18 (post-call router) ◄── Task 12, Task 17

Task 19 (app sync) ◄── Task 2
Task 20 (calcom + booking router) ◄── Task 3, Task 4

Task 21 (Inngest schemas — all 3) ── independent
Task 22 (Inngest functions + tests) ◄── Task 21

Task 23 (integration test) ◄── ALL above
Task 24 (health check — Cal.com + Twilio) ── independent
Task 25 (full suite) ◄── ALL above
```

**Parallelizable groups for Codex/Droid:**
- Group A (Foundation): Tasks 1, 2, 3, 4, 4b, 4c, 5 (sequential)
- Group B (Extraction): Tasks 6-12 (sequential, independent of Group A after Task 2)
- Group C (Tools): Tasks 13-15 (sequential, depends on Tasks 2+5)
- Group D (Inngest): Tasks 21-22 (TypeScript, fully independent)
- Group E (Integration): Tasks 16-20 (depends on Groups A-C). **Order within E: 16 → 17 → 18 → 19, 20**
- Group F (Verification): Tasks 23-25 (depends on all)

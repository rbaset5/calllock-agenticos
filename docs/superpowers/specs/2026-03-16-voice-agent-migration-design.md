# Voice Agent Migration Design

**Date:** March 16, 2026
**Status:** Draft
**Owner:** Founder
**Supersedes:** Architecture spec Section 0 ("Express V2 — evolves into part of the product core, not replaced"). Express V2 is now fully ported to Python and decommissioned.

## Summary

Port the Alexandria V2/V3 Express voice agent backend into rabat as a new `harness/src/voice/` Python package. Real-time Retell tool calls are handled by FastAPI endpoints on the same Render service. Post-call processing fires an Inngest event and fans out through existing harness infrastructure (growth memory, alerts, job dispatch). Multi-tenant from day one. Zero-downtime cutover by running both services in parallel during transition.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Migration target | Full port to Python | One runtime, one repo. Eliminates Node dependency. Rabat is the business OS. |
| Package location | `harness/src/voice/` | Peer to `harness/`, `growth/`, `inbound/`. Clean boundary, shared infrastructure. |
| Deployment | Same Render service | Voice routes mount on existing FastAPI app. No new infra to manage. |
| Source material | V2 logic + V3 patterns | V2 is battle-tested (39 files, Vitest suite, 117-tag taxonomy). V3's traffic controller is a cleaner routing pattern. |
| Real-time vs post-call | Split | Real-time tool calls stay synchronous in FastAPI. Post-call fires Inngest event for async fan-out. |
| Tenancy | Multi-tenant from day one | Rabat's repository layer enforces RLS. Fighting it for single-tenant would be more work. |
| Cal.com + Twilio | Keep as-is | Working integrations, no reason to change. |
| Dashboard | Same webhook contract | Dashboard stays on Vercel, receives same HMAC-signed payloads. |
| Taxonomy storage | YAML knowledge node | `knowledge/industry-packs/hvac/taxonomy.yaml`. Reusable by other industry packs. |
| Agent config storage | YAML knowledge node | `knowledge/industry-packs/hvac/voice/retell-agent-v9.yaml`. Versionable, no secrets. |
| Voice credential storage | New migration: `voice_config` JSONB column on `tenant_configs` | Existing `tenant_configs` (migration 002) has only named columns, no generic JSONB. New migration adds the column. |
| Retell webhook routing | Single URL dispatcher | Retell sends all tool calls to one webhook URL with tool name in request body. Router dispatches internally. |
| Call records persistence | New `call_records` table | Post-call data needs a home. New migration alongside voice config column. |
| HMAC secret | Global environment variable (`RETELL_WEBHOOK_SECRET`) | Retell uses a single API key for HMAC signing per account, not per-agent. |
| Conversation state | Stateless tool handlers | Retell passes relevant context in each tool call payload. No server-side session state needed. |

## 1. Architecture Overview

### Architectural boundary (updated)

The original architecture spec drew the boundary as: harness orchestrates everything except real-time voice conversation. This migration moves the boundary — the harness now also handles real-time voice tool execution. Retell AI remains the voice *conversation* runtime (LLM, FSM transitions, speech). The harness handles all webhook-driven work: tool calls, post-call processing, booking management.

```
  ┌─────────────────────────────────────────────────────┐
  │              AGENT HARNESS (LangGraph + FastAPI)      │
  │  Workers, Jobs, Policy, Eval, Improvement Lab         │
  │  Voice Tools, Post-Call Processing, Booking API        │
  └──────────────────────┬──────────────────────────────┘
                         │ orchestrates
  ┌──────────────────────┼──────────────────────────────┐
  │                      │                              │
  │  PRODUCT CORE        │    VOICE RUNTIME             │
  │  (Next.js Dashboard  │    (Retell AI v9-triage)     │
  │   + Supabase         │                              │
  │   + Cal.com          │    Handles: real-time calls,  │
  │   + Twilio)          │    15-state FSM, Claude 3.5   │
  │                      │    Haiku, speech synthesis     │
  └──────────────────────┴──────────────────────────────┘
```

### Runtime split

- **Retell AI:** Real-time voice conversation (LLM, state transitions, speech-to-text, text-to-speech)
- **Python (FastAPI):** All webhook handlers — tool calls, post-call extraction, booking REST API
- **TypeScript (Inngest):** Thin event proxies — `calllock/call.ended` triggers fan-out to harness endpoints
- **Supabase:** Persistence for call records, bookings, sessions, tenant configs

## 2. Package Structure

```
harness/src/voice/
├── __init__.py              # Public API exports
├── router.py                # FastAPI router: Retell webhook routes
├── booking_router.py        # FastAPI router: booking REST API
├── models.py                # Pydantic models (ConversationState, tool request/response)
├── auth.py                  # Retell HMAC-SHA256 verification + API key auth
├── tools/
│   ├── __init__.py
│   ├── service_area.py      # validate_service_area (ZIP lookup from tenant config)
│   ├── calendar.py          # check_calendar_availability (Cal.com slots)
│   ├── booking.py           # book_appointment (Cal.com create)
│   ├── customer_status.py   # get_customer_status (prior bookings lookup)
│   └── end_call.py          # end_call state finalization
├── services/
│   ├── __init__.py
│   ├── calcom.py            # Cal.com API client (availability, book, cancel, reschedule)
│   ├── twilio_sms.py        # Emergency SMS + sales lead alerts via Twilio
│   └── dashboard.py         # Dashboard webhook sync (payload transform, HMAC signing)
├── extraction/
│   ├── __init__.py
│   ├── post_call.py         # Name, address, safety extraction from transcript
│   ├── urgency.py           # Urgency inference from keywords
│   ├── call_scorecard.py    # Weighted quality scoring (0-100, 7 fields)
│   └── tags.py              # 117-tag taxonomy engine (loads from YAML, negation-aware)
└── classification/
    ├── __init__.py
    ├── call_type.py          # Urgency → urgencyTier + dashboard level mapping
    ├── revenue.py            # Revenue tier classification
    └── traffic.py            # Traffic controller: spam/vendor/legitimate routing
```

### Router mounting

```python
# In harness/src/harness/server.py
from voice.router import voice_router
from voice.booking_router import booking_router

app.include_router(voice_router, prefix="/webhook/retell")    # HMAC auth
app.include_router(booking_router, prefix="/api/bookings")    # API key auth
```

### Shared infrastructure (reused, not duplicated)

- `db/repository.py` + `db/tenant_scope.py` — all DB operations, RLS enforcement
- `observability/` — LangSmith tracing, PII redaction
- `cache/` — Redis key management

## 3. Real-Time Tool Call Flow

When Retell calls a tool mid-conversation, the request hits FastAPI directly. No Inngest, no queuing.

```
Caller speaks → Retell LLM decides to call tool
    → POST /webhook/retell/tool-call
    → auth.py verifies HMAC-SHA256 signature (global RETELL_WEBHOOK_SECRET env var)
    → dispatcher reads tool name from request body, routes to handler
    → tenant_scope.py sets RLS context from call metadata.tenant_id
    → tool handler executes (external API call or DB query)
    → returns JSON response to Retell
    → Retell LLM continues conversation
```

### Webhook routing

Retell sends all tool calls to a **single webhook URL** (`POST /webhook/retell/tool-call`) with the tool name and arguments in the request body. The router acts as a dispatcher:

```python
@voice_router.post("/tool-call")
async def handle_tool_call(request: RetellToolCallRequest):
    handler = TOOL_HANDLERS.get(request.tool_name)
    if not handler:
        return RetellToolResponse(error=f"Unknown tool: {request.tool_name}")
    return await handler(request)
```

Retell also sends a separate `POST /webhook/retell/call-ended` for the post-call webhook — this is a different endpoint, not a tool call.

### Tool handler pattern

Every tool handler follows the same structure:

1. **Auth** — Retell HMAC signature verification (middleware on `voice_router`)
2. **Tenant** — extract `tenant_id` from Retell's `custom_metadata`, set RLS context
3. **Config** — resolve `VoiceConfig` from `tenant_configs` (cached in Redis)
4. **Execute** — call external API or query DB
5. **Return** — JSON matching Retell's tool response schema

### Tool inventory

| Tool | External dependency | Latency budget | Notes |
|---|---|---|---|
| `validate_service_area` | DB lookup (`tenant_configs.service_area_zips`) | <100ms | Pure config lookup |
| `check_calendar_availability` | Cal.com `/slots/available` API | <1.5s | Respects urgency → date window |
| `book_appointment` | Cal.com booking API | <2s | Returns `appointmentId` + confirmation |
| `get_customer_status` | DB query (prior bookings by phone) | <200ms | Supabase query |
| `end_call` | None | <100ms | Finalizes conversation state |
| `send_emergency_sms` | Twilio SMS API | <1s | Fire-and-forget, life safety only |

### Error handling

If an external API fails (Cal.com down, Twilio timeout), the tool returns a graceful degradation response to Retell. Example: "I wasn't able to check the calendar right now. Let me take your number and have someone call you back." Tools never hang or throw — Retell would interpret silence as a tool failure and the caller hears dead air.

## 4. Post-Call Flow

When Retell fires the `call-ended` webhook, the voice module does minimal synchronous work and hands off to Inngest.

### Synchronous (in the webhook handler, <2s)

1. Verify HMAC signature
2. Extract `tenant_id` from call metadata
3. **Persist raw Retell payload** to `call_records` table immediately (before extraction). This ensures call data is never lost even if extraction fails.
4. Run extraction pipeline (pure functions, no external calls):
   - `post_call.py` — customer name, service address, safety flags from transcript
   - `urgency.py` — urgency inference from keywords
   - `tags.py` — 117-tag HVAC taxonomy classification
   - `call_scorecard.py` — quality score (0-100)
   - `call_type.py` — urgency tier + dashboard level mapping
   - `traffic.py` — traffic controller routing decision
5. **Update `call_records`** with extracted fields
6. Fire Inngest event `calllock/call.ended` with extracted payload
7. Return 200 to Retell

### Extraction failure handling

If any extraction step throws an exception, the handler catches it, logs the error, and still fires the Inngest event with whatever fields were successfully extracted (others default to `None`). The raw Retell payload is already persisted (step 3), so no data is lost. A `extraction_status: 'partial' | 'complete'` field on the event signals downstream consumers. The `call_records` row retains the raw payload for manual review or retry.

### Asynchronous (Inngest fan-out)

```
calllock/call.ended
  ├→ process-call          (existing) — harness orchestration, job dispatch
  ├→ sync-dashboard        (new)      — transform payload, POST to dashboard webhook
  ├→ evaluate-alerts       (existing) — emergency alert evaluation
  ├→ growth-touchpoint     (existing) — log call as growth touchpoint
  └→ send-emergency-sms    (new, conditional) — only if safety emergency flagged AND not already sent during call
```

### Emergency SMS deduplication

The `send_emergency_sms` tool can fire during the live call (real-time, via Retell tool call) AND the `send-emergency-sms` Inngest function can fire post-call (if safety flag is set). To prevent duplicate SMS:

- The real-time tool writes a `call_records.emergency_sms_sent_at` timestamp when it sends.
- The post-call Inngest function checks this field before sending. If already set, it skips.
- Idempotency key: `{tenant_id}:{call_id}:emergency-sms`

### Event payload schema

```python
class CallEndedEvent(BaseModel):
    tenant_id: str
    call_id: str
    call_source: Literal["retell"]
    phone_number: str
    transcript: str
    # Extracted fields
    customer_name: str | None
    service_address: str | None
    problem_description: str | None
    urgency_tier: UrgencyTier
    caller_type: CallerType
    primary_intent: PrimaryIntent
    revenue_tier: RevenueTier
    tags: list[str]
    quality_score: float
    scorecard_warnings: list[str]
    # Routing decision from traffic controller
    route: Literal["legitimate", "spam", "vendor", "recruiter"]
    # Booking state (needed by scorecard and dashboard)
    booking_id: str | None          # Cal.com booking UID if booked during call
    callback_scheduled: bool        # Whether a callback was promised
    # Extraction metadata
    extraction_status: Literal["complete", "partial"]
    # Raw Retell data
    retell_call_id: str
    call_duration_seconds: int
    end_call_reason: str
    call_recording_url: str | None
```

This extends rabat's existing `ProcessCallRequest` model shape with voice-specific fields.

### Why this split

- Extraction is CPU-only (regex, string matching) — fast, no reason to defer
- Dashboard sync, alert evaluation, growth tracking involve external calls and can retry independently
- If dashboard is down, call data is not lost — Inngest retries with backoff
- Growth memory gets the call event for attribution and lifecycle tracking

## 5. Tenant Credential Management

### Tenant ID propagation

Retell supports `metadata` on agent configurations. Each tenant's Retell agent is configured with:

```json
{
  "agent_id": "agent_xxx",
  "metadata": {
    "tenant_id": "uuid-here"
  }
}
```

Every webhook Retell fires includes this metadata. The voice module extracts `tenant_id` on every request.

### Voice config in tenant_configs

```python
class VoiceConfig(BaseModel):
    # Cal.com
    calcom_api_key: str
    calcom_event_type_id: int
    calcom_username: str
    calcom_timezone: str                # e.g., "America/Chicago"
    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    # Dashboard
    dashboard_webhook_url: str
    dashboard_webhook_secret: str
    # Service area
    service_area_zips: list[str]
    # Business identity
    business_name: str
    business_phone: str
```

### New migration: `048_voice_config.sql`

The existing `tenant_configs` table (migration 002) has only named columns — no generic JSONB config field. A new migration adds:

```sql
-- Add voice config column to tenant_configs
ALTER TABLE public.tenant_configs
  ADD COLUMN voice_config jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Call records table for voice call persistence
CREATE TABLE public.call_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_call_id text NOT NULL,
  phone_number text,
  transcript text,
  raw_retell_payload jsonb NOT NULL,       -- persisted before extraction
  extracted_fields jsonb DEFAULT '{}'::jsonb,  -- populated after extraction
  extraction_status text NOT NULL DEFAULT 'pending',  -- pending | complete | partial
  quality_score numeric(5,2),
  tags text[] DEFAULT '{}',
  route text,                              -- legitimate | spam | vendor | recruiter
  urgency_tier text,
  caller_type text,
  primary_intent text,
  revenue_tier text,
  booking_id text,                         -- Cal.com booking UID if booked
  callback_scheduled boolean DEFAULT false,
  call_duration_seconds integer,
  end_call_reason text,
  call_recording_url text,
  synced_to_dashboard boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

-- Booking API keys table
CREATE TABLE public.voice_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  api_key_hash text NOT NULL,              -- SHA-256 hash, not plaintext
  label text NOT NULL DEFAULT 'default',
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE(api_key_hash)
);

-- RLS on both tables
ALTER TABLE public.call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_records FORCE ROW LEVEL SECURITY;
CREATE POLICY call_records_tenant ON public.call_records
  USING (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_api_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_api_keys_tenant ON public.voice_api_keys
  USING (tenant_id = public.current_tenant_id());

-- Index for phone number lookups (customer status tool)
CREATE INDEX idx_call_records_phone ON public.call_records(tenant_id, phone_number);
-- Index for dashboard sync retry
CREATE INDEX idx_call_records_unsynced ON public.call_records(tenant_id, synced_to_dashboard)
  WHERE synced_to_dashboard = false;
```

`VoiceConfig` is stored in `tenant_configs.voice_config` JSONB column. Credentials are encrypted at the application layer before writing to this column (same pattern as other sensitive tenant config).

### Credential caching

On the first tool call of a conversation, `VoiceConfig` is fetched from `tenant_configs` via the repository layer and cached in Redis:
- Key: `t:{tenant_id}:voice:config` (follows existing `cache/keys.py` pattern)
- TTL: 5 minutes
- Subsequent tool calls in the same conversation hit cache

### Retell agent configs as knowledge nodes

The v9-triage agent definition (15-state FSM, tool definitions, prompts) is stored as:

```
knowledge/industry-packs/hvac/voice/retell-agent-v9.yaml
```

Standard knowledge node frontmatter. Versionable, reviewable, loadable by the knowledge graph. Different tenants can reference different agent versions. **No secrets in knowledge files** — API keys and credentials live only in `tenant_configs` in Supabase.

## 6. Extraction and Classification Logic

All extraction and classification modules are **pure functions** — no side effects, no DB calls, fully testable.

### 117-tag HVAC taxonomy (`extraction/tags.py`)

Direct port from Alexandria V2 `classification/tags.ts`:

- 9 categories: HAZARD (7), URGENCY (8), SERVICE_TYPE (23), REVENUE (9), RECOVERY (10), LOGISTICS (20), CUSTOMER (15), NON_CUSTOMER (12), CONTEXT (13)
- Negation-aware: checks 40 chars before match for "no", "not", "never", "don't", "isn't"
- Multi-word phrases use substring match; single words use word-boundary regex
- Returns `list[str]` of matched tag names

Tag definitions stored in `knowledge/industry-packs/hvac/taxonomy.yaml` as structured data. The Python module loads them at startup. Other industry packs can define their own taxonomies using the same engine.

### Call scorecard (`extraction/call_scorecard.py`)

Port from V2 `extraction/call-scorecard.ts`:

| Field | Weight |
|---|---|
| Customer name | 15 |
| Customer phone | 15 |
| Service address | 15 |
| Problem description | 15 |
| Urgency (urgency OR urgencyTier) | 10 |
| Booking OR callback | 20 |
| Tags present (binary) | 10 |

Warnings: `zero-tags` (no taxonomy tags classified), `callback-gap` (call ended without booking or callback).

### Urgency inference (`extraction/urgency.py`)

Keyword patterns from V2 returning `UrgencyTier`:
- **Emergency:** gas leak, CO, smoke, fire, sparking, flood
- **Urgent:** water leak, no heat/cool, emergency, ASAP
- **Routine:** maintenance, tune-up, standard
- **Estimate:** quote, how much, whenever, flexible

### Traffic controller (`classification/traffic.py`)

Adopted from V3's pattern. Routes calls based on `caller_type` and `primary_intent`:
- `legitimate` → normal dashboard card (blue/red/green by urgency)
- `spam` → archived gray card
- `vendor` / `recruiter` → archived gray card, no alert

### Test fixture migration

V2's Vitest test cases (transcript snippet → expected tags, expected urgency, expected score) port to **pytest parametrized fixtures**. These are the regression safety net — the logic must produce identical results after porting.

## 7. Booking REST API

Dashboard-facing endpoints for manual booking operations. Separate from Retell tool calls.

### Endpoints

```
GET  /api/bookings/lookup?phone={phone}     → Cal.com lookup by phone
POST /api/bookings/cancel                    → Cancel by booking_uid + reason
POST /api/bookings/reschedule                → Reschedule by booking_uid + new time
```

### Auth

API key via `X-API-Key` header, timing-safe comparison. Each API key maps to one tenant — tenant resolution happens at auth time. Separate from Retell HMAC auth.

### Validation

Pydantic equivalents of V2's Zod schemas:
- Phone: E.164 format (`+1XXXXXXXXXX`)
- Datetime: ISO 8601
- Booking UID: Cal.com format

## 8. Health Checks

Extend existing harness health endpoint:

- `GET /health` — simple 200 (Render load balancer)
- `GET /health/detailed` — existing checks + Cal.com reachability + Twilio reachability

## 9. Deployment and Cutover

### Render configuration

Voice routes mount on the existing harness FastAPI app. `render.yaml` updated to reflect Python runtime (if not already). Single Render service serves both harness orchestration and voice webhook endpoints.

### Zero-downtime cutover

1. **Deploy** updated harness with voice routes to Render. Old Express and new FastAPI run simultaneously.
2. **Smoke test** each voice endpoint with test payloads. Verify Cal.com integration, dashboard webhook delivery, Inngest event firing.
3. **Update Retell agent config** — point tool webhook URLs from Express service to FastAPI service. Single update in Retell dashboard per agent.
4. **Monitor** first 10-20 live calls. Check tool call latency, dashboard card correctness, Inngest event processing.
5. **Decommission** Express service on Render.

### Rollback

Revert Retell webhook URLs to Express service. Both services coexist indefinitely — they share the same Supabase database. No data migration needed.

During the cutover window, a call could start on Express (pre-switch) and subsequent tool calls could hit FastAPI (post-switch). This is safe because tool handlers are stateless — each tool call carries all context in the Retell request payload. There is no shared server-side session state between tool calls.

For Inngest event compatibility: during the cutover period, the Express service continues to emit its own post-call events (if any). The new `calllock/call.ended` events are only fired by the FastAPI service. There is no overlap — whichever service receives the `call-ended` webhook processes it. Rollback simply means the Express service resumes receiving all webhooks.

## 10. Write Ownership

| Table / Resource | Primary writer | Notes |
|---|---|---|
| `tenant_configs` (voice credentials) | Onboarding / admin | Voice module reads only |
| Call session state | Voice module (real-time tools) | Upserted during call |
| Dashboard webhook | Voice module (via Inngest) | Post-call sync |
| `touchpoint_log` | Growth system (via Inngest) | Call event as touchpoint |
| Alert records | Alert evaluator (via Inngest) | Emergency assessment |
| Job records | Job dispatcher (via Inngest) | Post-call job creation |
| Cal.com bookings | Voice module (real-time) | Created during call |
| Twilio SMS | Voice module (real-time + Inngest) | Emergency alerts |

## 11. Observability

### Metrics

| Metric | Type | Description |
|---|---|---|
| `voice.tool_call.duration_ms` | Histogram | Per-tool latency (labels: `tool_name`, `tenant_id`) |
| `voice.tool_call.errors` | Counter | Tool call failures (labels: `tool_name`, `error_type`) |
| `voice.post_call.extraction_duration_ms` | Histogram | Time spent in synchronous extraction pipeline |
| `voice.post_call.extraction_failures` | Counter | Extraction failures (partial extractions) |
| `voice.dashboard_sync.duration_ms` | Histogram | Dashboard webhook delivery time |
| `voice.dashboard_sync.failures` | Counter | Dashboard webhook delivery failures |
| `voice.calcom.duration_ms` | Histogram | Cal.com API call latency |
| `voice.calcom.errors` | Counter | Cal.com API failures |
| `voice.calls.total` | Counter | Total calls processed (labels: `route`, `urgency_tier`) |
| `voice.quality_score` | Histogram | Call quality score distribution |

### Alerts

| Alert | Threshold | Action |
|---|---|---|
| Tool call P95 latency > 1.5s | Sustained 5 min | Page — callers hearing dead air |
| Cal.com error rate > 10% | Over 15 min window | Page — bookings failing |
| Extraction failure rate > 5% | Over 30 min window | Warn — partial data reaching dashboard |
| Dashboard sync failure rate > 20% | Over 15 min window | Warn — dashboard cards missing |
| Zero calls processed in 1 hour | During business hours | Warn — possible webhook misconfiguration |

### PII handling

Transcripts contain customer names, addresses, and phone numbers. PII handling follows the existing `observability/pii_redactor.py` pattern:

- **LangSmith traces:** PII redacted before sending to LangSmith. Transcript content is masked in trace metadata.
- **Supabase `call_records`:** Raw transcript stored unredacted (needed for extraction retry and quality review). Access controlled by RLS — only the owning tenant's users can query.
- **Inngest event payload:** Transcript included in `calllock/call.ended` event. Inngest event logs should be treated as PII-containing and retention-limited.
- **Logs (Pino/structlog):** Phone numbers masked in structured logs (port V2's phone masking utility). Customer names not logged.
- **Retention:** `call_records` rows retained for 90 days by default. Configurable per tenant via `tenant_configs`. Transcripts can be purged independently of extracted fields.

## 12. Taxonomy startup validation

The taxonomy engine (`extraction/tags.py`) loads `knowledge/industry-packs/hvac/taxonomy.yaml` at module import time. If the file is missing or malformed, the module raises an `ImportError` at startup — failing fast rather than silently returning zero tags on the first post-call webhook.

## 13. What Gets Retired

| Component | Action |
|---|---|
| Alexandria Express V2 backend (Render) | Decommission after cutover |
| Alexandria Express V3 experimental | Already unused, no action |
| 23 city git worktrees | Archive — deployment artifacts only |
| `retellai-calllock/` workspace | Archive after migration complete |
| Node.js/TypeScript runtime for voice | Eliminated entirely |

## 14. Dependencies

### Python packages (additions to `harness/requirements.txt`)

- `twilio` — Twilio SMS client
- No new packages for Cal.com — uses `httpx` (already in requirements)
- No new packages for taxonomy — uses `pyyaml` (already in requirements) + `re` (stdlib)

### Inngest events (additions to `inngest/src/events/schemas.ts`)

- `calllock/call.ended` — new event with `CallEndedEvent` payload
- `calllock/call.dashboard.sync` — triggers dashboard webhook delivery
- `calllock/call.emergency.sms` — conditional emergency SMS

### Inngest functions (additions)

- `sync-dashboard` — receives `calllock/call.ended`, transforms payload, POSTs to dashboard webhook
- `send-emergency-sms` — receives `calllock/call.ended` (filtered: only safety emergencies), sends Twilio SMS

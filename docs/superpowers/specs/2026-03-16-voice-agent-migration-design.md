# Voice Agent Migration Design

**Date:** March 16, 2026
**Status:** Draft
**Owner:** Founder
**Supersedes:** Architecture spec Section 0 ("Express V2 — evolves into part of the product core, not replaced"). Express V2 is now fully ported to Python and decommissioned.

## Summary

Port the Valencia v10-simplified Express voice agent backend into rabat as a new `harness/src/voice/` Python package. Real-time Retell tool calls (`lookup_caller`, `create_callback_request`, `send_sales_lead_alert`) are handled by FastAPI endpoints on the same Render service. `book_service` remains on the CallLock App (`app.calllock.co`, Vercel) — it already works and the app owns the Cal.com integration. Post-call processing fires an Inngest event and fans out through existing harness infrastructure (growth memory, alerts, job dispatch). Multi-tenant from day one. Zero-downtime cutover by running both services in parallel during transition.

**Source correction:** The original spec referenced Alexandria (v9-triage, 15-state FSM, deployed Feb 12). The actual production agent is Valencia (v10-simplified, 10-state FSM, deployed Feb 14, Retell version 79). v10 was a structural redesign that cut 5 states based on the lesson: "Prompt-based guards: 0% success rate. Structural fixes (removing tools): 100% success rate."

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Migration target | Full port to Python | One runtime, one repo. Eliminates Node dependency. Rabat is the business OS. |
| Package location | `harness/src/voice/` | Peer to `harness/`, `growth/`, `inbound/`. Clean boundary, shared infrastructure. |
| Deployment | Same Render service | Voice routes mount on existing FastAPI app. No new infra to manage. |
| Source material | Valencia v10 logic + V2 extraction | v10-simplified is the production agent (10-state FSM, GPT-4o, Retell v79). V2's extraction/classification logic (117-tag taxonomy, scorecard, urgency) is battle-tested and ports as-is. |
| Real-time vs post-call | Split | Real-time tool calls stay synchronous in FastAPI. Post-call fires Inngest event for async fan-out. |
| Tenancy | Multi-tenant from day one | Rabat's repository layer enforces RLS. Fighting it for single-tenant would be more work. |
| Cal.com + Twilio | Keep as-is | Working integrations, no reason to change. |
| CallLock App | Same webhook contract | CallLock App stays on Vercel, receives same HMAC-signed payloads. |
| Taxonomy storage | YAML knowledge node | `knowledge/industry-packs/hvac/taxonomy.yaml`. Reusable by other industry packs. |
| Agent config storage | YAML knowledge node | `knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml`. Versionable, no secrets. Source: Valencia `retell-llm-v10-simplified.json`. |
| book_service ownership | Stays on CallLock App | `book_service` tool calls `app.calllock.co/api/retell/book-service` directly. CallLock App owns Cal.com booking integration. FastAPI does NOT handle bookings. |
| Voice credential storage | New migration: `voice_config` JSONB column on `tenant_configs` | Existing `tenant_configs` (migration 002) has only named columns, no generic JSONB. New migration adds the column. |
| Retell webhook routing | Per-tool URLs | Retell v10 sends each tool call to a dedicated URL (e.g., `/webhook/retell/lookup_caller`). Each tool has its own endpoint — no dispatcher needed. |
| Call records persistence | New `call_records` table | Post-call data needs a home. New migration alongside voice config column. |
| HMAC secret | Global environment variable (`RETELL_WEBHOOK_SECRET`) | Retell uses a single API key for HMAC signing per account, not per-agent. |
| Conversation state | Stateless tool handlers | Retell passes relevant context in each tool call payload. No server-side session state needed. |

## 1. Architecture Overview

### Architectural boundary (updated)

The original architecture spec drew the boundary as: harness orchestrates everything except real-time voice conversation. This migration moves the boundary — the harness now also handles real-time voice tool execution. Retell AI remains the voice *conversation* runtime (LLM, FSM transitions, speech). The harness handles most webhook-driven work: tool calls, post-call processing, booking management API. The one exception is `book_service`, which stays on the CallLock App.

```
  ┌─────────────────────────────────────────────────────────┐
  │              AGENT HARNESS (LangGraph + FastAPI)          │
  │  Workers, Jobs, Policy, Eval, Improvement Lab             │
  │  Voice Tools (lookup, callback, sales alert),             │
  │  Post-Call Processing, Booking Management API             │
  └──────────────────────┬────────────────────────────────────┘
                         │ orchestrates
  ┌──────────────────────┼──────────────────────────────────┐
  │                      │                                  │
  │  PRODUCT CORE        │    VOICE RUNTIME                 │
  │  (Next.js CallLock   │    (Retell AI v10-simplified)    │
  │   + Supabase         │                                  │
  │   + Cal.com          │    Handles: real-time calls,     │
  │   + Twilio)          │    10-state FSM, GPT-4o,         │
  │                      │    speech synthesis               │
  │  book_service tool   │                                  │
  │  (app.calllock.co)   │                                  │
  └──────────────────────┴──────────────────────────────────┘
```

### Runtime split

- **Retell AI:** Real-time voice conversation (GPT-4o LLM, 10-state FSM, speech-to-text, text-to-speech)
- **Python (FastAPI):** Tool call handlers (`lookup_caller`, `create_callback_request`, `send_sales_lead_alert`), post-call extraction, booking management REST API
- **CallLock App (Next.js, Vercel):** `book_service` tool handler (Cal.com integration), customer-facing UI
- **TypeScript (Inngest):** Thin event proxies — `calllock/call.ended` triggers fan-out to harness endpoints
- **Supabase:** Persistence for call records, bookings, sessions, tenant configs

## 2. Package Structure

```
harness/src/voice/
├── __init__.py              # Public API exports
├── router.py                # FastAPI router: Retell tool call endpoints (per-tool URLs)
├── post_call_router.py      # FastAPI router: Retell call-ended webhook
├── booking_router.py        # FastAPI router: booking management REST API (CallLock App-facing)
├── models.py                # Pydantic models (RetellToolCallRequest, ConversationState, etc.)
├── auth.py                  # Retell HMAC-SHA256 verification + booking API key auth
├── tools/
│   ├── __init__.py
│   ├── lookup_caller.py     # lookup_caller — full caller history from Supabase
│   ├── create_callback.py   # create_callback_request — callback + SMS notification
│   └── sales_lead_alert.py  # send_sales_lead_alert — high-ticket lead SMS to owner
├── services/
│   ├── __init__.py
│   ├── calcom.py            # Cal.com API client (lookup, cancel, reschedule — NOT booking)
│   ├── twilio_sms.py        # SMS: callback alerts, sales lead alerts, emergency alerts
│   └── app_sync.py          # CallLock App webhook sync (payload transform, HMAC signing)
├── extraction/
│   ├── __init__.py
│   ├── post_call.py         # Name, address, safety extraction from transcript
│   ├── urgency.py           # Urgency inference from keywords
│   ├── call_scorecard.py    # Weighted quality scoring (0-100, 7 fields)
│   └── tags.py              # 117-tag taxonomy engine (loads from YAML, negation-aware)
└── classification/
    ├── __init__.py
    ├── call_type.py          # Urgency → urgencyTier + app card level mapping
    ├── revenue.py            # Revenue tier classification
    └── traffic.py            # Traffic controller: spam/vendor/legitimate routing

NOTE: `book_service` is NOT in this package. It stays on the CallLock App at
`app.calllock.co/api/retell/book-service`. The CallLock App owns Cal.com booking.
`end_call` is Retell-internal (no webhook — Retell handles it natively).
`validate_service_area` and `check_calendar_availability` do not exist as tools —
ZIP validation is in-prompt logic, calendar availability is part of book_service.
```

### Router mounting

```python
# In harness/src/harness/server.py
from voice.router import voice_router
from voice.post_call_router import post_call_router
from voice.booking_router import booking_router

app.include_router(voice_router, prefix="/webhook/retell")         # HMAC auth — tool calls
app.include_router(post_call_router, prefix="/webhook/retell")     # HMAC auth — call-ended
app.include_router(booking_router, prefix="/api/bookings")         # API key auth — CallLock App
```

### Shared infrastructure (reused, not duplicated)

- `db/repository.py` + `db/tenant_scope.py` — all DB operations, RLS enforcement
- `observability/` — LangSmith tracing, PII redaction
- `cache/` — Redis key management

## 3. Real-Time Tool Call Flow

When Retell calls a tool mid-conversation, the request hits FastAPI directly. No Inngest, no queuing.

```
Caller speaks → Retell LLM decides to call tool
    → POST /webhook/retell/{tool_name}  (per-tool URL, configured in Retell agent)
    → auth.py verifies HMAC-SHA256 signature (global RETELL_WEBHOOK_SECRET env var)
    → tenant_scope.py sets RLS context from call metadata.tenant_id
    → tool handler executes (DB query or Twilio SMS)
    → returns JSON response to Retell
    → Retell LLM continues conversation
```

### Webhook routing

Retell v10 configures each tool with its own webhook URL. There is **no dispatcher** — each tool has a dedicated FastAPI endpoint:

```python
# Tools handled by FastAPI (rabat)
@voice_router.post("/lookup_caller")
async def handle_lookup_caller(request: RetellToolCallRequest): ...

@voice_router.post("/create_callback")
async def handle_create_callback(request: RetellToolCallRequest): ...

@voice_router.post("/send_sales_lead_alert")
async def handle_sales_lead_alert(request: RetellToolCallRequest): ...

# Tools NOT handled by FastAPI:
# - book_service → app.calllock.co/api/retell/book-service (CallLock App)
# - end_call → Retell-internal (no webhook)
```

Retell also sends a separate `POST /webhook/retell/call-ended` for the post-call webhook — this is a lifecycle event, not a tool call.

### Tool handler pattern

Every tool handler follows the same structure:

1. **Auth** — Retell HMAC signature verification (middleware on `voice_router`)
2. **Tenant** — extract `tenant_id` from Retell's `custom_metadata`, set RLS context
3. **Config** — resolve `VoiceConfig` from `tenant_configs` (cached in Redis)
4. **Execute** — call external API or query DB
5. **Return** — JSON matching Retell's tool response schema

### Tool inventory (v10-simplified)

**Tools handled by FastAPI (this migration):**

| Tool | Retell URL | External dependency | Latency budget | States |
|---|---|---|---|---|
| `lookup_caller` | `/webhook/retell/lookup_caller` | Supabase (last 10 jobs, last 5 calls, last 5 bookings — LIMIT per table) | <500ms | lookup |
| `create_callback_request` | `/webhook/retell/create_callback` | Twilio SMS (callback notification) | <1s | callback |
| `send_sales_lead_alert` | `/webhook/retell/send_sales_lead_alert` | Twilio SMS (owner alert) | <1s | callback |

**Tools NOT handled by FastAPI:**

| Tool | Owner | Notes |
|---|---|---|
| `book_service` | CallLock App (`app.calllock.co/api/retell/book-service`) | Cal.com booking. Stays on CallLock App. |
| `end_call` | Retell-internal | No webhook — Retell handles natively. States: safety_exit, service_area, done, callback |

**Not tools (in-prompt logic):**

| Capability | How it works | States |
|---|---|---|
| ZIP validation | LLM checks ZIP prefix "787" per prompt rules | service_area |
| Calendar availability | Part of `book_service` flow on CallLock App | booking |
| Safety screening | LLM asks question, routes via edges only | safety |

### Error handling

If an external dependency fails (Supabase down for lookup, Twilio timeout for SMS), the tool returns a graceful degradation response to Retell. Examples:
- `lookup_caller` failure: return `{found: false}` — agent proceeds as new caller (slightly worse UX, no data loss)
- `create_callback_request` failure: return success to Retell (caller hears normal ending) but log failure and fire Inngest retry event
- `send_sales_lead_alert` failure: return success to Retell, retry SMS via Inngest post-call

Tools never hang or throw — Retell has a per-tool timeout (8s for lookup, default for others) and the caller hears dead air if the tool doesn't respond.

## 4. Post-Call Flow

When Retell fires the `call-ended` webhook, the voice module does minimal synchronous work and hands off to Inngest.

### Synchronous (in the webhook handler, <2s)

1. Verify HMAC signature
2. Extract `tenant_id` from call metadata
3. **Generate `call_id`** (harness UUID via `uuid4()`) and **persist raw Retell payload** to `call_records` table immediately (before extraction). The `retell_call_id` field stores Retell's own call identifier from the webhook payload. The harness-generated `call_id` is the primary key used across all downstream systems (Inngest events, CallLock App sync, growth touchpoints). This ensures call data is never lost even if extraction fails.
4. Run extraction pipeline (pure functions, no external calls):
   - `post_call.py` — customer name, service address, safety flags from transcript
   - `urgency.py` — urgency inference from keywords
   - `tags.py` — 117-tag HVAC taxonomy classification
   - `call_scorecard.py` — quality score (0-100)
   - `call_type.py` — urgency tier + app card level mapping
   - `traffic.py` — traffic controller routing decision
5. **Update `call_records`** with extracted fields
6. Fire Inngest event `calllock/call.ended` with extracted payload
7. Return 200 to Retell

### Extraction failure handling

If any extraction step throws an exception, the handler catches it, logs the error, and still fires the Inngest event with whatever fields were successfully extracted (others default to `None`). The raw Retell payload is already persisted (step 3), so no data is lost. A `extraction_status: 'partial' | 'complete'` field on the event signals downstream consumers. The `call_records` row retains the raw payload for manual review or retry.

### Asynchronous (Inngest fan-out)

```
calllock/call.ended
  ├→ process-voice-call    (new)      — maps CallEndedEvent → ProcessCallRequest, calls harness /process-call
  ├→ sync-app              (new)      — transform payload, POST to CallLock App webhook, set synced_to_dashboard
  ├→ evaluate-alerts       (existing) — emergency alert evaluation
  ├→ growth-touchpoint     (existing) — log call as growth touchpoint
  └→ send-emergency-sms    (new, conditional) — only if safety emergency flagged AND not already sent during call
```

### Emergency SMS handling

In v10-simplified, there is **no live-call emergency SMS tool**. Emergency calls route to `safety_exit` → `end_call` (Retell-internal). Emergency SMS is sent **post-call only** via the `send-emergency-sms` Inngest function, triggered when the extraction pipeline flags a safety emergency in the transcript.

Idempotency: Inngest's built-in function-level idempotency key `{tenant_id}:{call_id}:emergency-sms` prevents duplicate sends on Inngest retries.

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
    # Booking state (needed by scorecard and CallLock App)
    booking_id: str | None          # Parsed from Retell's tool_call_results (book_service result), not transcript
    callback_scheduled: bool        # Whether a callback was promised
    # Extraction metadata
    extraction_status: Literal["complete", "partial"]
    # Raw Retell data
    retell_call_id: str
    call_duration_seconds: int
    end_call_reason: str
    call_recording_url: str | None
```

`CallEndedEvent` shares common fields with rabat's existing `ProcessCallRequest` (`tenant_id`, `call_id`, `call_source`, `transcript`) but is a **separate model** — not a subclass. `ProcessCallRequest` uses `StrictModel` with `extra="forbid"`, so it cannot accept voice-specific fields.

### Integration with existing `process-call` Inngest function

The existing `process-call` function expects a `ProcessCallRequest` payload. A new Inngest function `process-voice-call` subscribes to `calllock/call.ended` and maps `CallEndedEvent` to `ProcessCallRequest`:

```python
def voice_event_to_process_call(event: CallEndedEvent) -> ProcessCallRequest:
    return ProcessCallRequest(
        call_id=event.call_id,
        tenant_id=event.tenant_id,
        transcript=event.transcript,
        problem_description=event.problem_description,
        call_source="retell",
        call_metadata={"voice_event": True, "route": event.route},
    )
```

This replaces the `process-call (existing)` entry in the fan-out diagram above. The `process-voice-call` function calls the existing harness `/process-call` endpoint with the mapped payload.

### Why this split

- Extraction is CPU-only (regex, string matching) — fast, no reason to defer
- CallLock App sync, alert evaluation, growth tracking involve external calls and can retry independently
- If CallLock App is down, call data is not lost — Inngest retries with backoff
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
    # Twilio (for callback SMS and sales lead alerts)
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_owner_phone: str             # Owner's phone for sales lead alerts
    # CallLock App webhook
    app_webhook_url: str
    app_webhook_secret: str
    # Service area (used by post-call classification, not real-time — ZIP check is in-prompt)
    service_area_zips: list[str]
    # Business identity
    business_name: str
    business_phone: str
```

Note: Cal.com credentials (`calcom_api_key`, `calcom_event_type_id`, etc.) are NOT in `VoiceConfig` because `book_service` stays on the CallLock App. The booking management REST API (Section 7) uses Cal.com for lookup/cancel/reschedule — those credentials are stored in a separate `calcom_config` field on `tenant_configs`, shared with the CallLock App.

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
  synced_to_dashboard boolean DEFAULT false,  -- "dashboard" here means CallLock App at app.calllock.co
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

-- Auto-update updated_at on row modification
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
-- Index for CallLock App sync retry
CREATE INDEX idx_call_records_unsynced ON public.call_records(tenant_id, synced_to_dashboard)
  WHERE synced_to_dashboard = false;
```

`VoiceConfig` is stored in `tenant_configs.voice_config` JSONB column. Sensitive credentials (`calcom_api_key`, `twilio_auth_token`, `app_webhook_secret`) are encrypted at the application layer using AES-256-GCM before writing to this column. The encryption key is sourced from `VOICE_CREDENTIAL_KEY` environment variable (same pattern as inbound pipeline's `IMAP_CREDENTIAL_KEY` in the inbound pipeline spec Section 13). Key rotation: re-encrypt on write with the current key; decryption attempts the current key first, then the previous key (`VOICE_CREDENTIAL_KEY_PREV`).

### Empty voice config handling

Non-voice tenants will have `voice_config = '{}'` after migration 048. If a Retell webhook arrives with a `tenant_id` whose `voice_config` is empty or missing required fields, `VoiceConfig` Pydantic validation will fail. The tool handler catches this and returns a graceful error to Retell: "We're experiencing technical difficulties. Please call back or leave a message." This prevents dead air for misconfigured tenants.

### Credential caching

On the first tool call of a conversation, `VoiceConfig` is fetched from `tenant_configs` via the repository layer and cached in Redis:
- Key: `t:{tenant_id}:voice:config` (follows existing `cache/keys.py` pattern)
- TTL: 5 minutes
- Subsequent tool calls in the same conversation hit cache

### Retell agent configs as knowledge nodes

The v10-simplified agent definition (10-state FSM, tool definitions, prompts) is stored as:

```
knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml
```

Source: Valencia `voice-agent/retell-llm-v10-simplified.json`. Standard knowledge node frontmatter. Versionable, reviewable, loadable by the knowledge graph. Different tenants can reference different agent versions. **No secrets in knowledge files** — API keys and credentials live only in `tenant_configs` in Supabase.

### v10 design principles (preserve during port)

The v10 state machine encodes hard-won lessons from 18 patches on v9:

1. **States that make decisions have no tools. States that take actions have specific tools. Terminal states handle end_call.**
2. **`general_tools` is empty** — no tool is available in all states. This prevents the LLM from calling `end_call` or `book_service` from wrong states.
3. **All non-happy-path exits converge to ONE terminal: `callback`** — simplifies error handling and ensures callers always get a callback if anything goes wrong.
4. **`booking` has NO `end_call`** — agent cannot hang up after a failed booking, must route to `callback` instead.

## 6. Extraction and Classification Logic

All extraction and classification modules are **pure functions** — no side effects, no DB calls, fully testable.

### 117-tag HVAC taxonomy (`extraction/tags.py`)

Direct port from Valencia V2 backend `classification/tags.ts` (shared across Alexandria and Valencia — extraction logic is identical):

- 9 categories: HAZARD (7), URGENCY (8), SERVICE_TYPE (23), REVENUE (9), RECOVERY (10), LOGISTICS (20), CUSTOMER (15), NON_CUSTOMER (12), CONTEXT (13)
- Negation-aware: checks 40 chars before match for "no", "not", "never", "don't", "isn't"
- Multi-word phrases use substring match; single words use word-boundary regex
- Returns `list[str]` of matched tag names

Tag definitions stored in `knowledge/industry-packs/hvac/taxonomy.yaml` as structured data. **This file must be created as a deliverable of this migration** — the 117 tags are ported from V2's `classification/tags.ts` into YAML format. The Python module loads them at startup. Other industry packs can define their own taxonomies using the same engine.

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

### Short call / empty transcript handling

For calls with empty or minimal transcripts (<20 characters — hangups, robocalls, wrong numbers):
- `urgency_tier` defaults to `Routine`
- `route` defaults to `legitimate` (better to show a low-priority card than silently drop)
- `tags` will be empty list, `quality_score` will be 0
- Both `zero-tags` and `callback-gap` warnings fire — this is expected and correct
- CallLock App shows a gray "minimal info" card rather than dropping the call entirely

### Traffic controller (`classification/traffic.py`)

Adopted from V3's pattern. Routes calls based on `caller_type` and `primary_intent`:
- `legitimate` → normal app card (blue/red/green by urgency)
- `spam` → archived gray card
- `vendor` / `recruiter` → archived gray card, no alert

### Test fixture migration

V2's Vitest test cases (transcript snippet → expected tags, expected urgency, expected score) port to **pytest parametrized fixtures**. These are the regression safety net — the logic must produce identical results after porting.

### Pipeline smoke test

One integration test that fires a realistic Retell call-ended payload at the FastAPI endpoint and asserts:
1. `call_records` row created with correct `extraction_status`
2. Inngest event fired with correct `CallEndedEvent` schema
3. CallLock App webhook payload (captured via mock HTTP server) matches expected format

This is the "2am Friday confidence test" — if this passes, the full pipeline works. Uses mock Inngest client and mock HTTP server for the CallLock App webhook.

## 7. Booking REST API

CallLock App-facing endpoints for manual booking operations. Separate from Retell tool calls.

### Endpoints

```
GET  /api/bookings/lookup?phone={phone}     → Cal.com lookup by phone
POST /api/bookings/cancel                    → Cancel by booking_uid + reason
POST /api/bookings/reschedule                → Reschedule by booking_uid + new time
```

### Auth

API key via `X-API-Key` header, timing-safe comparison against SHA-256 hash stored in `voice_api_keys` table. Each API key maps to one tenant — tenant resolution happens at auth time. Separate from Retell HMAC auth.

### API key provisioning

Keys are created during tenant onboarding (when `OnboardTenantRequest.configure_voice_agent = True`):
1. Generate a random 32-byte API key, encode as base64
2. Store SHA-256 hash in `voice_api_keys` with the `tenant_id`
3. Return the plaintext key once to the caller (not stored)
4. Rotation: create a new key, distribute to CallLock App, then revoke the old key by setting `revoked_at`
5. Auth middleware skips keys where `revoked_at IS NOT NULL`

### Validation

Pydantic equivalents of V2's Zod schemas:
- Phone: E.164 format (`+1XXXXXXXXXX`)
- Datetime: ISO 8601
- Booking UID: Cal.com format

## 8. Health Checks

Extend existing harness health endpoint:

- `GET /health` — simple 200 (Render load balancer)
- `GET /health/detailed` — existing checks + Cal.com connectivity (`HEAD https://api.cal.com`, not credential-specific) + Twilio connectivity (`HEAD https://api.twilio.com`). These are connectivity checks, not per-tenant credential checks — credential validity is verified on first use per call.

## 9. Deployment and Cutover

### Render configuration

Voice routes mount on the existing harness FastAPI app. `render.yaml` updated to reflect Python runtime (if not already). Single Render service serves both harness orchestration and voice webhook endpoints.

### Zero-downtime cutover

1. **Deploy** updated harness with voice routes to Render. Old Express and new FastAPI run simultaneously.
2. **Smoke test** each voice endpoint with test payloads. Verify lookup_caller returns correct data, create_callback sends SMS, Inngest event fires on call-ended.
3. **Update Retell agent tool URLs** — only 3 tool URLs change (per-tool, not a single webhook):
   - `lookup_caller`: `calllock-server.onrender.com/webhook/retell/lookup_caller` → `{rabat-service}/webhook/retell/lookup_caller`
   - `create_callback_request`: `calllock-server.onrender.com/webhook/retell/create_callback` → `{rabat-service}/webhook/retell/create_callback`
   - `send_sales_lead_alert`: `calllock-server.onrender.com/webhook/retell/send_sales_lead_alert` → `{rabat-service}/webhook/retell/send_sales_lead_alert`
   - `book_service`: **NO CHANGE** — stays at `app.calllock.co/api/retell/book-service`
   - Also update the post-call webhook URL in Retell agent settings.
4. **Monitor** first 10-20 live calls. Check tool call latency, CallLock App card correctness, Inngest event processing.
5. **Decommission** Express service on Render.

### Rollback

Revert Retell webhook URLs to Express service. Both services coexist indefinitely — they share the same Supabase database. No data migration needed.

During the cutover window, a call could start on Express (pre-switch) and subsequent tool calls could hit FastAPI (post-switch). This is safe because tool handlers are stateless — each tool call carries all context in the Retell request payload. There is no shared server-side session state between tool calls.

Calls in progress during URL swap are safe because the call-ended webhook payload contains the complete transcript and all tool call results regardless of which service handled the individual tool calls during the conversation.

For Inngest event compatibility: during the cutover period, the Express service continues to emit its own post-call events (if any). The new `calllock/call.ended` events are only fired by the FastAPI service. There is no overlap — whichever service receives the `call-ended` webhook processes it. Rollback simply means the Express service resumes receiving all webhooks.

## 10. Write Ownership

| Table / Resource | Primary writer | Notes |
|---|---|---|
| `tenant_configs` (voice credentials) | Onboarding / admin | Voice module reads only |
| `call_records` | Voice module (post-call handler) | Insert raw payload, update with extracted fields |
| CallLock App webhook | Voice module (via Inngest) | Post-call sync |
| `touchpoint_log` | Growth system (via Inngest) | Call event as touchpoint |
| Alert records | Alert evaluator (via Inngest) | Emergency assessment |
| Job records | Job dispatcher (via Inngest) | Post-call job creation |
| Cal.com bookings | CallLock App (`book_service` tool) | Created during call via Retell → CallLock App |
| Twilio SMS (callbacks) | Voice module (real-time `create_callback_request`) | Callback notifications |
| Twilio SMS (sales leads) | Voice module (real-time `send_sales_lead_alert`) | High-ticket owner alerts |
| Twilio SMS (emergency, post-call) | Voice module (via Inngest, conditional) | Safety emergency alerts |

## 11. Observability

### Metrics

| Metric | Type | Description |
|---|---|---|
| `voice.tool_call.duration_ms` | Histogram | Per-tool latency (labels: `tool_name`, `tenant_id`) |
| `voice.tool_call.errors` | Counter | Tool call failures (labels: `tool_name`, `error_type`) |
| `voice.post_call.extraction_duration_ms` | Histogram | Time spent in synchronous extraction pipeline |
| `voice.post_call.extraction_failures` | Counter | Extraction failures (partial extractions) |
| `voice.app_sync.duration_ms` | Histogram | CallLock App webhook delivery time |
| `voice.app_sync.failures` | Counter | CallLock App webhook delivery failures |
| `voice.twilio_sms.duration_ms` | Histogram | Twilio SMS send latency |
| `voice.twilio_sms.errors` | Counter | Twilio SMS failures |
| `voice.calls.total` | Counter | Total calls processed (labels: `route`, `urgency_tier`) |
| `voice.quality_score` | Histogram | Call quality score distribution |
| `voice.config_cache.hits` | Counter | VoiceConfig Redis cache hits |
| `voice.config_cache.misses` | Counter | VoiceConfig Redis cache misses (triggers Supabase fetch) |

### Alerts

| Alert | Threshold | Action |
|---|---|---|
| Tool call P95 latency > 1.5s | Sustained 5 min | Page — callers hearing dead air |
| Twilio SMS error rate > 10% | Over 15 min window | Warn — callback/sales alert SMS failing |
| Extraction failure rate > 5% | Over 30 min window | Warn — partial data reaching CallLock App |
| CallLock App sync failure rate > 20% | Over 15 min window | Warn — app cards missing |
| Zero calls processed in 1 hour | During business hours | Warn — possible webhook misconfiguration |

### PII handling

Transcripts contain customer names, addresses, and phone numbers. PII handling follows the existing `observability/pii_redactor.py` pattern:

- **LangSmith traces:** PII redacted before sending to LangSmith. Transcript content is masked in trace metadata.
- **Supabase `call_records`:** Raw transcript stored unredacted (needed for extraction retry and quality review). Access controlled by RLS — only the owning tenant's users can query.
- **Inngest event payload:** Transcript included in `calllock/call.ended` event. Inngest event logs should be treated as PII-containing and retention-limited.
- **Logs (Pino/structlog):** Phone numbers masked in structured logs (port V2's phone masking utility). Customer names not logged.
- **Retention:** `call_records` rows retained for 90 days by default. Configurable per tenant via `tenant_configs`. Transcripts can be purged independently of extracted fields. A weekly Inngest cron (`calllock/call.retention.cleanup`) deletes expired rows based on tenant retention policy. Transcripts older than the retention window are nullified first; full row deletion happens 30 days after transcript purge.

### CallLock App sync lifecycle

The `sync-app` Inngest function sets `call_records.synced_to_dashboard = true` on successful delivery. If Inngest exhausts retries (default: 3 attempts with exponential backoff), the row remains `synced_to_dashboard = false`. A daily Inngest cron (`calllock/call.app-sync.retry`) queries `idx_call_records_unsynced` and re-attempts delivery for rows older than 1 hour but younger than 7 days. After 7 days, unsynced rows are flagged for manual review.

## 12. v10 State Machine Reference

The production Retell agent uses a 10-state FSM (v10-simplified, deployed Feb 14 2026). This is the definitive reference for the migration.

```
  ┌─────────┐
  │ welcome │ (no tools, edges only)
  └────┬────┘
       │ service intent          │ non-service intent
       ▼                         ▼
  ┌─────────┐              ┌──────────┐
  │ lookup  │              │ callback │ (create_callback_request,
  │ (lookup_│              │          │  send_sales_lead_alert,
  │  caller)│              │          │  end_call)
  └────┬────┘              └──────────┘
       │
       ▼
  ┌─────────┐
  │ safety  │ (no tools, edges only)
  └────┬────┘
       │ clear               │ emergency
       ▼                     ▼
  ┌─────────────┐      ┌─────────────┐
  │ service_area│      │ safety_exit │ (end_call)
  │ (end_call   │      └─────────────┘
  │  for OOA)   │
  └──────┬──────┘
         │ in-area
         ▼
  ┌───────────┐
  │ discovery │ (no tools, edges only)
  └─────┬─────┘
        │
        ▼
  ┌─────────┐
  │ confirm │ (no tools, edges only — merged urgency + pre_confirm)
  └────┬────┘
       │ approved              │ callback/sales lead
       ▼                       ▼
  ┌─────────┐            ┌──────────┐
  │ booking │            │ callback │
  │ (book_  │            └──────────┘
  │ service)│ ← NO end_call!
  └────┬────┘
       │ success            │ failure
       ▼                    ▼
  ┌──────┐            ┌──────────┐
  │ done │            │ callback │
  │(end_ │            └──────────┘
  │ call)│
  └──────┘
```

### Tool-to-state mapping (v10)

| State | Tools available | Webhook owner |
|---|---|---|
| welcome | (none) | — |
| lookup | `lookup_caller` | FastAPI |
| safety | (none) | — |
| safety_exit | `end_call` | Retell-internal |
| service_area | `end_call` (out-of-area only) | Retell-internal |
| discovery | (none) | — |
| confirm | (none) | — |
| booking | `book_service` (NO end_call) | CallLock App |
| done | `end_call` | Retell-internal |
| callback | `create_callback_request`, `send_sales_lead_alert`, `end_call` | FastAPI (callback, alert), Retell-internal (end_call) |

## 13. Taxonomy startup validation

The taxonomy engine (`extraction/tags.py`) loads `knowledge/industry-packs/hvac/taxonomy.yaml` at module import time. If the file is missing or malformed, the module raises an `ImportError` at startup — failing fast rather than silently returning zero tags on the first post-call webhook.

## 14. What Gets Retired

| Component | Action |
|---|---|
| Valencia Express V2 backend on Render (`calllock-server.onrender.com`) | Decommission after cutover |
| Alexandria workspace (`retellai-calllock/alexandria/`) | Already superseded by Valencia, no action |
| Valencia workspace (`retellai-calllock/valencia/`) | Archive after migration complete — v10 config is source of truth |
| 23 city git worktrees | Archive — deployment artifacts only |
| `retellai-calllock/` workspace | Archive after migration complete |
| Node.js/TypeScript runtime for voice | Eliminated entirely (except `book_service` which stays on CallLock App) |

## 15. Dependencies

### Python packages (additions to `harness/requirements.txt`)

- `twilio` — Twilio SMS client
- `httpx` (already in requirements) — used for Cal.com booking management REST API and CallLock App webhook delivery
- No new packages for taxonomy — uses `pyyaml` (already in requirements) + `re` (stdlib)

### Inngest events (additions to `inngest/src/events/schemas.ts`)

- `calllock/call.ended` — new event with `CallEndedEvent` payload
- `calllock/call.app.sync` — triggers CallLock App webhook delivery
- `calllock/call.emergency.sms` — conditional emergency SMS

### Inngest functions (additions)

- `process-voice-call` — receives `calllock/call.ended`, maps `CallEndedEvent` → `ProcessCallRequest`, calls existing harness `/process-call` endpoint
- `sync-app` — receives `calllock/call.ended`, transforms payload, POSTs to CallLock App webhook, sets `synced_to_dashboard = true`
- `send-emergency-sms` — receives `calllock/call.ended` (filtered: only safety emergencies, checks `emergency_sms_sent_at` for dedup), sends Twilio SMS
- `app-sync-retry` — daily cron, retries unsynced `call_records` (1h–7d old)
- `call-records-retention` — weekly cron, purges transcripts and deletes expired `call_records` per tenant retention policy

## 16. CEO Review Findings

### Review decisions (HOLD SCOPE mode)

| # | Issue | Decision | Rationale |
|---|---|---|---|
| 1 | Post-call raw persist fails (Supabase down) | Return 500, Retell retries | Simplest — Retell holds data until DB recovers |
| 2 | VoiceConfig resolution fails (Redis + Supabase down) | Graceful Retell error + alert | Caller hears polite message, not dead air |
| 3 | Credential decryption fails | Graceful Retell error + alert | Same pattern as #2, operator must fix key |
| 4 | Retell tool call input validation | Loose validation, log warnings, proceed | Trusted upstream, don't punish callers |
| 5 | SMS content injection | Template-based SMS with sanitized interpolation | Fixed templates, truncate + strip reason |
| 6 | Post-call webhook idempotency | UNIQUE(tenant_id, call_id) constraint | Catch duplicate INSERT, skip, return 200 |
| 7 | Cal.com credential duplication | Accept duplication | CallLock App has its own, tenant_configs has per-tenant |
| 8 | V2 test fixture migration | Exact parity | Every V2 test → pytest, results must be identical |
| 9 | Structured logging for tool calls | Add structured logs at entry/exit + post-call summary | Grep-friendly, matches harness pattern |
| 10 | Runbooks for top alerts | Add to spec | 3-5 steps each for top 3 alerts |
| 11 | Cutover duplicate processing | Rely on idempotency guard | UNIQUE constraint handles it, no feature flag |
| 12 | Emergency SMS dedup (v10 has no live-call SMS tool) | Remove dedup, post-call only via Inngest | v10 safety_exit → end_call, no SMS during call |
| 13 | voice_event_to_process_call field name bug | Fix: `metadata` → `call_metadata` | ProcessCallRequest uses call_metadata with extra=forbid |
| 14 | server.py doesn't use include_router | Voice module introduces routers (correct FastAPI pattern) | Sets precedent, existing monolithic server.py is tech debt |
| 15 | Booking mgmt API missing from Error & Rescue Registry | Add 4 entries (Cal.com timeout, error, validation, auth) | Consistency with failure modes registry |
| 16 | booking_id source unclear (book_service on CallLock App) | Parsed from Retell's tool_call_results in raw payload | Retell includes tool results in call-ended webhook |
| 17 | Global HMAC secret is single point of compromise | Accept — Retell platform limitation. Document as known risk | Per-agent signing not supported by Retell |
| 18 | Empty/short transcript handling unspecified | Default: urgency=Routine, route=legitimate | Show low-priority card rather than silently drop |
| 19 | No pipeline smoke test (webhook → extraction → Inngest → CallLock App) | Add one integration test covering full pipeline | The 2am Friday confidence test |
| 20 | lookup_caller unbounded query | Add LIMIT per table (10 jobs, 5 calls, 5 bookings) | Prevents latency blowup for frequent callers |
| 21 | No VoiceConfig cache hit/miss metric | Add voice.config_cache.hits/misses counters | Cheap, immediately diagnostic for latency |
| 22 | In-flight calls during URL swap | Add clarification: call-ended payload is self-contained | Confirms safety, no code change |

### Security: Known Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Global HMAC secret compromise | Low | High (all tenants' voice webhooks) | Retell platform limitation — no per-agent signing. Rotation: update RETELL_WEBHOOK_SECRET env var + update in Retell dashboard. Both systems must update simultaneously. |
| Twilio credentials in JSONB (encrypted) | Low | Medium (per-tenant SMS) | AES-256-GCM encryption at rest. Key rotation via VOICE_CREDENTIAL_KEY / VOICE_CREDENTIAL_KEY_PREV. |
| Transcripts in Inngest event logs | Medium | Medium (PII exposure) | Inngest event retention should be limited. Transcripts are PII — configure Inngest log retention to match call_records retention policy (90 days default). |

### Runbooks

**Alert: Tool call P95 latency > 1.5s (sustained 5 min)**
1. Check Supabase dashboard for connection pool exhaustion or slow queries
2. Check Redis for connectivity issues (VoiceConfig cache misses cause extra DB hits)
3. Check Render service logs for error spikes
4. If Supabase is the bottleneck: check `lookup_caller` query plan, verify indexes exist
5. If unresolvable in 5 min: rollback — revert Retell tool URLs to Express backend

**Alert: Twilio SMS error rate > 10% (over 15 min)**
1. Check Twilio dashboard for account status, balance, rate limits
2. Check structured logs for `voice.tool_call` events with `error_type: TwilioRestException`
3. Verify `twilio_from_number` in tenant VoiceConfig is valid and active
4. If Twilio is down: callbacks still work (Retell tool returns success), SMS delivery retried by Inngest post-call

**Alert: Zero calls processed in 1 hour (business hours)**
1. Verify Retell agent is active and phone number is bound to correct version
2. Check Retell dashboard for recent call activity (calls may be happening but webhooks aren't firing)
3. Verify FastAPI health endpoint is responding (`/health`)
4. Check Render deployment status — recent deploy may have broken voice routes
5. Test with a manual call to the Retell number

### Error & Rescue Registry

```
  METHOD                        | EXCEPTION              | RESCUED | ACTION                    | USER SEES
  ------------------------------|------------------------|---------|---------------------------|------------------
  lookup_caller handler         | httpx.TimeoutException | Y       | Return {found: false}     | Treated as new caller
  lookup_caller handler         | httpx.ConnectError     | Y       | Return {found: false}     | Treated as new caller
  create_callback handler       | TwilioRestException    | Y       | Return success, retry     | Normal call ending
  send_sales_lead_alert handler | TwilioRestException    | Y       | Return success, retry     | Normal call ending
  send_sales_lead_alert handler | VoiceConfigError       | Y       | Graceful error + alert    | "Technical difficulty"
  post-call: raw INSERT         | httpx.TimeoutException | Y       | Return 500 to Retell      | Retell retries webhook
  post-call: extraction         | ExtractionError        | Y       | Partial extract, continue | CallLock App gets partial data
  post-call: UPDATE extracted   | httpx.TimeoutException | Y       | Log, fire Inngest anyway  | CallLock App gets partial data
  post-call: fire Inngest       | httpx.TimeoutException | Y       | Log, return 200           | App card delayed
  post-call: duplicate INSERT   | UniqueViolation        | Y       | Skip processing, return 200| No visible effect
  VoiceConfig resolution        | httpx.TimeoutException | Y       | Graceful error + alert    | "Technical difficulty"
  VoiceConfig resolution        | ValidationError        | Y       | Graceful error + alert    | "Technical difficulty"
  credential decryption         | DecryptionError        | Y       | Graceful error + alert    | "Technical difficulty"
  HMAC verification             | HMACVerificationError  | Y       | Return 401                | Retell sees auth failure
  booking lookup                | httpx.TimeoutException | Y       | Return 503                | CallLock App shows error
  booking cancel                | httpx.HTTPStatusError  | Y       | Return 502 + Cal.com msg  | CallLock App shows error
  booking reschedule            | httpx.HTTPStatusError  | Y       | Return 502 + Cal.com msg  | CallLock App shows error
  booking auth                  | InvalidAPIKeyError     | Y       | Return 401                | CallLock App auth failure
  taxonomy load                 | ImportError            | FATAL   | Process won't start       | N/A (startup)
  RETELL_WEBHOOK_SECRET missing | ConfigurationError     | FATAL   | Process won't start       | N/A (startup)
```

### Failure Modes Registry

```
  CODEPATH              | FAILURE MODE              | RESCUED | TEST | USER SEES      | LOGGED
  ----------------------|---------------------------|---------|------|----------------|--------
  lookup_caller         | Supabase down             | Y       | Y    | New caller UX  | Y
  create_callback       | Twilio down               | Y       | Y    | Normal ending  | Y
  send_sales_lead_alert | Twilio down               | Y       | Y    | Normal ending  | Y
  post-call persist     | Supabase down             | Y       | Y    | Retell retries | Y
  post-call extraction  | Regex exception           | Y       | Y    | Partial data   | Y
  post-call Inngest     | Inngest down              | Y       | Y    | Card delayed   | Y
  post-call duplicate   | Retell retry              | Y       | Y    | No effect      | Y
  VoiceConfig load      | Redis + Supabase down     | Y       | Y    | Polite message | Y
  VoiceConfig decrypt   | Bad encryption key        | Y       | Y    | Polite message | Y (alert)
  HMAC auth             | Invalid/missing signature | Y       | Y    | Auth failure   | Y
  taxonomy startup      | YAML missing/malformed    | FATAL   | Y    | Deploy fails   | Y
  sync-app              | CallLock App 5xx          | Y       | Y    | Card delayed   | Y (Inngest retry)
  booking mgmt API      | Cal.com down              | Y       | Y    | 503 response   | Y
  booking mgmt API      | Invalid API key           | Y       | Y    | 401 response   | Y
```

**CRITICAL GAPS: 0.** All failure modes are rescued, tested, user-visible, and logged.

### NOT in scope

| Item | Rationale |
|---|---|
| Voice agent eval framework | Expansion scope — v10 config is ported as-is, not optimized |
| Cross-channel attribution (call + email) | Growth system Phase 2 concern, not voice migration |
| Automated agent config deployment (Retell API) | Nice-to-have, manual deploy via Retell admin console is fine |
| CallLock App UI changes | CallLock App receives same payloads, no UI changes needed |
| `book_service` migration to FastAPI | Explicitly kept on CallLock App — revisit only if app is retired |
| Voice agent prompt optimization | Out of scope — port v10 faithfully, optimize later |
| Multi-language support | No current need, ACE Cooling is English-only |

### What already exists

| Sub-problem | Existing code | Reused? |
|---|---|---|
| Tenant isolation / RLS | `db/tenant_scope.py`, migration 005 | Yes |
| DB CRUD | `db/repository.py`, `db/supabase_repository.py` | Yes |
| Cache management | `cache/keys.py` | Yes |
| PII redaction | `observability/pii_redactor.py` | Yes |
| Process call pipeline | `harness/server.py` `/process-call` | Yes |
| Alert evaluation | `evaluate-alerts` Inngest function | Yes |
| Growth touchpoint | `growth-touchpoint` Inngest function | Yes |
| Inngest event schemas | `inngest/src/events/schemas.ts` | Yes (extended) |

### Dream state delta

```
  12-MONTH IDEAL                          THIS PLAN GETS US
  ─────────────                           ──────────────────
  Multi-tenant voice platform             ✅ Multi-tenant from day one
  Per-industry-pack voice configs         ✅ Taxonomy YAML, agent config YAML
  Automated agent tuning via evals        ❌ Not in scope (Expansion)
  Voice-to-text enrichment → growth mem   ✅ calllock/call.ended → growth touchpoint
  Cross-channel attribution               ❌ Not in scope (Growth Phase 2)
  One runtime, one repo                   ✅ Express retired (except book_service on CallLock App)
  Retell agent version management         ⚠️  YAML in knowledge/ but no deployment automation
```

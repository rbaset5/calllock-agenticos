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
    → POST /webhook/retell/{tool_name}
    → auth.py verifies HMAC-SHA256 signature
    → tenant_scope.py sets RLS context from call metadata.tenant_id
    → tool handler executes (external API call or DB query)
    → returns JSON response to Retell
    → Retell LLM continues conversation
```

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
3. Run extraction pipeline (pure functions, no external calls):
   - `post_call.py` — customer name, service address, safety flags from transcript
   - `urgency.py` — urgency inference from keywords
   - `tags.py` — 117-tag HVAC taxonomy classification
   - `call_scorecard.py` — quality score (0-100)
   - `call_type.py` — urgency tier + dashboard level mapping
   - `traffic.py` — traffic controller routing decision
4. Fire Inngest event `calllock/call.ended` with extracted payload
5. Return 200 to Retell

### Asynchronous (Inngest fan-out)

```
calllock/call.ended
  ├→ process-call          (existing) — harness orchestration, job dispatch
  ├→ sync-dashboard        (new)      — transform payload, POST to dashboard webhook
  ├→ evaluate-alerts       (existing) — emergency alert evaluation
  ├→ growth-touchpoint     (existing) — log call as growth touchpoint
  └→ send-emergency-sms    (new, conditional) — only if safety emergency flagged
```

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
    # Raw Retell data
    retell_call_id: str
    call_duration_seconds: int
    end_call_reason: str
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

Stored in the `tenant_configs.config` JSON column (migration 002). No new migration needed — the column is `jsonb` and already supports arbitrary config shapes.

### Credential caching

On the first tool call of a conversation, `VoiceConfig` is fetched from `tenant_configs` via the repository layer and cached in Redis:
- Key: `voice:config:{tenant_id}`
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

## 11. What Gets Retired

| Component | Action |
|---|---|
| Alexandria Express V2 backend (Render) | Decommission after cutover |
| Alexandria Express V3 experimental | Already unused, no action |
| 23 city git worktrees | Archive — deployment artifacts only |
| `retellai-calllock/` workspace | Archive after migration complete |
| Node.js/TypeScript runtime for voice | Eliminated entirely |

## 12. Dependencies

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

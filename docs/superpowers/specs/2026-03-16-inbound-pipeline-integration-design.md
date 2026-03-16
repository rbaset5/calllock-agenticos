# Inbound Pipeline Integration Design

**Date:** March 16, 2026
**Status:** Draft
**Owner:** Founder

## Summary

Port the atlas inbound email processing pipeline into AgentOS as shared Python infrastructure. Both organic inbound emails and outbound reply classification use the same pipeline with a `source` mode flag. The Instantly sending transport lives as a shared Python client in the harness, with an MCP server deferred but designed for.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Port strategy | Rewrite to Python | Follow AgentOS runtime split: Python harness owns orchestration, LLM calls, persistence |
| IMAP polling | Inngest cron → harness endpoint | Consistent with existing event-driven architecture |
| Pipeline structure | Single pipeline, mode flag | ~80% shared logic (quarantine, gate, research, draft, stage). Mode flag is clean branching |
| Persistence | Hybrid schema | New tables for inbound-specific data; shared Growth Memory for lifecycle and research |
| Instantly | Shared client in harness, MCP deferred | One implementation, MCP wrapper added when voice agent needs it |

## 1. Architecture Overview

### Flow

```
Inngest cron (calllock/inbound.poll.requested)
  → TS handler POSTs to harness /inbound/poll
    → Python harness connects to IMAP, fetches messages
      → For each message, emits calllock/inbound.message.received
        → TS handler POSTs to harness /inbound/process
          → Python pipeline: quarantine → research → score → stage → draft → escalate
            → Writes to Supabase (hybrid schema)
```

### Runtime split

- **TypeScript (Inngest):** cron trigger, event emission, thin HTTP proxies to harness
- **Python (harness):** all business logic — IMAP connection, quarantine, scoring, drafting, stage tracking, persistence

### Single pipeline, mode flag

`process_message(msg, source='organic'|'reply')` — quarantine is identical, scoring injects prospect context for replies, stage tracker checks existing stage for replies vs. assigns fresh for organic.

## 2. Persistence — Hybrid Schema

### New Supabase tables (inbound-specific)

| Table | Purpose | Write owner |
|---|---|---|
| `inbound_messages` | Raw ingested messages with quarantine results | Inbound Pipeline |
| `inbound_drafts` | Generated reply drafts with reviewer verdict | Inbound Pipeline |
| `poll_checkpoints` | IMAP UID checkpoint per account/folder | Inbound Pipeline |

### Mapped into existing Growth Memory tables

| Atlas table | Maps to | How |
|---|---|---|
| `scores` | `touchpoint_log` (deferred) | Touchpoints are written only after promotion, when `prospect_id` exists. See Section 10 for the promotion flow. |
| `stages` | `inbound_stage_log` (new) | Inbound stages are tracked separately from Growth Memory lifecycle. See Section 10 for reconciliation. The pipeline does NOT write to `journey_assignments` — the Journey Orchestrator does, triggered by `calllock/inbound.prospect.promoted`. |
| `sender_research` | `enrichment_cache` (new) | Both inbound sender research and outbound prospect enrichment write here. A `source` column discriminates. TTL-based cache lookup. |

### New migration

`047_inbound_pipeline.sql` creates `inbound_messages`, `inbound_drafts`, `inbound_stage_log`, `poll_checkpoints`, `enrichment_cache`, `prospect_emails`, and `email_accounts`. All tenant-scoped with RLS via `current_tenant_id()`. RLS follows the same `ENABLE ROW LEVEL SECURITY` / `FORCE ROW LEVEL SECURITY` / `CREATE POLICY ... USING (tenant_id = public.current_tenant_id())` pattern from migration 005/046.

### Promotion path

When an organic inbound lead qualifies (scores `exceptional` or `high`), the pipeline:

1. Creates a prospect record (writes to `prospect_emails` with the sender's email)
2. Updates `inbound_messages.prospect_id` with the new prospect ID
3. Writes a `touchpoint_log` entry with `touchpoint_type='inbound_scored'` (now that `prospect_id` exists)
4. Emits `calllock/inbound.prospect.promoted`
5. The Journey Orchestrator handles creating the `journey_assignments` record

Touchpoints for unpromoted organic leads are NOT written to `touchpoint_log` (which requires `prospect_id NOT NULL`). The scoring data lives in `inbound_messages` until promotion. This avoids creating placeholder prospects that pollute Growth Memory with noise.

## 3. Python Module Structure

```
harness/src/inbound/
├── __init__.py              # Public API exports
├── types.py                 # Dataclasses: ParsedMessage, QuarantineResult, ScoringResult, etc.
├── config.py                # Load YAML config with defaults
├── quarantine.py            # strip_html, neutralize_links, detect_injection, run_full_quarantine
├── researcher.py            # is_private_ip, resolve_domain, fetch_homepage, research_sender
├── scorer.py                # compute_rubric_hash, parse_score_response, score_message
├── stage_tracker.py         # TRANSITIONS dict, is_valid_transition, assign_initial_stage, transition_stage, detect_drift
├── content_gate.py          # scan_draft — deterministic safety check on generated drafts
├── drafter.py               # select_template, fill_fallback_template, generate_draft (two-layer with reviewer)
├── escalation.py            # should_escalate, should_auto_archive, build_escalation_message
├── backfill.py              # is_new_domain, backfill_domain
├── imap_client.py           # connect_imap, fetch_new_messages (using imapclient)
├── pipeline.py              # process_message(msg, source), run_poll()
└── repository.py            # InboundRepository — Supabase CRUD
```

### Library swaps

| Atlas (TS) | AgentOS (Python) |
|---|---|
| `better-sqlite3` | `supabase-py` via existing repository pattern |
| `imapflow` | `imapclient` |
| `linkedom` | `beautifulsoup4` |
| Custom LLM router | Harness LLM integration |
| `node:crypto` SHA-256 | `hashlib` |

### Repository pattern

`InboundRepository` extends the existing `SupabaseRepository` pattern. Uses `tenant_scope.py` for RLS context. Shared Growth Memory writes go through `harness/src/growth/memory/repository.py`.

## 4. Inngest Events and Functions

### New events

| Event | Trigger | Payload |
|---|---|---|
| `calllock/inbound.poll.requested` | Inngest cron (default hourly) | `{ tenant_id, account_ids?: string[] }` |
| `calllock/inbound.message.received` | Poll handler per message | `{ tenant_id, account_id, message_id, from_addr, from_domain, subject, source: 'organic' \| 'reply' }` |
| `calllock/inbound.message.processed` | After pipeline completes | `{ tenant_id, message_id, action, total_score, stage, draft_generated: boolean }` |
| `calllock/inbound.escalation.triggered` | When escalation fires | `{ tenant_id, message_id, priority, channel }` |

### New Inngest functions

```
inngest/src/functions/inbound/
├── fan-out-poll.ts          # Cron → POST /inbound/tenants → emits per-tenant poll events
├── poll-inbound.ts          # On poll.requested → POST /inbound/poll
├── process-message.ts       # On message.received → POST /inbound/process
├── retry-scoring.ts         # Cron (every 15min) → POST /inbound/retry-scoring
```

Thin HTTP proxies. No business logic in TypeScript.

**Fan-out architecture:** A global Inngest cron (every hour) calls `fan-out-poll.ts`, which POSTs to a harness endpoint `/inbound/tenants` that returns all tenant IDs with enabled email accounts. The TS function then emits one `calllock/inbound.poll.requested` per tenant. This keeps the tenant query logic in Python (no business logic in TypeScript).

**Scoring retry:** A separate cron (every 15 minutes) calls `retry-scoring.ts`, which POSTs to `/inbound/retry-scoring`. The harness queries `inbound_messages WHERE scoring_status = 'pending' AND created_at > now() - interval '24 hours'` and re-processes each (up to `scoring.retry_max_attempts`).

### Harness endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/inbound/tenants` | POST | Return tenant IDs with enabled email accounts (fan-out source) |
| `/inbound/poll` | POST | Connect IMAP, fetch messages, emit events |
| `/inbound/process` | POST | Run full pipeline for one message |
| `/inbound/retry-scoring` | POST | Re-process messages with `scoring_status='pending'` |

### Reply integration

Reply Classifier Agent emits `calllock/inbound.message.received` with `source: 'reply'` — same event, same pipeline, mode flag routes appropriately.

## 5. Instantly Client and Safety

### Instantly client

Location: `harness/src/integrations/instantly.py`

```python
class InstantlyClient:
    send(to, subject, body, account_id, ...)
    check_reply(campaign_id, email)
    get_warmup_status(account_id)
    get_send_log(account_id, since)
    check_reputation(account_id)
```

Guardrails built into the client:
- Rate limiting per account
- Warmup-aware sending (refuse below threshold)
- Bounce/complaint rate check before send
- Dedup window (configurable)

MCP server wraps this class later — zero duplication.

### Quarantine — two layers

**Layer 1: Deterministic (no LLM)**
- `strip_html` — BeautifulSoup4
- `neutralize_links` — regex
- `detect_injection` — 9 regex patterns ported verbatim from atlas
- Any injection pattern → `status: 'blocked'`, message stops

**Layer 2: Semantic (LLM classifier, fail-closed)**
- Harness LLM classifies sanitized text
- Anything other than `SAFE` → blocked
- Classifier error → blocked (fail-closed)
- No classifier configured → skip layer

### Content gate on drafts

`scan_draft` runs deterministic injection patterns on generated draft text. Blocks drafts that echo injected content from the original message. Fail-closed.

### Safety invariant

No message reaches scoring without passing quarantine. No draft reaches persistence without passing the content gate.

## 6. Data Flow — Organic vs Reply

### Organic inbound (`source='organic'`)

```
IMAP fetch → quarantine → research_sender(domain, cache_ttl)
  → score_message(text, research, rubric)
    → assign_initial_stage(action)
      → insert journey_assignment (fresh, step 1)
        → generate_draft(action, template)
          → escalate or auto_archive
            → if score >= 'high': create prospect in Growth Memory
```

### Outbound reply (`source='reply'`)

```
Reply event → quarantine → lookup prospect via prospect_emails
  → score_message(text, research + prospect_context, rubric)
    → existing_stage = get from inbound_stage_log WHERE thread_id = X ORDER BY created_at DESC
      → transition_stage(existing_stage, inferred_stage) → write to inbound_stage_log
        → generate_draft(action, template, prospect_context)
          → escalate or auto_archive
            → write touchpoint_log with reply classification (prospect_id already exists)
```

If prospect not found via `prospect_emails`, falls back to organic path (see Section 11).

### Branching points

1. **Research:** Organic calls `research_sender()` fresh. Reply pulls existing enrichment from `enrichment_cache` + Growth Memory.
2. **Scoring context:** Both use `score_message()`. Reply injects `prospect_context` (segment, experiment arm, sequence position, prior touchpoints) to shift from "is this a good lead?" to "what kind of reply is this?"
3. **Stage tracking:** Organic calls `assign_initial_stage()` → writes to `inbound_stage_log`. Reply calls `transition_stage()` → validates transition from current stage in `inbound_stage_log`.

Everything else is shared: quarantine, content gate, draft generation, escalation, persistence, event emission.

## 7. Source Material

The atlas inbound pipeline (13 commits, `e31de22..6f29bc7`) provides the reference implementation:

- `src/inbound/quarantine.ts` — 9 injection patterns, HTML strip, link neutralization
- `src/inbound/scorer.ts` — rubric hashing, JSON response parsing, LLM scoring call
- `src/inbound/stage-tracker.ts` — 7-state machine with transition validation and drift detection
- `src/inbound/drafter.ts` — two-layer draft generation with reviewer fallback
- `src/inbound/content-gate.ts` — deterministic draft safety scan
- `src/inbound/researcher.ts` — SSRF-protected domain research with caching
- `src/inbound/escalation.ts` — priority mapping and NotifyQ integration
- `src/inbound/backfill.ts` — new domain detection and historical thread fetch
- `src/inbound/imap-client.ts` — IMAP connection, folder management, message fetch
- `src/inbound/poll.ts` — main orchestrator (`processMessage` + `runPoll`)
- `src/inbound/db.ts` — SQLite schema (6 tables) and repository class
- `data/rubric.md` — scoring rubric
- `data/templates/` — draft templates by action tier (exceptional, high, medium, low)
- 12 test files covering all modules

All recoverable via `git checkout 6f29bc7 -- src/inbound/ data/rubric.md data/templates/` in the atlas repo.

## 8. Dependencies

### Python packages (add to `harness/requirements.txt`)

- `imapclient` — IMAP protocol
- `beautifulsoup4` — HTML → text
- `pyyaml` — config loading (likely already present)

### Inngest package (already present)

No new TS dependencies needed for the thin proxy functions.

### Rubric and templates

Port `data/rubric.md` and `data/templates/*.md` into `knowledge/inbound/` as knowledge files with proper frontmatter.

## 9. Table Schemas

### `inbound_messages`

```sql
CREATE TABLE public.inbound_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,
    rfc_message_id      TEXT NOT NULL,          -- RFC 5322 Message-ID header (idempotency key)
    thread_id           TEXT NOT NULL,
    imap_uid            INTEGER NOT NULL,
    from_addr           TEXT NOT NULL,
    from_domain         TEXT NOT NULL,
    to_addr             TEXT NOT NULL,
    subject             TEXT NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL,
    body_text           TEXT NOT NULL,           -- sanitized text after quarantine
    source              TEXT NOT NULL DEFAULT 'organic'
                        CHECK (source IN ('organic', 'reply')),
    quarantine_status   TEXT NOT NULL
                        CHECK (quarantine_status IN ('clean', 'blocked', 'pending_scoring')),
    quarantine_flags    JSONB DEFAULT '[]',
    quarantine_reason   TEXT,
    prospect_id         UUID,                    -- linked on promotion or reply path lookup
    scoring_status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (scoring_status IN ('pending', 'scored', 'failed', 'skipped')),
    action              TEXT,                    -- exceptional, high, medium, low, spam, non-lead
    total_score         INTEGER,
    score_dimensions    JSONB DEFAULT '{}',
    score_reasoning     TEXT,
    rubric_hash         TEXT,
    stage               TEXT DEFAULT 'new'
                        CHECK (stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, rfc_message_id)           -- dedup on RFC Message-ID per tenant
);

CREATE INDEX idx_inbound_msg_domain ON public.inbound_messages (tenant_id, from_domain);
CREATE INDEX idx_inbound_msg_thread ON public.inbound_messages (tenant_id, thread_id);
CREATE INDEX idx_inbound_msg_prospect ON public.inbound_messages (tenant_id, prospect_id)
    WHERE prospect_id IS NOT NULL;
CREATE INDEX idx_inbound_msg_pending ON public.inbound_messages (tenant_id, scoring_status)
    WHERE scoring_status = 'pending';
```

Design note: Scoring data is denormalized onto `inbound_messages` rather than a separate `scores` table. Each message is scored once; rescoring overwrites. The atlas `scores` table was a separate table because SQLite has no JSONB and the code predates the single-table decision. In Supabase with JSONB, the join is unnecessary overhead.

### `inbound_drafts`

```sql
CREATE TABLE public.inbound_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    message_id          UUID NOT NULL REFERENCES public.inbound_messages(id),
    thread_id           TEXT NOT NULL,
    action              TEXT NOT NULL,            -- the action tier that triggered the draft
    template_used       TEXT NOT NULL,
    draft_text          TEXT NOT NULL,
    source              TEXT NOT NULL             -- 'llm' or 'fallback_template'
                        CHECK (source IN ('llm', 'fallback_template')),
    reviewer_verdict    TEXT,                     -- 'approved', 'revised', 'rejected'
    content_gate_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (content_gate_status IN ('passed', 'blocked', 'pending')),
    content_gate_flags  JSONB DEFAULT '[]',
    send_status         TEXT NOT NULL DEFAULT 'pending_review'
                        CHECK (send_status IN ('pending_review', 'approved', 'sent', 'rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, message_id)               -- at most one draft per message
);

CREATE INDEX idx_inbound_draft_msg ON public.inbound_drafts (tenant_id, message_id);
CREATE INDEX idx_inbound_draft_review ON public.inbound_drafts (tenant_id, send_status)
    WHERE send_status = 'pending_review';
```

### `poll_checkpoints`

```sql
CREATE TABLE public.poll_checkpoints (
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,
    folder              TEXT NOT NULL DEFAULT 'INBOX',
    last_uid            INTEGER NOT NULL DEFAULT 0,
    last_polled_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    poll_status         TEXT NOT NULL DEFAULT 'ok'
                        CHECK (poll_status IN ('ok', 'error')),
    last_error          TEXT,
    PRIMARY KEY (tenant_id, account_id, folder)
);
```

### `enrichment_cache`

```sql
CREATE TABLE public.enrichment_cache (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    cache_key           TEXT NOT NULL,            -- domain for sender research, company_domain for outbound enrichment
    cache_type          TEXT NOT NULL             -- 'sender_research' or 'prospect_enrichment'
                        CHECK (cache_type IN ('sender_research', 'prospect_enrichment')),
    source              TEXT NOT NULL             -- 'inbound_pipeline' or 'enrichment_agent'
                        CHECK (source IN ('inbound_pipeline', 'enrichment_agent')),
    data                JSONB NOT NULL,           -- homepage text, resolved IPs, enrichment fields
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cache_key, cache_type)
);

CREATE INDEX idx_enrichment_ttl ON public.enrichment_cache (tenant_id, cache_type, fetched_at);
```

TTL is application-level: queries filter `WHERE fetched_at > now() - interval '7 days'` (configurable). A daily Inngest cron (`calllock/enrichment.cleanup.requested`) triggers a harness endpoint that deletes rows older than 2x TTL (14 days default). This is specified in the fan-out cron alongside the poll cron.

### `prospect_emails` (email-to-prospect mapping)

```sql
CREATE TABLE public.prospect_emails (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    email               TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'outbound'
                        CHECK (source IN ('outbound', 'inbound', 'manual')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE INDEX idx_prospect_email_lookup ON public.prospect_emails (tenant_id, email);
CREATE INDEX idx_prospect_email_prospect ON public.prospect_emails (tenant_id, prospect_id);
```

This table resolves the reply path's need to map `from_addr → prospect_id`. The outbound Sender Agent writes here when sending. The inbound pipeline writes here on promotion.

**Backfill for existing prospects:** On initial deployment, a one-time migration script populates `prospect_emails` from existing prospect data (sourced from whatever system currently holds prospect email addresses). Until backfill completes, replies from pre-existing prospects will follow the orphaned-reply fallback path (treated as organic). This is acceptable for the initial deployment window.

## 10. Stage Machine Reconciliation

The atlas inbound pipeline uses a 7-state deal qualification machine: `new → qualified → engaged → negotiation → won / lost / archived`.

The Growth System design doc defines a 13-state prospect lifecycle: `UNKNOWN → REACHED → ENGAGED → EVALUATING → IN_PIPELINE → PILOT_STARTED → CUSTOMER` plus extended states.

**Resolution:** These are different models serving different purposes.

- The **inbound stage machine** tracks where an inbound lead is in the qualification funnel. It is internal to the inbound pipeline.
- The **Growth Memory lifecycle** tracks where a prospect is in the sales/customer journey. It is shared across all growth components.

The inbound pipeline does NOT write directly to `journey_assignments`. Instead:

1. Inbound stages are tracked in a new `stage` TEXT column on `inbound_messages` (values: `new`, `qualified`, `engaged`, `negotiation`, `won`, `lost`, `archived`).
2. Stage transitions are recorded in an `inbound_stage_log` append-only table.
3. When a lead is **promoted** to a prospect (scores `high` or `exceptional`), the pipeline emits `calllock/inbound.prospect.promoted`. The Journey Orchestrator handles creating the `journey_assignments` record with the correct Growth Memory lifecycle state.

This preserves single-writer ownership of `journey_assignments` (Journey Orchestrator) and eliminates the stage machine mismatch.

### `inbound_stage_log`

```sql
CREATE TABLE public.inbound_stage_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    message_id          UUID NOT NULL REFERENCES public.inbound_messages(id),
    thread_id           TEXT NOT NULL,
    from_stage          TEXT                      -- NULL for initial assignment
                        CHECK (from_stage IS NULL OR from_stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    to_stage            TEXT NOT NULL
                        CHECK (to_stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    changed_by          TEXT NOT NULL,            -- 'inbound_pipeline', 'founder', etc.
    reason              TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_inbound_stage_thread ON public.inbound_stage_log (tenant_id, thread_id, created_at);
```

### Stage-to-lifecycle mapping (on promotion)

| Inbound stage | Growth Memory lifecycle state |
|---|---|
| `new` | `UNKNOWN` |
| `qualified` | `EVALUATING` |
| `engaged` | `ENGAGED` |
| `negotiation` | `IN_PIPELINE` |
| `won` | `PILOT_STARTED` |
| `lost` | `LOST` |
| `archived` | `DORMANT` |

This mapping is used only at promotion time. The Journey Orchestrator applies it when handling `calllock/inbound.prospect.promoted`.

## 11. Failure Modes

### Scoring LLM unavailable

**Fail-deferred.** The message is persisted in `inbound_messages` with `scoring_status: 'pending'`. A retry mechanism re-processes pending messages on the next poll cycle or via a dedicated retry Inngest function. This differs from quarantine (fail-closed) because a quarantine failure is a safety risk; a scoring failure is a latency risk.

### Draft generation LLM unavailable

**Fallback to template.** The `fill_fallback_template` function generates a draft from the static template without LLM personalization. The draft is persisted with `source: 'fallback_template'`. The content gate still runs on fallback drafts.

### IMAP connection failure

**Per-account isolation, logged, retried next cycle.** If account 3 of 5 fails, accounts 4-5 still get polled. The `poll_checkpoints` table records `poll_status: 'error'` and `last_error`. An alert fires if the same account fails 3 consecutive polls (emits `calllock/inbound.poll.failed`).

### IMAP connection drops mid-fetch

**Per-message checkpoint.** The checkpoint is updated after each message is successfully emitted as an event. If the connection drops after message 50 of 200, the checkpoint is at message 50. The next poll re-fetches from 51. Combined with `UNIQUE (tenant_id, rfc_message_id)` dedup, at-least-once semantics are safe.

### Reply arrives but prospect not in Growth Memory

**Fallback to organic path.** If the reply path cannot find a `prospect_id` via `prospect_emails`, it re-routes to the organic path (`source` stays `'reply'` for audit trail, but processing follows the organic logic). A warning event `calllock/inbound.reply.orphaned` is emitted for reconciliation.

### Content gate blocks a draft

Draft is persisted with `content_gate_status: 'blocked'` and `content_gate_flags`. Event `calllock/inbound.draft.blocked` is emitted. The message processing continues (score and stage are already recorded). `message.processed` event has `draft_generated: false`.

### Cross-path dedup

The same email arriving via IMAP (organic) and Reply Classifier (reply) hits the `UNIQUE (tenant_id, rfc_message_id)` constraint on `inbound_messages`. The second insert is a no-op (ON CONFLICT DO NOTHING). The first path wins.

## 12. Additional Events

| Event | Trigger | Payload |
|---|---|---|
| `calllock/inbound.poll.failed` | Account fails 3 consecutive polls | `{ tenant_id, account_id, error, consecutive_failures }` |
| `calllock/inbound.quarantine.blocked` | Message blocked by quarantine | `{ tenant_id, rfc_message_id, flags, block_reason }` |
| `calllock/inbound.draft.blocked` | Draft blocked by content gate | `{ tenant_id, message_id, flags }` |
| `calllock/inbound.prospect.promoted` | Organic lead promoted to prospect | `{ tenant_id, prospect_id, message_id, inbound_stage, lifecycle_state }` |
| `calllock/inbound.reply.orphaned` | Reply has no matching prospect | `{ tenant_id, from_addr, rfc_message_id }` |

## 13. IMAP Credential Storage

IMAP account credentials are stored in a new `email_accounts` table:

```sql
CREATE TABLE public.email_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,            -- human-readable identifier
    imap_host           TEXT NOT NULL,
    imap_port           INTEGER NOT NULL DEFAULT 993,
    imap_username       TEXT NOT NULL,
    imap_auth_type      TEXT NOT NULL DEFAULT 'password'
                        CHECK (imap_auth_type IN ('password', 'oauth2')),
    imap_credential     TEXT NOT NULL,            -- encrypted at application level before storage
    folders             JSONB DEFAULT '["INBOX"]',
    enabled             BOOLEAN NOT NULL DEFAULT true,
    features            JSONB DEFAULT '{"labels": false, "stage_tracking": true, "draft_generation": true, "escalation": true, "auto_archive": true}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_id)
);
```

RLS ensures tenants can only access their own accounts. `imap_credential` is encrypted using AES-256-GCM by the harness before write and decrypted on read. The encryption key is stored in environment variable `IMAP_CREDENTIAL_KEY` (32-byte base64-encoded). Key rotation: write new credentials with the new key, re-encrypt existing rows via a migration script, remove the old key. Supabase default encryption is not sufficient for credentials.

The poll cron emits one `calllock/inbound.poll.requested` event per tenant, with `account_ids` left null to poll all enabled accounts for that tenant. A fan-out Inngest function queries `email_accounts WHERE enabled = true` per tenant.

## 14. Idempotency

**Message-level idempotency key:** RFC 5322 `Message-ID` header, stored as `rfc_message_id` in `inbound_messages` with a `UNIQUE (tenant_id, rfc_message_id)` constraint.

**Event-level idempotency:** The `calllock/inbound.message.received` event carries `rfc_message_id` (not a generated UUID) and sets Inngest's `idempotencyKey` to `inbound:${tenant_id}:${rfc_message_id}` with a 24-hour dedup window (sufficient given the hourly poll cycle). If the poll handler crashes after emitting an event but before updating the checkpoint, the next poll re-fetches the same message, emits the same event with the same key, and Inngest deduplicates.

**Touchpoint-level idempotency:** When the pipeline writes to `touchpoint_log`, the `touchpoint_id` is derived deterministically: `uuid5(namespace=tenant_id, name=f"inbound:{rfc_message_id}:{touchpoint_type}")`. This prevents duplicate touchpoints on retry.

## 15. Write Ownership Summary

| Table | Write owner | Notes |
|---|---|---|
| `inbound_messages` | Inbound Pipeline | Sole writer |
| `inbound_drafts` | Inbound Pipeline | Sole writer |
| `inbound_stage_log` | Inbound Pipeline | Sole writer |
| `poll_checkpoints` | Inbound Pipeline | Sole writer |
| `email_accounts` | Admin / onboarding | Not written by pipeline |
| `enrichment_cache` | Inbound Pipeline + Enrichment Agent | Multi-writer, discriminated by `source` column |
| `prospect_emails` | Sender Agent + Inbound Pipeline | Multi-writer, discriminated by `source` column |
| `touchpoint_log` | Inbound Pipeline (append) | Already multi-writer by design |
| `journey_assignments` | Journey Orchestrator only | Inbound pipeline emits events; Journey Orchestrator writes |

## 16. Observability

### Counters

- `inbound.messages.polled` — per account, per poll cycle
- `inbound.messages.quarantined` — per quarantine flag type
- `inbound.messages.scored` — per action tier
- `inbound.messages.promoted` — organic leads becoming prospects
- `inbound.drafts.generated` — per source (llm / fallback_template)
- `inbound.drafts.blocked` — content gate rejections
- `inbound.escalations.triggered` — per priority
- `inbound.poll.failures` — per account

### Gauges

- `inbound.poll.latency_ms` — time to complete a poll cycle
- `inbound.process.latency_ms` — time to process a single message
- `inbound.checkpoint.lag_messages` — estimated messages behind (if knowable)
- `inbound.scoring.pending_count` — messages awaiting scoring retry

### Alerts

- Poll failure for same account 3+ consecutive times
- Quarantine rate exceeds 50% of messages in a 24h window (possible injection campaign)
- Scoring retry queue depth exceeds 100
- Zero messages polled for 48+ hours (possible IMAP credential expiry)

## 17. Quarantine Patterns Reference

Ported from atlas `src/inbound/quarantine.ts`. Python `re` equivalents verified — all patterns use features common to both JS and Python regex engines (case-insensitive flag, word boundaries, basic alternation).

| Flag | Pattern |
|---|---|
| `role_marker` | `\b(system\|assistant\|user)\s*:` |
| `directive_override` | `ignore\s+(previous\|above\|all)\s+instructions` |
| `identity_manipulation` | `act\s+as\s+(a\|an\|the)?\s*\w+` |
| `identity_manipulation` | `you\s+are\s+now\s+(a\|an\|the)?\s*\w+` |
| `directive_override` | `\bdo\s+not\s+follow\b` |
| `directive_override` | `\bnew\s+instructions?\b` |
| `directive_override` | `\boverride\b.*\b(rules?\|instructions?\|policy)` |
| `directive_override` | `\bforget\b.*\b(rules?\|instructions?\|everything)` |
| `code_fence_injection` | ` ```\s*(system\|prompt\|instruction)` |

All compiled with `re.IGNORECASE`.

## 18. Configuration Schema

```yaml
# config/inbound.yaml
database_url: ${SUPABASE_URL}        # from environment
rubric_path: knowledge/inbound/rubric.md
templates_path: knowledge/inbound/templates/

polling:
  default_interval_minutes: 60
  imap_timeout_seconds: 30
  batch_size: 200                     # max messages per poll cycle
  backfill_max_messages: 50

scoring:
  model: claude-sonnet-4-5-20250514
  max_tokens: 1024
  temperature: 0.1
  retry_max_attempts: 3
  retry_delay_seconds: 60

drafting:
  writer_model: claude-sonnet-4-5-20250514
  reviewer_model: claude-sonnet-4-5-20250514
  max_tokens: 2048

research:
  cache_ttl_hours: 168                # 7 days
  fetch_timeout_seconds: 10
  blocked_ip_ranges:                  # SSRF protection
    - "10.0.0.0/8"
    - "172.16.0.0/12"
    - "192.168.0.0/16"
    - "127.0.0.0/8"
    - "169.254.0.0/16"
    - "::1/128"
    - "fc00::/7"

escalation:
  backend: incidents                  # 'incidents' | 'stdout'
  consecutive_poll_failure_threshold: 3
  quarantine_rate_alert_threshold: 0.5

backfill:
  enabled: true
  max_messages: 50
```

## 19. Backfill Module

**Purpose:** When a new sender domain appears for the first time, the pipeline searches the IMAP folder for older messages from the same domain and processes them retroactively. This ensures historical context is captured for scoring and research.

**When it runs:** Synchronously within `run_poll()`, before processing the current message. If `is_new_domain(tenant_id, account_id, from_domain)` returns true (no prior messages from that domain in `inbound_messages`), `backfill_domain()` fetches up to `backfill.max_messages` historical messages from the same domain and processes each through the full pipeline.

**Safeguard:** Backfilled messages are processed with the same quarantine, scoring, and stage logic. They emit the same events. The per-message checkpoint ensures backfilled messages are not re-processed.

**Disable:** Set `backfill.enabled: false` in config to skip.

# ADR 004: Event Idempotency and Dead-Letter Queue Contract

Status: Proposed

## Context

The design doc requires idempotency on all event handlers (Principle 5.9) and a dead-letter queue for unrecoverable events (Rule 5 of Universal Rescue Doctrine). Inngest provides at-least-once delivery with automatic retries. The idempotency key format (`event_type + entity_id + timestamp_bucket`) is defined in principle but not concretely enough to implement from:

1. `timestamp_bucket` resolution is undefined — wrong resolution causes duplicate processing on retry
2. DLQ backing store is unspecified — can't build DLQ depth metrics without knowing where events land
3. Per-handler idempotency keys are not listed — implementer must invent them

## Decision

### Idempotency model

**Do NOT use timestamp_bucket.** Inngest retry windows (seconds to minutes) make any bucket resolution either too narrow (duplicates on retry) or too wide (legitimate re-processing blocked).

Instead, use **natural idempotency keys** — the identity of the thing being processed, not the event delivery:

```
HANDLER                         IDEMPOTENCY KEY                     DEDUP MECHANISM
────────────────────────────── ──────────────────────────────────── ────────────────
handle-touchpoint               touchpoint_id (UUID, set by sender) UNIQUE constraint on touchpoint_log.touchpoint_id
handle-lifecycle-transition     prospect_id + to_state + trigger_id UNIQUE constraint on lifecycle_transitions(prospect_id, to_state, trigger_id)
handle-experiment-outcome       experiment_id + arm_id + prospect_id UNIQUE constraint on experiment_outcomes(experiment_id, arm_id, prospect_id)
handle-belief-inference         touchpoint_id                       UNIQUE constraint on belief_events.source_touchpoint_id
handle-growth-memory-write      source_component + entity_id + ver  UPSERT with version counter (existing pattern from §7.10)
growth-advisor-weekly           run_date (YYYY-MM-DD)               Idempotent by output: weekly digest for same date replaces previous
combination-discovery-weekly    run_date (YYYY-MM-DD)               Idempotent by output: same date re-run replaces previous results
```

**Enforcement:** Idempotency is enforced at the database level via UNIQUE constraints, not application logic. A duplicate event hits the constraint, the handler catches the unique violation, logs it as a dedup hit, and returns success (not error). Inngest sees success and does not retry.

```python
# Pattern for all growth event handlers:
async def handle_touchpoint(event: TouchpointEvent) -> None:
    try:
        await growth_memory.write_touchpoint(event)
    except UniqueViolation:
        logger.info("dedup_hit", touchpoint_id=event.touchpoint_id)
        return  # success — Inngest will not retry
    except Exception as e:
        # Re-raise — Inngest will retry
        raise
```

### Dead-letter queue

**DLQ backing store: Supabase table.**

Rationale: DLQ events need to be queryable (for the weekly founder review), persistent (survive Redis flushes and Inngest retention windows), and tenant-scoped (RLS applies). A Supabase table satisfies all three. Redis and Inngest DLQ features do not provide tenant-scoped queryability.

```sql
CREATE TABLE growth_dead_letter_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    event_type      TEXT NOT NULL,
    event_payload   JSONB NOT NULL,
    error_class     TEXT NOT NULL,
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    source_version  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    resolution      TEXT CHECK (resolution IN ('replayed', 'discarded', 'manual')),
    resolved_by     TEXT
);

-- RLS
ALTER TABLE growth_dead_letter_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE growth_dead_letter_queue FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON growth_dead_letter_queue
    USING (tenant_id = current_setting('app.current_tenant')::UUID);

-- Index for dashboard metric (DLQ depth per tenant)
CREATE INDEX idx_dlq_unresolved ON growth_dead_letter_queue (tenant_id, created_at)
    WHERE resolved_at IS NULL;
```

**DLQ write path:**

Events enter the DLQ after exhausting Inngest retries (3 attempts by default). The final Inngest failure handler writes to the DLQ:

```typescript
// In Inngest function definition:
inngest.createFunction(
  {
    id: "growth/handle-touchpoint",
    retries: 3,
    onFailure: async ({ event, error }) => {
      await writeToDLQ({
        tenant_id: event.data.tenant_id,
        event_type: event.name,
        event_payload: event.data,
        error_class: error.name,
        error_message: error.message,
        retry_count: 3,
        source_version: process.env.DEPLOY_VERSION || "unknown",
      });
    },
  },
  { event: "growth/touchpoint.logged" },
  async ({ event, step }) => { ... }
);
```

**DLQ read path:**

- Dashboard metric: `SELECT COUNT(*) FROM growth_dead_letter_queue WHERE resolved_at IS NULL` per tenant
- Weekly review: `SELECT * FROM growth_dead_letter_queue WHERE resolved_at IS NULL ORDER BY created_at`
- Resolution: UPDATE `resolved_at`, `resolution`, `resolved_by` after manual review or replay

**DLQ depth alerting:**

- DLQ depth > 10 unresolved events: Growth Advisor includes in weekly digest
- DLQ depth > 50 unresolved events: founder alert (Learning Integrity Monitor)
- DLQ depth growing faster than resolution: CRITICAL alert

### Inngest event naming convention

All growth system events use the `growth/` prefix:

```
growth/touchpoint.logged
growth/prospect.enriched
growth/segment.assigned
growth/segment.transitioned
growth/experiment.created
growth/experiment.winner
growth/experiment.retired
growth/lifecycle.transitioned
growth/message.sent
growth/page.viewed
growth/demo.played
growth/meeting.booked
growth/insight.generated
growth/cost.recorded
growth/doctrine.conflict
```

This separates growth events from harness events (`harness/process-call`) in Inngest's event stream.

## Consequences

- Every growth handler deduplicates at the database level — no application-level dedup state to manage
- Duplicate deliveries are cheap (one failed INSERT, one log line, return success)
- DLQ is queryable per tenant via standard Supabase queries
- DLQ depth is a first-class dashboard metric from day 1
- Inngest `onFailure` hooks are the single entry point to the DLQ — no other code path writes to it
- The `source_version` on DLQ entries enables correlation with quarantine protocol (§7.10)

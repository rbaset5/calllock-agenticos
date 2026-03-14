# ADR 003: Growth System Runtime Placement

Status: Proposed

## Context

The design doc specifies 38+ growth system components. The call-pipeline harness already runs as a Python/LangGraph service on Render (`calllock-harness`). The event bus is Inngest (`calllock-inngest`). The question: where does growth system code run?

Growth system components split into three execution profiles:

| Profile | Examples | Latency requirement | Trigger |
|---------|----------|---------------------|---------|
| Inline (event-driven) | Signal Quality scoring, Belief Layer inference, lifecycle transitions | <5ms per event | Inngest event delivery |
| Request-driven | Thompson sampling posterior lookup, routing decision assembly, Health Gate checks | <100ms per request | Outbound pipeline call |
| Batch (scheduled) | Combination Discovery, Growth Advisor digest, Wedge Fitness snapshot, Content Intelligence | 10min budget | Cron / scheduled Inngest function |

## Decision

### Single codebase, two execution surfaces

All growth system code lives in `harness/src/growth/` as a Python package within the existing harness codebase.

```
harness/
  src/
    harness/          # existing call pipeline
    growth/           # new — growth system
      __init__.py
      events/         # Inngest event handlers (inline profile)
      engine/         # core logic: Thompson sampling, Signal Quality, Belief Layer
      batch/          # scheduled jobs: Growth Advisor, Combination Discovery
      memory/         # Growth Memory read/write abstractions
      gate/           # Outbound Health Gate
```

Growth system code executes via two surfaces:

**Surface 1: Inngest functions (inline + batch profiles)**

Growth event handlers are registered as Inngest functions in `inngest/src/functions/growth/`. Each function validates the event, then calls into the Python growth package via the existing harness HTTP API pattern (same as `process-call`).

```
Inngest event arrives
  → inngest/src/functions/growth/handle-touchpoint.ts
  → HTTP POST to harness /growth/handle-touchpoint
  → harness/src/growth/events/touchpoint_handler.py
  → Signal Quality scoring + Belief inference + Growth Memory write
```

Batch jobs are Inngest cron functions:

```
inngest.createFunction(
  { id: "growth-advisor-weekly" },
  { cron: "0 9 * * 1" },        // Monday 9am UTC
  async ({ step }) => { ... }
);
```

**Surface 2: Harness HTTP API (request-driven profile)**

The existing `harness/src/harness/server.py` (FastAPI) gets a `/growth/` route prefix for growth-specific endpoints:

- `POST /growth/handle-touchpoint` — event handler entry point
- `POST /growth/handle-lifecycle` — lifecycle transition entry point
- `GET /growth/experiment/{id}/allocate` — Thompson sampling allocation
- `POST /growth/gate/check` — Health Gate check
- `GET /growth/metrics/snapshot` — dashboard data

These are internal API routes called by Inngest functions and (later) the Founder Dashboard. They are NOT public endpoints.

### Deployment

Growth system deploys as part of the existing `calllock-harness` Render service. No new Render service.

Rationale: the growth system shares Supabase credentials, Redis, and LiteLLM access with the harness. A separate service would duplicate all connection management. The harness is already a FastAPI server with capacity for additional routes.

### Scaling boundary

If growth system load materially outpaces call pipeline load (measurable via Render metrics), split `harness/src/growth/` into its own Render service. The HTTP API contract stays the same — only the `GROWTH_BASE_URL` config changes.

Revisit when:
- Growth event handler p95 > 200ms (inline handler too slow)
- Harness memory > 80% (growth batch jobs competing with call pipeline)
- Growth API request volume > 10x call pipeline volume

## Consequences

- No new Render service needed now
- Growth code shares the harness's Supabase, Redis, and LiteLLM connections
- Inngest handles retry, scheduling, and at-least-once delivery for all growth events
- Batch jobs run as Inngest cron functions with built-in timeout and retry
- The split path is documented and triggered by observable metrics
- Droid implements growth system Python code in `harness/src/growth/` and TypeScript Inngest handlers in `inngest/src/functions/growth/`

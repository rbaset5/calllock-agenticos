# ADR 008: Tenant-Aware Maintenance Scheduling

Status: Accepted

## Decision

Recurring maintenance and tenant-level eval work is orchestrated every 5 minutes, but executed only for tenants whose configured local hour is due and whose deterministic intra-hour schedule has been reached.

The harness exposes `POST /schedules/due-tenants` for:

- `retention`
- `tenant_eval`

Each tenant config provides:

- `timezone`
- `retention_local_hour`
- `tenant_eval_local_hour`

The scheduler also applies:

- deterministic intra-hour stagger minutes
- per-tick batch caps
- same-hour catch-up for tenants missed earlier in the scheduled hour
- cross-hour carry-forward until the backlog ages out
- persisted backlog records keyed by tenant, job type, and scheduled start time
- claim leases for active scheduler ticks
- atomic claim function in the database-backed path
- explicit completion/release acknowledgements from the scheduler
- heartbeat-based lease extension for long-running work
- a stale-claim sweeper
- operator override for live claims
- cockpit-ready scheduler visibility

Global eval suites remain fixed to one UTC window. Tenant-scoped recurring work follows tenant-local time.

## Rationale

- A single UTC maintenance window is operationally simple but wrong for multi-tenant scheduling.
- Tenant-local execution reduces noisy off-hours work and aligns scheduled processing with tenant expectations.
- Keeping due-tenant selection in the harness avoids duplicating timezone logic in Inngest and keeps the live scheduling policy close to tenant configuration.
- Deterministic intra-hour staggering avoids bunching all due tenants at the top of the hour without requiring extra tenant configuration.
- Per-tick caps let the scheduler spill excess due tenants into later ticks inside the same hour instead of dropping them.
- Existing audit logs are sufficient to prevent duplicate execution within the same scheduled hour.
- `max_schedule_lag_hours` bounds how long missed scheduled work remains eligible for replay.
- Persisting backlog rows makes missed work queryable in the control plane instead of keeping it as an implicit scheduler computation.
- Claim leases reduce duplicate execution by turning scheduler selection into a state transition instead of a pure read.
- The Supabase path now claims rows through a single database function, reducing race windows between concurrent scheduler ticks.
- Explicit completion and release acknowledgements shorten the time rows spend ambiguously claimed after scheduler work finishes or fails.
- Heartbeats let legitimately long-running scheduled work keep its lease without inflating the default claim TTL for every run.
- A dedicated sweep pass releases expired claims even when the normal due path is not active for that job type.
- Operators can now intentionally preempt a claim via force-release or force-claim without waiting for TTL expiry.
- The control plane now exposes a scheduler-focused summary for oldest pending work, soon-expiring claims, and recent scheduler actions.

## Current Limits

- Scheduling is 5-minute granular, not exact-minute granular.
- Local trace fallback and recovery journals are now tenant-partitioned on disk, and retention prunes them per tenant policy while preserving aggregated operator listing/replay APIs.
- The local fallback remains process-local and non-atomic; only the Supabase-backed path has DB-side atomic claims.

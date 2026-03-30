# CallLock AgentOS

CallLock AgentOS is a greenfield monorepo for the multi-tenant harness described in the architecture spec. It combines a Python orchestration service, TypeScript Inngest event wiring, file-backed knowledge graphs, industry packs, and Supabase-backed tenant/compliance data.

If you are starting cold, read [plans/start-here-no-context.md](/Users/rashidbaset/Documents/calllock-agenticos/plans/start-here-no-context.md) first, then [plans/whole-system-executable-master-plan.md](/Users/rashidbaset/Documents/calllock-agenticos/plans/whole-system-executable-master-plan.md).

## Layout

- `knowledge/`: markdown and YAML knowledge graphs, worker specs, and industry packs
- `harness/`: Python harness runtime, health server, cache/db helpers, and worker orchestration
- `inngest/`: TypeScript event schemas and functions for Express V2 -> harness triggers
- `supabase/`: migrations and seed data for tenants, configs, jobs, and compliance rules
- `infra/`: deploy assets such as the LiteLLM proxy
- `scripts/`: validation and extraction scripts
- `tests/`: integration coverage for repository-level checks
- `plans/`: execution plans for Phases 1-4

## Seed Strategy

- `supabase/seed.sql`: realistic, day-to-day CallLock App data for tenant-alpha (`demo-call-*` namespace).
- `supabase/migrations/055_test_tenant_seed.sql`: deterministic fixture data for automated Product Guardian checks.
- `supabase/seed-checks.sql`: optional post-seed verification queries (counts, bucket coverage, callback windows, touch history).

## Phase Scope

This repository now contains an implemented Phase 1-4 backend foundation:

- Phase 1-2: scaffold, knowledge substrate, worker specs, tenant/compliance schema, policy/context/persist harness path, HVAC pack extraction
- Phase 3: multi-worker supervisor routing, deterministic verification outcomes, async jobs, artifact governance, tenant onboarding, kill switches, and alerts
- Phase 4 foundation: improvement experiments with lock isolation, eval fixtures, customer content pipeline, and backend Cockpit APIs

The Founder Cockpit is implemented here as backend/control-plane APIs. A separate frontend application would still need to consume these endpoints.

## Getting Started

### Python harness

```bash
cd harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

Key harness endpoints:

- `POST /process-call`
- `POST /events/process-call`
- `POST /events/job-complete`
- `POST /onboard-tenant`
- `GET /jobs`
- `GET /artifacts?tenant_id=...`
- `POST /artifacts/{artifact_id}/lifecycle`
- `POST /control/kill-switch`
- `GET /alerts`
- `GET /incidents`
- `GET /incidents/{incident_id}/runbook-plan`
- `POST /incidents/{incident_id}/workflow`
- `POST /incidents/{incident_id}/runbook-progress`
- `POST /incidents/{incident_id}/runbook-assignment`
- `POST /incidents/remind-stale`
- `POST /alerts/{alert_id}/status`
- `POST /alerts/evaluate`
- `POST /alerts/escalate-stale`
- `POST /alerts/resolve-recovered`
- `POST /improvement/run-experiment`
- `POST /evals/run`
- `GET /evals/results`
- `GET /recovery/entries`
- `POST /recovery/replay`
- `GET /audit-logs`
- `GET /approvals`
- `POST /approvals/{approval_id}`
- `POST /retention/run`
- `POST /schedules/due-tenants`
- `POST /schedules/claim`
- `POST /schedules/heartbeat`
- `POST /schedules/finalize`
- `POST /schedules/sweep`
- `POST /schedules/override`
- `GET /schedules/backlog`
- `POST /content/process`
- `GET /cockpit/overview`
- `GET /cockpit/scheduler`

### Validation scripts

```bash
node scripts/validate-knowledge.ts
node scripts/validate-worker-specs.ts
node scripts/validate-packs.ts
```

### Local extraction

```bash
node scripts/extract-hvac-pack.ts
```

The extraction script reads from the local V2 source tree under `retellai-calllock/madrid/V2` by default and can be overridden with `CALLLOCK_V2_ROOT`.

### Inngest

```bash
cd inngest
npm install
npm run typecheck
```

Current scheduled functions:

- alert evaluation every 15 minutes
- retention fan-out every 5 minutes with tenant-local staggering, catch-up, and per-tick batch caps
- eval orchestration every 5 minutes with tenant-local staggering, catch-up, and per-tick batch caps
- global core/industry eval runs once daily at 04:00 UTC inside the 5-minute eval scheduler

Scheduler behavior:

- `POST /schedules/due-tenants` returns scheduled metadata including `scheduled_start_at`, `lateness_minutes`, `catch_up`, and capacity fields
- `POST /schedules/claim` leases concrete backlog rows before the scheduler executes them
- `POST /schedules/heartbeat` extends an active scheduler lease for long-running work
- `POST /schedules/finalize` explicitly marks a claimed row completed or releases it back to pending
- `POST /schedules/sweep` proactively releases expired claimed rows
- `POST /schedules/override` lets an operator force-release or take over a live claim
- `GET /schedules/backlog` exposes the persisted pending/completed/expired scheduler backlog
- tenant work carries forward beyond the scheduled hour until processed or until `max_schedule_lag_hours` expires
- `GET /cockpit/scheduler` summarizes scheduler backlog, expiring leases, and recent scheduler activity for operator views

Alert coverage now includes:

- policy block rate
- verification degradation
- job failure spikes
- external service errors
- stale scheduler claims
- aging scheduler backlog

Alert thresholds use repo defaults by default and can be overridden per tenant through `tenant_configs.alert_thresholds`. Alert delivery supports `dashboard`, optional per-tenant `webhook`, `email`, `sms`, and `pager` routing through `tenant_configs.alert_channels`, `tenant_configs.alert_webhook_url`, `tenant_configs.alert_email_to`, `tenant_configs.alert_sms_to`, and `tenant_configs.alert_pager_to`. Email uses SMTP when configured and otherwise falls back to a local outbox for development and testing. SMS and pager delivery use configured webhook transports when present and otherwise fall back to local outboxes. The remaining production gap is tuning those values from live traffic baselines.
Local trace fallback and recovery journals are now partitioned by tenant under `.context/traces/<tenant>/` and `.context/recovery/<tenant>/`, while the listing and replay APIs still aggregate across tenants for operator use. Retention now prunes those local files per tenant policy instead of treating them as one global bucket.

Alerts now carry lifecycle state in the control plane: `open`, `acknowledged`, `escalated`, and `resolved`. The `/alerts/{alert_id}/status` endpoint records operator action metadata and audit logs for acknowledgment, escalation, and resolution.
The scheduled alert pass now includes timeout-based auto escalation. `POST /alerts/escalate-stale` applies severity-aware escalation policy from `tenant_configs.alert_escalation_policy`, re-notifies escalated alerts, and records `alert.auto_escalated` audit events.
Repeated alert evaluations now suppress duplicate unresolved alerts within `tenant_configs.alert_suppression_window_minutes`, updating `occurrence_count` and `last_observed_at` instead of creating duplicate alert rows.
Recovered alert conditions now auto-resolve after `tenant_configs.alert_recovery_cooldown_minutes` below threshold. `POST /alerts/resolve-recovered` resolves eligible alerts, records `alert.auto_resolved` audit events, and is invoked by the scheduled alert pass.
The control plane now also exposes grouped incidents through `GET /incidents`. Incidents roll alert lifecycle changes into a longer-lived `tenant + alert_type` record with cumulative `occurrence_count`, current status, and linked alert ids.
Incident records now preserve episode boundaries as well: reopening the same `tenant + alert_type` after resolution increments `current_episode`/`episode_count` and appends the closed episode to `episode_history`.
Incidents now also carry operator workflow separate from alert health. `POST /incidents/{incident_id}/workflow` updates `workflow_status`, assignee, notes, and last reviewer metadata without mutating the underlying alert rows.
Assigned incidents now trigger assignee-aware delivery and reminder passes. `POST /incidents/remind-stale` sends reminder notifications for assigned incidents whose `last_reviewed_at` is older than `tenant_configs.incident_reminder_minutes`. Incident delivery supports `dashboard`, `assignee_webhook`, `assignee_email`, `assignee_sms`, and `assignee_pager`, with assignee email using the same SMTP-or-outbox path as alerts and assignee SMS/pager using the same webhook-or-outbox paths as the alert transports.
Incident assignment is now availability-aware as well. Assignee records in `tenant_configs.incident_assignees` can declare availability windows and `fallback_assignee`, while `incident_default_assignee` and `incident_reassign_after_reminders` drive fallback routing when the preferred assignee is unavailable or unresponsive.
Tenants can also define `incident_oncall_rotation` plus `incident_rotation_interval_hours` for time-bucketed primary selection across an on-call pool before fallback logic applies.
Within that pool, routing is now weighted and capacity-aware: assignee records can declare `routing_weight` and `max_active_incidents`, and the resolver prefers the best effective score before using rotation order as a tie-breaker.
Incidents now also carry normalized classification fields: `incident_domain`, `incident_category`, `remediation_category`, and `incident_urgency`. Tenant-specific `incident_classification_rules` can override the default mapping from raw alert types, and skill routing now uses those normalized categories first before falling back to raw `alert_type` strings.
Skill matching now sits above the remaining tie-breakers: `tenant_configs.incident_skill_requirements` can define required skills by normalized incident category, remediation category, domain, or legacy alert type, and assignee records can declare `skills` so the resolver prefers qualified operators before comparing load, capacity, or weight.
Incidents can now also bind to resolved runbooks through `tenant_configs.incident_runbooks`. Those bindings persist `runbook_id`, `runbook_title`, `runbook_steps`, and `approval_policy` on the incident record, and workflow changes can require an approval request before the incident is allowed to move into protected states such as `closed`.
Runbook execution is now tracked per step as well. Incidents persist `runbook_progress` and `runbook_progress_summary`, and `POST /incidents/{incident_id}/runbook-progress` updates checklist state without implicitly changing workflow or assignment.
Runbooks can also enforce completion gates. If a runbook’s `completion_policy.required_workflow_statuses` includes a target status such as `closed`, the workflow endpoint will reject that transition until all runbook steps are completed; only then does any approval policy apply.
Runbook steps can now be structured instead of flat strings. Step definitions support `required`, `depends_on`, and `parallel_group`, so optional steps no longer block closure, dependency-blocked steps cannot be completed out of order, and operators can still see which steps are safe to run in parallel.
Incidents now also expose a derived execution plan. `runbook_execution_plan` and `GET /incidents/{incident_id}/runbook-plan` surface next runnable steps, blocked steps with human-readable wait reasons, completed steps, and runnable parallel groups for operator guidance.
Runbook steps can now also be assigned or claimed. `POST /incidents/{incident_id}/runbook-assignment` updates per-step `assigned_to`, `claimed_by`, `claim_expires_at`, and supports `heartbeat` to extend a live claim lease. Active claims now reject conflicting claims from another operator until the lease expires, and incident payloads carry both `incident_revision` and per-step `step_revision` so runbook writes can reject stale same-step updates while still retrying independent step updates safely. On the live Supabase path, those step mutations now execute through a row-locking RPC instead of whole-incident JSON PATCHes, so conflict enforcement happens in the database as well as in the API layer. Incident workflow transitions now use the same pattern on the live backend, so `POST /incidents/{incident_id}/workflow` and approval-driven workflow continuation no longer rely on whole-row PATCH semantics there either. Reminder-driven incident maintenance now does too: reassignment and reminder counter updates from the reminder pass use a dedicated atomic reminder mutation on the live backend instead of generic incident patching. Alert-to-incident rollups now follow the same pattern: incident sync from alert lifecycle changes executes through a dedicated merge RPC on the live backend, so reopen/resolve episode logic and alert-id accumulation are no longer driven by a read-then-upsert race there. Alert status and suppression updates now also use an atomic alert-plus-incident mutation on the live backend, so operator status changes, auto-escalation, auto-recovery, and duplicate suppression no longer leave a crash window between the alert row and the incident projection. New alert creation now uses the same model for scheduled evaluation paths: alert rows can be created together with their incident projection in one live transaction instead of being created first and projected second.

# ADR 015: Inngest Event Naming Convention

**Date:** 2026-03-15
**Status:** Accepted
**Context:** Office Dashboard CEO review, Issue 5

## Decision

All Inngest events in the CallLock AgentOS monorepo use the `calllock/` namespace prefix with dot-delimited resource and action segments.

### Format

```
calllock/<resource>.<action>[.<qualifier>]
```

### Examples

| Event Name | Trigger |
|---|---|
| `calllock/agent.state.changed` | Harness node entry (InngestEmitter) |
| `calllock/agent.handoff` | Cross-department context handoff |
| `calllock/agent.dispatch` | Operator dispatches task to idle agent |
| `calllock/policy.gate.pending` | Policy gate blocks, creates quest |
| `calllock/policy.gate.resolved` | Operator resolves quest |
| `calllock/handoff.override` | Admin redirects in-flight handoff |
| `calllock/meeting.requested` | Meeting trigger fires (Phase 2) |
| `calllock/memo.daily.generate` | Midnight cron for daily memo |

### Rules

1. All new events MUST use the `calllock/` prefix.
2. Resource names are singular nouns (`agent`, not `agents`).
3. Actions are past-tense verbs or present-tense descriptors (`changed`, `pending`, `generate`).
4. Existing unprefixed events (`ProcessCallPayload`, `JobDispatchPayload`, etc.) are grandfathered. A backfill to rename them is tracked in TODOS.md as P3.

## Consequences

- New Inngest functions subscribe to `calllock/*` events.
- Event validators in `inngest/src/events/schemas.ts` follow the same naming for payload interfaces.
- The `calllock/` prefix makes events grep-friendly and distinguishable from Inngest system events.

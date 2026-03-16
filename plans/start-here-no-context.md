# Start Here with No Context

Use this document when you are opening the repo cold and need to become productive without reconstructing the whole planning history.

## What This Repo Is

CallLock AgentOS is the monorepo for a multi-tenant agent harness and persuasion platform layered on top of an existing live production stack.

The current production stack outside this repo is:

- Retell AI voice runtime
- Express V2 backend on Render
- Supabase
- Next.js dashboard on Vercel
- Cal.com
- Twilio

This repo contains the shared platform, harness, knowledge assets, industry packs, operator/control-plane foundations, and the persuasion-platform system specification and execution plans.

## What Is Already Live vs. What Is Planned

### Already live in production outside this repo

- voice calls through Retell AI
- backend operations through Express V2
- core database in Supabase
- dashboard frontend
- booking and alerts integrations

### Already present in this repo

- harness runtime foundations in `harness/`
- Inngest event wiring in `inngest/`
- Supabase migrations and seed data in `supabase/`
- knowledge graphs, worker specs, and HVAC pack assets in `knowledge/`
- architecture and persuasion-platform specs
- control-plane, alerting, incident, scheduler, eval, artifact, and improvement foundations

### Still specification-first

- the full persuasion-platform contract lock for all core interfaces
- the canonical founder/operator workflow semantics for `review_object`
- projection skew and staleness semantics
- full federated benchmark privacy mechanics
- the complete whole-system execution program beyond existing phase snapshots

## Read These in This Order

If you only read four things, read these:

1. `plans/start-here-no-context.md`
2. `plans/whole-system-executable-master-plan.md`
3. `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
4. `knowledge/growth-system/design-doc.md`

Then read these if you are working on planning, review, or contract definitions:

5. `knowledge/growth-system/hold-scope-review.md`
6. `TODOS.md`
7. `plans/phases-1-2-foundation-and-core-harness.md`
8. `plans/phases-3-4-operations-and-improvement.md`

## Document Authority

Do not guess this. The repo is intentionally split:

- `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
  Owns shared platform boundaries, runtime split, tenant isolation, deployment posture, and ADR-backed infrastructure constraints.

- `knowledge/growth-system/design-doc.md`
  Owns persuasion-platform contracts and trust-ladder semantics:
  `persuasion_path`, `graph_mutation`, `review_object`, `lineage_chain`, `decisioning_projections`, `operator_projections`, `control_plane_auth`, `federated_benchmark`.

- `plans/whole-system-executable-master-plan.md`
  Owns execution order, stage dependencies, readiness gates, acceptance criteria, and rollout order for the whole system.

- `knowledge/growth-system/hold-scope-review.md`
  Owns the critical findings, gaps, failure modes, and review rationale. It is not the active execution plan.

- Older phase plans in `plans/`
  Supporting detail only. Useful for implementation detail, not authoritative for sequencing.

## Current Program Shape

The canonical program now has 8 stages:

0. Contract Lock
1. Shared Platform Foundation
2. Capture-Only
3. Advisory-Only
4. Assisted + Closed-Loop
5. Cross-Funnel Expansion
6. Federated Benchmarks
7. Wedge Replication

Near-term expectation:

- Stages 1-4 should be executable.
- Stages 5-7 should be contract-locked, gated, and explicit, but not over-specified beyond current evidence.

## Core Contracts You Must Not Redefine

These are the platform contracts that downstream work depends on:

- `persuasion_path`
- `graph_mutation`
- `review_object`
- `lineage_chain`
- `decisioning_projections`
- `operator_projections`
- `control_plane_auth`
- `federated_benchmark`

Before implementing anything that depends on them, check whether the contract is already locked. If not, work belongs in Stage 0 first.

## Current Highest-Priority Gaps

These are the main unresolved items blocking clean execution:

- stable `persuasion_path` identity and versioning
- deterministic `graph_mutation` categories, merge rules, and replay invariants
- `review_object` lifecycle, transitions, apply semantics, and duplicate/supersede behavior
- projection versioning, freshness, stale reads, and skew handling
- `control_plane_auth` role matrix and action permissions
- federated benchmark privacy thresholds and suppression rules

These are already tracked in `TODOS.md` and called out in the HOLD SCOPE review.

## If You Are Starting Work Cold

### First 10 minutes

- Read this file.
- Read the master plan.
- Read the architecture spec and the growth-system spec.
- Confirm whether your task is shared-platform work, persuasion-contract work, or sequencing work.

### First 30 minutes

- Read the relevant section of `knowledge/growth-system/hold-scope-review.md`.
- Check `TODOS.md` for open contract work that overlaps your task.
- Search the repo before making assumptions:
  `rg "review_object|persuasion_path|graph_mutation|lineage_chain|decisioning_projections|operator_projections|control_plane_auth|federated_benchmark"`

### First implementation decision

Ask one question:

"Am I building on an already-locked contract, or am I about to invent semantics that belong in Stage 0?"

If the answer is the second one, stop and update the spec first.

## If You Need to Validate the Repo Quickly

Run:

```bash
node scripts/validate-knowledge.ts
node scripts/validate-worker-specs.ts
node scripts/validate-packs.ts
```

For harness work:

```bash
cd harness
pytest
```

For Inngest typing:

```bash
cd inngest
npm run typecheck
```

## Operational Rules

- Do not create a second source of truth for contracts.
- Do not let phase plans silently override the master plan.
- Do not let UI state replace `review_object` state.
- Do not let logs replace authorization; `control_plane_auth` must stay explicit.
- Do not bypass append-only evidence or deterministic mutation with direct model writes.
- Do not widen scope when a contract lock is the actual blocker.

## Recommended Next Work

If no one has given you a more specific task, the next best planning/contract tasks are:

1. `review_object` lifecycle and apply semantics
2. `graph_mutation` and `lineage_chain` contracts
3. projection versioning and stale-read behavior
4. `control_plane_auth` role matrix
5. federated benchmark privacy thresholds

If no one has given you a planning task and you are doing implementation, only work on items that already have enough contract clarity in the specs.

## One-Sentence Mental Model

This system is a shared agent platform plus a persuasion-memory platform: the architecture spec says what the system is, the growth spec says what the persuasion objects mean, and the master plan says what gets built in what order.

# Unified Implementation Plan: Sales Machine + Inbound Pipeline

**Date:** March 16, 2026
**Status:** Ready for execution
**Baseline:** commit `f74f977` on `rbaset5/ceo-review-todos` (196 tests passing)
**Specs:**
- `2026-03-16-sales-machine-operating-manual-design.md` (v3, merged)
- `2026-03-16-inbound-pipeline-integration-design.md` (v2, reconciled)

## Current State

| Layer | Status | Tests |
|---|---|---|
| Growth Memory foundation (touchpoints, beliefs, experiments, wedge fitness) | Built (commit 22a7920) | 196 passing |
| Growth repository (local + Supabase dual-mode) | Built | Covered |
| Growth event handlers (touchpoint, lifecycle, belief) | Built | Covered |
| Growth engine (wedge fitness, allocator) | Built | Covered |
| Growth infrastructure (DLQ, health gate, idempotency, attribution) | Built | Covered |
| Inngest growth functions (handle-touchpoint, handle-lifecycle, growth-advisor-weekly) | Built | Typechecked |
| ADRs 010-014 | Locked | N/A |
| Migration 045 (metric_events) | Applied | N/A |
| Migration 046 (growth_memory_phase1) | Applied | N/A |
| Sales Machine agents (Prospector through Handoff) | Spec'd, not built | None |
| Inbound pipeline (quarantine through escalation) | Spec'd, not built | None |
| Instantly client | Spec'd, not built | None |

## Implementation Philosophy

### What Codex is for

Deterministic, well-constrained tasks with clear inputs and outputs. Schema migrations, repository CRUD, module porting where source TS and target Python are both known, test suites, type definitions, Inngest function scaffolding.

**How to use it:** Give it a frozen commit baseline, locked authority docs (ADRs, migration, spec section), explicit constraints ("do not reinterpret," "preserve dual-mode repository"), and verification commands to run when done.

### What founder vibe-coding is for

Creative judgment work: LLM prompt design, scoring rubric tuning, template authoring, config value decisions, end-to-end integration testing, "does the email sound right?" evaluation. Also: wiring modules together when the connection requires understanding business context.

**How to use it:** Work in Claude Code interactively. Read the module, think about the business goal, iterate on prompts, test against real data.

### The split rule

> If the task has one correct answer derivable from a spec, give it to Codex.
> If the task requires taste, domain judgment, or iterative refinement, do it yourself with Claude Code.

---

## Phase 1: Schema + Shared Infrastructure

**Goal:** Get the database tables, repository layer, and shared modules in place. Everything else depends on this.

### 1A. Migration 047 (Codex)

**Task:** Write `supabase/migrations/047_inbound_pipeline.sql` with all 7 tables from the inbound spec Section 9-10, 13. Plus `enrichment_cache` extension (add `cache_type` column per reconciliation).

**Authority:** Inbound pipeline spec Sections 9, 10, 13. Sales Machine spec Section 6 for `enrichment_cache` base schema.

**Constraints:**
- Follow migration 046 patterns exactly (RLS enable, force, policy using `current_tenant_id()`)
- `enrichment_cache` schema from Sales Machine is authoritative; add `cache_type` column
- All CHECK constraints, indexes, and UNIQUE constraints per spec
- Do not touch migrations 001-046
- Additive only

**Verification:** `npm run typecheck && npm run build` in inngest (unchanged, but verify no breakage)

**Codex prompt anchor:** _"Read migration 046 for the pattern. Write 047 per spec Sections 9, 10, 13."_

### 1B. Repository layer (Codex)

**Task:** Add inbound repository methods to the dual-mode repository pattern.

**Files to modify:**
- `harness/src/db/repository.py` — add `insert_inbound_message`, `get_inbound_message_by_rfc_id`, `insert_inbound_draft`, `upsert_poll_checkpoint`, `insert_inbound_stage`, `upsert_enrichment_cache`, `insert_prospect_email`, `get_prospect_by_email`, `insert_email_account`, `list_enabled_email_accounts`
- `harness/src/db/local_repository.py` — in-memory implementations
- `harness/src/db/supabase_repository.py` — Supabase implementations

**Authority:** Inbound pipeline spec Section 9 schemas. Existing repository pattern in these files.

**Constraints:**
- Preserve the `using_supabase()` dual-mode pattern exactly
- Dedup behavior: catch unique violation, log dedup_hit, return success (per ADR 011)
- Do not rename or restructure existing repository methods
- Add tests in `harness/tests/` following existing patterns

**Verification:** `python3 -m pytest -q` — all existing 196 tests pass + new tests pass

### 1C. Shared inbound modules — deterministic layers (Codex)

**Task:** Port the deterministic (no-LLM) modules from atlas TS to Python.

**Modules:**
- `harness/src/inbound/__init__.py`
- `harness/src/inbound/types.py` — dataclasses from spec
- `harness/src/inbound/config.py` — YAML loader per spec Section 18
- `harness/src/inbound/quarantine.py` — port from atlas `quarantine.ts` (9 regex patterns per spec Section 17, BeautifulSoup4 for HTML)
- `harness/src/inbound/stage_tracker.py` — port from atlas `stage-tracker.ts` (7-state machine, transition validation)
- `harness/src/inbound/content_gate.py` — port from atlas `content-gate.ts`
- `harness/src/inbound/escalation.py` — port from atlas `escalation.ts`
- `harness/src/inbound/backfill.py` — port from atlas `backfill.ts`

**Source material:** Recover from atlas repo: `git checkout 6f29bc7 -- src/inbound/` in `/Users/rashidbaset/emdash-projects/calllock-atlas`

**Constraints:**
- Python `re` module with `re.IGNORECASE` for all patterns
- BeautifulSoup4 for HTML stripping (not linkedom)
- `hashlib` for SHA-256 (not node:crypto)
- All functions must be importable by the Sales Machine Reply Classifier Agent
- Add tests in `harness/tests/inbound/` — port the 12 atlas test files

**Verification:** `python3 -m pytest -q` — all tests pass

---

## Phase 2: Sales Machine Outbound Swarm

**Goal:** Build the revenue-generating outbound pipeline. This is the highest-value work.

**Dependency:** Phase 1A (migration) and 1B (repository) must be complete.

### 2A. Prospector Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/prospector_agent.py`
- Add `prospects` table to migration 047 (or 048 if 047 is already applied)
- Add repository methods for prospect CRUD
- Add Inngest function `inngest/src/functions/growth/handle-prospecting-batch.ts`
- Add harness endpoint `POST /growth/swarm/prospect`
- Add event schema `ProspectingBatchPayload` and `ProspectSourcedPayload`
- Tests for dedup logic, ICP filtering, batch cap

**Founder vibe-coding portion:**
- Apollo API integration (API key, query parameters, rate limiting)
- ICP filter tuning (which HVAC signals to filter on)
- Contact email "most personal wins" heuristic refinement
- End-to-end test with real Apollo sandbox data

### 2B. Enrichment Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/enrichment_agent.py`
- Add harness endpoint `POST /growth/swarm/enrich`
- Add Inngest function `handle-prospect-sourced.ts`
- Input sanitization module (reuse `inbound/quarantine.py` strip/neutralize functions)
- Output enum validation
- Write to `enrichment_cache` with `cache_type='prospect_enrichment'`
- Tests for sanitization, enum validation, partial enrichment fallback

**Founder vibe-coding portion:**
- LLM prompt for enrichment analysis (trade detection, pain profiling, revenue estimation)
- Revenue estimation tiers from `knowledge/industry-packs/hvac/`
- Website scraping strategy (what to extract, how to handle failures)
- Prompt iteration against real HVAC business websites

### 2C. Segmentation Agent (Codex)

**Fully Codex** — this is rule-based, no LLM.

- Scaffold `harness/src/growth/agents/segmentation_agent.py`
- Implement segment assignment rules per Sales Machine Section 2.5.3
- Initial lifecycle state = REACHED
- Prospect scoring formula
- Add Inngest function and harness endpoint
- Tests for each segment bucket + unclassified fallback

### 2D. Sequence Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/sequence_agent.py`
- 5-touch, 14-day sequence structure per Section 3.1
- Timing rules (Tue-Thu, 7-9am, holiday suppression)
- `step.sleepUntil` scheduling in Inngest function
- Step ID stability (versioned step IDs)
- Write to `journey_assignments`
- Tests for scheduling, step ID stability, experiment arm assignment

**Founder vibe-coding portion:**
- Template family design (what each touch says)
- Angle selection logic (which pain signal maps to which angle)
- Subject line personalization with revenue estimates
- Template slot validation rules

### 2E. Sender Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/sender_agent.py`
- Pre-send sequence status check (paused/cancelled guard)
- Outbound Health Gate integration (reuse `growth/gate/health_gate.py`)
- CAN-SPAM slot validation
- Touchpoint logging
- Tests for health gate blocks, sequence pause race condition

**Founder vibe-coding portion:**
- Instantly client (`harness/src/integrations/instantly.py`) — API integration, warmup awareness, reputation checks
- Domain rotation strategy
- Send cap tuning

### 2F. Reply Classifier Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/reply_classifier_agent.py`
- HMAC webhook verification
- Input sanitization (import from `inbound/quarantine.py`)
- Classification category enum
- Belief signal mapping table (Section 2.6)
- Idempotency on reply message ID
- Eval runner against `reply-classifier-eval-fixtures.yaml`
- Tests for each category, low-confidence routing, dedup

**Founder vibe-coding portion:**
- LLM classification prompt (the core of this agent)
- Prompt iteration against the 45+5 eval fixtures until accuracy targets are met
- Edge case tuning (the "is this an objection or a question?" judgment calls)

### 2G. Handoff Agent (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/growth/agents/handoff_agent.py`
- Routing rules per Section 2.5.7
- Lifecycle state transitions with CAS
- Sequence replay assembly from touchpoint_log
- Suppress list management
- Handoff packet generation
- Tests for each routing path, CAS conflict, doctrine unavailable failsafe

**Founder vibe-coding portion:**
- Handoff notification format (what the founder actually sees)
- Doctrine registry initial entries
- Auto-reply template for questions with proof assets
- PII deletion workflow

### 2H. Supporting crons (Codex)

**Fully Codex:**
- Sequence Health Monitor (daily cron, Section 2.7)
- Cost Aggregation Job (daily cron, Section 1.3)
- Inngest functions + harness endpoints for both
- Tests

---

## Phase 3: Inbound Pipeline

**Goal:** Add organic inbound lead capture. Depends on Phase 1 (schema, shared modules) and benefits from Phase 2 (Growth Memory is populated, reply infrastructure exists).

### 3A. LLM-dependent modules (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/inbound/scorer.py` — port structure from atlas `scorer.ts`
- Scaffold `harness/src/inbound/drafter.py` — port structure from atlas `drafter.ts`
- Scaffold `harness/src/inbound/researcher.py` — port from atlas `researcher.ts` with SSRF protection
- Response parsing, rubric hashing, template selection logic
- Tests for JSON parsing, rubric hash, SSRF blocks, template selection

**Founder vibe-coding portion:**
- Scoring rubric (`knowledge/inbound/rubric.md`) — what makes an inbound lead exceptional vs spam?
- Draft templates (`knowledge/inbound/templates/`) — what do reply drafts actually say?
- LLM prompt design for scorer and drafter
- Iteration against real inbound emails

### 3B. IMAP client + pipeline orchestrator (Codex)

**Fully Codex:**
- `harness/src/inbound/imap_client.py` — connect, fetch, checkpoint (using `imapclient`)
- `harness/src/inbound/pipeline.py` — `process_message()` orchestrator, `run_poll()`
- `harness/src/inbound/repository.py` — thin wrapper calling repository methods from 1B
- Per-message checkpoint update
- Promotion flow (create prospect, write touchpoint, emit event)
- Tests for dedup, checkpoint, promotion, quarantine-blocked flow

### 3C. Inngest wiring (Codex)

**Fully Codex:**
- Add event schemas to `inngest/src/events/schemas.ts` (5 inbound events per spec Section 4 + Section 12)
- Add `inngest/src/functions/inbound/fan-out-poll.ts`
- Add `inngest/src/functions/inbound/poll-inbound.ts`
- Add `inngest/src/functions/inbound/process-message.ts`
- Add `inngest/src/functions/inbound/retry-scoring.ts`
- Add harness endpoints: `/inbound/tenants`, `/inbound/poll`, `/inbound/process`, `/inbound/retry-scoring`
- Register in `inngest/src/index.ts`
- Typecheck + build verification

### 3D. Instantly client (Codex + Founder)

**Codex portion:**
- Scaffold `harness/src/integrations/instantly.py` per spec Section 5
- Rate limiter, dedup window, warmup threshold check
- Tests for guardrails (refuse when warmup low, dedup window, rate limit)

**Founder vibe-coding portion:**
- Instantly API key setup and sandbox testing
- Warmup threshold values
- Bounce/complaint rate thresholds

### 3E. End-to-end integration (Founder)

**Fully founder vibe-coding:**
- Wire IMAP credentials for a test mailbox
- Send test emails, verify they flow through the pipeline
- Tune scoring rubric against real messages
- Tune draft templates
- Verify promotion creates correct Growth Memory entries
- Verify observability (counters, alerts)

---

## Phase 4: Dashboard + Observability

**Goal:** Make the system visible to the founder.

### 4A. Founder Dashboard v0 (Founder vibe-coding)

- System narrative
- Momentum score
- Rolling CAC
- Active sequences
- Handoff queue
- Inbound lead pipeline

### 4B. Alerting (Codex)

- P1 performance alerts per Sales Machine Section 8.1
- Inbound alerts per inbound spec Section 16
- Wire into existing alerting infrastructure

---

## Execution Order

```
Phase 1A ──→ Phase 1B ──→ Phase 1C
  (migration)  (repository)  (shared modules)
                  │
                  ├──→ Phase 2A-2H (Sales Machine agents, can parallelize some)
                  │      │
                  │      └──→ Phase 4B (alerting)
                  │
                  └──→ Phase 3A-3C (Inbound pipeline)
                         │
                         └──→ Phase 3D (Instantly)
                                │
                                └──→ Phase 3E (E2E integration)
                                       │
                                       └──→ Phase 4A (Dashboard)
```

**Critical path:** 1A → 1B → 2A → 2B → 2C → 2D → 2E → 2F → 2G (outbound swarm working end-to-end)

**Parallel track:** 1C → 3A → 3B → 3C (inbound pipeline, can run alongside outbound agents)

---

## Codex Prompt Template

For each Codex task, use this template:

```text
Implement from the current repo state at commit {COMMIT_SHA} on branch {BRANCH}.

Treat the following as fixed authority and do not reinterpret:
- {list locked ADRs and specs}

What is already implemented and must be preserved:
- {list existing patterns from the codebase}

Your task:
- {specific deliverable}

Constraints:
- {list of "do not" rules}
- Keep all existing tests passing and add tests alongside new behavior.
- Prefer additive changes.
- Do not rename or renumber ADRs/migrations.
- Do not replace the dual local/Supabase repository pattern.

When finished:
- Run: python3 -m pytest -q (all tests must pass)
- Run: cd inngest && npm run typecheck && npm run build (if TS changed)
- Summarize exactly what changed.
```

---

## Founder Vibe-Coding Sessions

For each founder session, the pattern is:

1. **Read** the Codex output (the scaffolded module)
2. **Decide** the creative parts (LLM prompts, templates, config values)
3. **Iterate** with Claude Code until it feels right
4. **Test** against real data or eval fixtures
5. **Commit** when satisfied

The founder sessions are where domain knowledge meets code. Nobody else can decide what a good HVAC cold email sounds like or what makes an inbound lead "exceptional."

---

## Summary: Task Count

| Phase | Codex tasks | Founder sessions | Estimated Codex prompts |
|---|---|---|---|
| 1. Schema + Infrastructure | 3 | 0 | 3 |
| 2. Sales Machine Agents | 7 Codex portions + 2 full Codex | 6 | 9 |
| 3. Inbound Pipeline | 3 Codex portions + 1 full Codex | 2 | 4 |
| 4. Dashboard + Observability | 1 | 1 | 1 |
| **Total** | | | **17 Codex prompts, 9 founder sessions** |

The Codex tasks can be parallelized where dependencies allow. The founder sessions are sequential (each builds on domain learning from the previous one).

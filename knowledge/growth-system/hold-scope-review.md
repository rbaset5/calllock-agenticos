---
id: growth-system-hold-scope-review
title: HOLD SCOPE Review - Historical Narrowed Persuasion Graph Phase
graph: growth-system
owner: founder
last_reviewed: 2026-03-14
trust_level: curated
progressive_disclosure:
  summary_tokens: 700
  full_tokens: 18000
status: Review - HOLD SCOPE
---

# HOLD SCOPE Review - Historical Narrowed Persuasion Graph Phase

**Reviewed artifact at review time:** the narrowed persuasion-graph rewrite of `knowledge/growth-system/design-doc.md` that immediately preceded the ambitious authority restore on 2026-03-14  
**Reference artifacts:** `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`, `plans/phases-1-2-foundation-and-core-harness.md`, `plans/phases-3-4-operations-and-improvement.md`, `TODOS.md`, `docs/decisions/002-005,008-009`

**Historical note:** this document is preserved as rationale for the narrowed phase, not as the current growth-system authority. The current authority lives in `knowledge/growth-system/design-doc.md`. The still-binding findings from this review are the need for an explicit authority seam, durable founder-review workflow semantics, deterministic write and lineage behavior, control-plane rigor, and privacy-safe aggregate benchmarking.

## Verdict

**Overall verdict at the time of review:** the growth-system spec was directionally right and ambitious enough. It should stay in `HOLD SCOPE`. The failure mode was not underscoping. The failure mode was leaving the core persuasion contracts half-specified while adjacent docs kept evolving independently.

**How to read this now:** treat this as a record of the contract-hardening pass that happened before the ambitious restore. Use it to preserve rigor, not to argue that the main growth doc should stay narrowed.

**Top-tier issues to fix before implementation planning:**

1. **CRITICAL GAP:** the authority seam between the growth spec, architecture spec, and phase plans was implicit.
2. **CRITICAL GAP:** `review_object` is defined as a first-class state machine, but current repo decisions still treat approvals mostly as audit events rather than a durable workflow object.
3. **CRITICAL GAP:** the phase plans do not yet assign concrete implementation ownership for `event_spine`, `graph_mutation`, `persuasion_path`, or projection refresh/versioning.
4. **CRITICAL GAP:** `control_plane_auth` remains conceptually correct but operationally underdefined for cross-tenant reads, writes, overrides, and replay.
5. **WARNING:** Phases 5-7 are binding in direction, but their privacy, cohorting, and benchmarking mechanics are not yet implementation-grade.

## System Audit

### Current system state

- The repo is not greenfield. The production shape in the architecture spec is still the anchor: Retell AI voice runtime, Express V2 backend, Supabase, Next.js dashboard, Cal.com, Twilio.
- The repository already contains substantial backend foundations for jobs, alerts, artifacts, audit logging, tenant onboarding, verification, retention, scheduler claims, incidents, and control-plane operations.
- The growth-system spec was recently rewritten heavily. `git diff --stat HEAD~1..HEAD` shows a large rewrite isolated to `knowledge/growth-system/design-doc.md`, which is a strong signal that this topic is in active review/refinement rather than stable execution mode.

### What is already in flight

- Current branch: `codex/phase34`
- `git diff main --stat` shows a large architectural and implementation surface already landed or in progress across `knowledge/`, `harness/`, `inngest/`, `supabase/`, `plans/`, and `docs/decisions/`.
- `git stash list` is empty.
- No tracked-source `TODO` / `FIXME` / `HACK` / `XXX` comments were found under `harness/`, `inngest/`, `scripts/`, `knowledge/`, or `supabase/` after excluding vendored dependencies.

### Retrospective check

Recent commit history shows repeated review-driven refinement:

- `46251fc` Address architecture spec review findings
- `66035bc` Address eng review findings: implementation phasing, harness deployment, tenant isolation
- `9aa9b33` Add retrieval engine evaluation, database-backed compliance consideration, and multimodal embedding rider
- `f67f3f1` Implement Phase 1-2 foundation and deployment path
- `46daa30` Review latest change list
- `482003e` Document recent request updates

Recurring problem areas are clear:

- architectural boundary definition
- resilience and partial-failure handling
- tenant isolation and control-plane safety
- implementation phasing versus platform ambition

That history justifies a stricter standard for any new contract that crosses product core, harness, and operator surfaces.

## Step 0

### 0A. Premise challenge

**Right problem:** yes, if the problem is "build trustworthy persuasion memory and governed decisioning." No, if the problem drifts toward "build a second product core for GTM automation."

**Actual business outcome:** the real outcome is finding and repeating the shortest believable path from first signal to booked pilot, then extending that path through onboarding, retention, and referral. The design doc is mostly on that outcome, not a proxy.

**What if we did nothing:** CallLock could still ship wedge tactics manually, but it would not accumulate durable persuasion memory, replayable evidence, or a founder-grade approval surface. That would cap learning velocity and explainability.

### 0B. Existing code leverage

| Sub-problem | Existing repo leverage | Reuse status |
|---|---|---|
| Event validation | ADR 004 + current FastAPI event contracts | Partial reuse |
| Tenant isolation | RLS migrations, tenant-scoped config, ADR-backed rules | Strong reuse |
| Audit trail | ADR 005 + `audit_logs` + artifact/audit modules | Strong reuse |
| Alerts and kill switches | alerting, suppression, escalation, control-plane modules | Strong reuse |
| Retry and degraded persistence | ADR 002 + recovery journal + replay path | Strong reuse |
| Privacy redaction | ADR 003 + trace redactor | Partial reuse |
| Approval workflow | audit log coverage only | Gap |
| Persuasion-path memory | none | Gap |
| Projection refresh/versioning | local patterns exist, persuasion-specific contract absent | Gap |
| Federated benchmarks | privacy principles only | Gap |

### 0C. Dream state mapping

```text
CURRENT STATE                     THIS PLAN                        12-MONTH IDEAL
-----------------------------    -----------------------------    -----------------------------
Live product core plus harness   Persuasion graph platform        One trusted persuasion memory
foundations, but no canonical    layered over product core and    and operator control plane
persuasion memory or founder     harness with event spine,        spanning acquisition, sales,
review object.                   deterministic graph,              onboarding, retention, and
                                 projections, review objects,     referral, with replayable
                                 and trust-ladder rollout.        evidence and safe automation.
```

### 0D. HOLD SCOPE analysis

The scope is already large. The minimum set of changes that achieves the stated goal is not "cut features," but "lock the contracts that everything else depends on."

Do not add new subsystems. Do not reduce the seven-phase shape. Force the following contracts into an implementation-safe state:

- stable `persuasion_path` identity and versioning
- deterministic `graph_mutation` categories and merge rules
- `review_object` transitions, idempotency, and apply semantics
- projection versioning, freshness, and stale-read behavior
- `control_plane_auth` role matrix and audit requirements
- benchmark privacy threshold and cohort safety rules

### 0E. Temporal interrogation

**Hour 1 (foundations):** implementers need to know which document owns persuasion contracts and how those contracts version.

**Hour 2-3 (core logic):** they will hit ambiguity on path merge rules, review-object transitions, approval idempotency, and projection freshness.

**Hour 4-5 (integration):** they will hit cross-doc seams around control-plane auth, audit logging, and whether existing Cockpit approval flows are sufficient.

**Hour 6+ (polish/tests):** they will wish the plan had already specified deterministic replay inputs, stale snapshot behavior, and rollback order when event capture stays live but graph promotion is frozen.

## Section 1: Architecture Review

### Architecture finding summary

1. **CRITICAL GAP:** document authority was implicit. This review treats the growth spec as authoritative for persuasion contracts and the architecture spec as authoritative for shared platform boundaries.
2. **CRITICAL GAP:** the current phase plans do not allocate implementation ownership for `event_spine`, `graph_mutation`, `persuasion_path`, or persuasion-specific projections.
3. **WARNING:** `review_object` creates a hard dependency among governance intelligence, operator control plane, audit logging, and downstream effect application, but the transaction boundaries are not yet specified.
4. **WARNING:** Phases 5-7 rely on benchmark privacy and cross-funnel evidence rules that are still principle-level rather than contract-level.
5. **OK:** the platform layering itself is coherent. The growth doc does not try to replace the product core or harness.

### Full system architecture

```text
                    +-----------------------------------------+
                    |           SHARED PLATFORM               |
                    | product core + harness + ADR constraints|
                    +-------------------+---------------------+
                                        |
                                        v
               +------------------------------------------------------+
               |        PERSUASION GRAPH PLATFORM (this spec)          |
               | event_spine -> graph_mutation -> canonical graph      |
               |        -> decisioning/operator projections            |
               +----------------------+-------------------------------+
                                      | 
                    +-----------------+------------------+
                    |                                    |
                    v                                    v
        bounded decisioning surfaces         operator control plane
        (routing, proof, sequencing)         (packet, queue, review)
                    |                                    |
                    +-----------------+------------------+
                                      |
                                      v
                        downstream effects + founder actions
                                      |
                                      v
                                 event_spine append
```

### Dependency graph before and after

```text
BEFORE
product core -----> harness -----> Cockpit/audit/alerts

AFTER
product core -----> harness ------------------------------+
      |                                                   |
      +-----> persuasion graph platform ------------------+
                              |                           |
                              +--> decisioning surfaces   |
                              +--> operator projections   |
                              +--> review_object apply ---+
```

### Single points of failure

- event schema validation and append path
- deterministic mutation planner/apply path
- doctrine registry availability
- projection refresh pipeline
- review apply transaction boundary
- control-plane auth resolver

### Rollback posture

The growth doc has the right rollback principle:

- freeze closed-loop actioning first
- freeze graph promotion separately if needed
- keep event capture live
- keep last-good projections readable
- repair or replay from append-only evidence

What is still missing is the exact sequence for partially applied `review_object` actions when downstream side effects have started but projection refresh has not completed.

## Section 2: Error & Rescue Map

### Error & Rescue Registry

| Method / codepath | What can go wrong | Exception class | Rescued? | Rescue action | User sees |
|---|---|---|---|---|---|
| `EventSpineIngest.validate` | malformed event | `EventSchemaValidationError` | Y | reject + quarantine + audit | event not accepted |
| `EventSpineIngest.append` | append write fails | `EventAppendWriteError` | **N - GAP** | should fail closed, retry boundedly, and surface backlog state | silent ingest gap today |
| `EventSpineIngest.append` | duplicate or late event | `IdempotencyConflictError` | Y | merge/no-op by idempotency key | nothing if harmless |
| `GraphMutationPlanner.plan` | missing path key fields | `MissingPathKeyError` | Y | hold mutation, open repair/review object | path not promoted |
| `GraphMutationPlanner.plan` | malformed model annotation | `BeliefInferenceParseError` | Y | store analysis-only note, block canonical write | recommendation omitted |
| `GraphMutationApplier.apply` | conflicting merge target | `PathMergeConflictError` | Y | do not apply, open conflict review | visible conflict queue |
| `GraphMutationApplier.apply` | non-deterministic replay mismatch | `ReplayDeterminismMismatchError` | **N - GAP** | should halt promotion and page operator | trust break, currently underspecified |
| `ProjectionRefresher.refreshDecisioning` | refresh fails | `ProjectionRefreshError` | Y | keep last good, mark stale, alert | stale decisioning state |
| `ProjectionRefresher.refreshOperator` | only one projection family refreshes | `ProjectionVersionSkewError` | **N - GAP** | should pin old snapshot for both families or mark both stale | packet/queue divergence risk |
| `ReviewObjectService.create` | duplicate active review for subject/version | `ActiveReviewConflictError` | **N - GAP** | should dedupe or supersede atomically | duplicate queue items |
| `ReviewObjectService.apply` | stale snapshot | `ReviewSnapshotStaleError` | Y | reject, refresh, preserve reviewable state | action rejected cleanly |
| `ReviewObjectService.apply` | downstream side effect fails | `ReviewApplyFailedError` | Y | mark `failed_apply`, preserve intent, retry/replay path | explicit failure state |
| `ControlPlaneAuth.authorize` | actor lacks cross-tenant grant | `ControlPlaneAuthorizationError` | Y | fail closed + audit | not authorized |
| `DoctrineEvaluator.evaluate` | registry unavailable | `DoctrineRegistryUnavailable` | Y | fail closed, queue risky actions | blocked pending doctrine |
| `BenchmarkAggregator.publish` | cohort below privacy threshold | `UnsafeBenchmarkCohortError` | Y | block output, log reason | benchmark unavailable |

### Error flow

```text
raw event
  -> validate
     -> invalid -> quarantine_event + audit
     -> valid -> append
        -> append failure -> retry -> recovery hold -> operator visibility
        -> append success -> plan mutation
           -> mutation conflict -> hold + review queue
           -> mutation apply success -> refresh projections
              -> refresh skew/failure -> mark stale + freeze dependent reads
              -> refresh success -> decisioning/operator surfaces update
```

**CRITICAL GAPS from this registry:**

- append-write failure path is not named end-to-end
- replay determinism mismatch does not yet have an explicit halt procedure
- projection version skew is not specified
- duplicate active review creation is not specified

## Section 3: Security & Threat Model

| Threat | Likelihood | Impact | Current mitigation | Review verdict |
|---|---|---|---|---|
| Cross-tenant review access through control plane | Med | High | tenant isolation rules + audit logging | **WARNING:** role matrix still missing |
| Prompt injection from transcripts into proof recommendations | High | High | deterministic write boundary blocks direct graph mutation | **WARNING:** recommendation sanitation path still needs explicit rules |
| Undersized benchmark cohort leaks tenant identity | Low | High | aggregate-only principle + privacy thresholds promised | **WARNING:** thresholds not yet defined |
| Replay/admin misuse without reason-bound authorization | Med | High | audit log exists | **CRITICAL GAP:** audit is not authorization |
| Stale approval or TOCTOU on review apply | Med | Med | stale snapshot rejection exists conceptually | **WARNING:** concurrency semantics incomplete |
| Raw transcript over-retention in persuasion memory | Med | Med | data classification and redaction ADR exist | **OK**, if raw content never becomes canonical graph state |
| IDOR against `review_object` or `persuasion_path` identifiers | Med | High | no concrete API contract yet | **WARNING:** auth scope must be locked before API build |

Security conclusion: the design direction is sound, but `control_plane_auth` must move from principle to role/action matrix before any cross-tenant operator surface ships.

## Section 4: Data Flow & Interaction Edge Cases

### Data flow with shadow paths

```text
INPUT EVENT
  -> VALIDATION
  -> NORMALIZATION
  -> APPEND TO EVENT SPINE
  -> PLAN GRAPH MUTATION
  -> APPLY GRAPH MUTATION
  -> REFRESH PROJECTIONS
  -> SURFACE TO DECISIONING / OPERATOR

shadow paths:
  nil input        -> reject + quarantine
  empty input      -> accept raw event, no promotion
  wrong type       -> reject + quarantine
  upstream error   -> retry or hold, never silent
  duplicate event  -> idempotent merge/no-op
  stale projection -> last-good snapshot or both stale
```

### Interaction edge cases

| Interaction | Edge case | Handled? | Expected handling |
|---|---|---|---|
| Review approval | double-click apply | Partial | idempotency key + compare-and-set on subject/version |
| Review approval | stale snapshot | Yes, conceptually | reject and refresh |
| Review approval | navigate away mid-apply | Partial | resumable apply status + failed/applying visibility |
| Packet view | projection stale | Partial | render last-good snapshot with stale marker |
| Queue view | duplicate review objects | No | active-review uniqueness + supersede semantics |
| Decisioning | doctrine unavailable | Yes, conceptually | fail closed |
| Replay | replay while live ingest continues | Partial | bounded replay window + promotion freeze |
| Benchmark view | cohort drops below minimum after filter | No | suppress output, explain reason |
| Closed-loop actioning | back button or retry while in-flight | No | dedupe token + action status |
| Cross-funnel path merge | referral skips early steps | Partial | inherited trust must be explicit in path context |

## Section 5: Quality Review

### Quality findings

1. **CRITICAL GAP:** the public interface section names the right objects but still leaves implementers to invent versioning rules for `persuasion_path`, mutation keys, and projection snapshots.
2. **WARNING:** the `review_object` state machine lists states but not legal transitions, terminal states, or compare-and-set semantics.
3. **WARNING:** "all phases binding" is acceptable only if later phases are compatibility commitments, not hidden implementation requirements for Phase 1-4.
4. **OK:** the doc is explicit about deterministic writes, append-only evidence, materialized projections, and aggregate-only future learning.

## Section 6: Test Review

### Test diagram

```text
NEW UX FLOWS
  founder packet
  review queue
  doctrine conflict queue
  proof debt queue

NEW DATA FLOWS
  raw event -> event spine -> mutation -> path -> projection
  review object -> apply -> downstream effect -> event spine
  benchmark aggregation -> privacy filter -> operator view

NEW CODEPATHS
  idempotent event ingest
  deterministic mutation planning
  mutation conflict hold
  stale snapshot rejection
  projection stale fallback
  benchmark suppression

NEW BACKGROUND / ASYNC
  projection refresh
  replay/recompute
  benchmark aggregation

NEW ERROR / RESCUE PATHS
  quarantine
  mutation hold
  blocked_pending_doctrine
  failed_apply
  stale_projection
```

### Required tests

| Area | Test type | Must prove |
|---|---|---|
| Event ingest idempotency | Integration | duplicate and late events do not fork path state |
| Mutation determinism | Replay / integration | same event set yields same path versions |
| Review apply concurrency | Integration | stale snapshot and double-submit do not double-apply |
| Projection fallback | Integration | last-good snapshot remains coherent when refresh fails |
| Operator consistency | System | packet, queue, and dashboard show same review state |
| Doctrine outage | Integration | risky actions fail closed without silent execution |
| Benchmark privacy | Integration | undersized cohorts never publish |
| Rollback drill | System | closed-loop can freeze while ingest remains live |

### Test gaps

- No persuasion-specific eval suite mapping exists yet.
- No explicit chaos/replay suite is assigned to the persuasion platform contracts.
- No contract test currently ties audit logs, review objects, and downstream effects together.

## Section 7: Performance Review

Top risk areas:

1. replay and recompute fanout across long event windows
2. projection refresh fanout across operator and decisioning surfaces
3. cross-funnel path merge logic under high-cardinality evidence
4. benchmark aggregation over low-signal cohorts

Required posture:

- treat `event_spine` append and `graph_mutation` apply as index-first design problems
- keep decisioning and operator reads on materialized projections only
- avoid synchronous cross-funnel graph joins on request paths
- define freshness budgets so stale-but-coherent reads are acceptable while recompute runs

## Section 8: Observability & Debuggability Review

### Required day-1 signals

- ingest accepted / quarantined / duplicate counters
- mutation applied / held / conflict counters
- replay determinism mismatch counter
- projection refresh latency and stale-age gauges
- review-object counts by state
- review apply success / stale / failed_apply counters
- doctrine blocked action count
- benchmark suppressed-for-privacy count

### Required dashboards

- trust-ladder readiness dashboard
- event-spine health and quarantine volume
- projection freshness and skew
- review queue health and apply failure trend
- benchmark privacy suppression trend

### Runbook requirements

- event backlog / append failure
- mutation hold explosion
- stale projection recovery
- failed review apply replay
- doctrine registry outage
- benchmark privacy block explanation

## Section 9: Deployment & Rollout Review

### Deployment sequence

```text
1. ship event_spine append + validation
2. ship deterministic mutation planner/apply
3. ship projection refresh + stale markers
4. ship operator read surfaces
5. ship review_object persistence + apply path
6. enable advisory-only
7. enable assisted only after replay and stale-snapshot tests pass
8. enable closed-loop last, behind feature flags
```

### Rollback flowchart

```text
incident
  -> freeze closed-loop actions
  -> if corruption risk: freeze graph promotion
  -> keep event ingest live
  -> keep last-good projections readable
  -> inspect review apply failures / mutation holds
  -> replay from event spine if needed
  -> restore advisory
  -> restore assisted
  -> restore closed-loop last
```

### Rollout verdict

- **OK:** trust ladder is the right rollout shape.
- **WARNING:** advisory-only depends on projection coherence, not just projection existence.
- **WARNING:** assisted mode depends on `review_object` and stale snapshot semantics being real, not conceptual.
- **WARNING:** closed-loop must be feature-flagged independently from capture and advisory.

## Section 10: Long-Term Trajectory Review

### Debt and reversibility

- **Reversibility:** `3/5`
- The event-spine and deterministic graph approach is a good long-term foundation.
- The most dangerous debt would be shipping approvals and operator actions without a first-class `review_object` store and then retrofitting it later.
- The second danger is allowing later benchmark/privacy semantics to leak backward into early path identity and projection design.

### One-year question

A new engineer in 12 months should be able to read the growth spec and answer:

- what is the canonical persuasion object?
- where does evidence live?
- who can mutate canonical state?
- how do founder decisions flow?
- what happens when projections are stale?
- what is safe to automate and when?

Today the doc is close, but not fully there because versioning, transitions, and auth are still underspecified.

## What Already Exists

- append-only and typed event discipline in harness event contracts
- tenant isolation rules and RLS posture
- audit logging for operator actions
- alerting, suppression, and escalation primitives
- artifact persistence and lineage concepts
- replay/degraded persistence patterns
- control-plane concepts, onboarding, and kill switches
- privacy redaction and data classification posture

These should be reused rather than replaced.

## NOT in Scope

- building a new tenant-facing UI in this review pass
- defining new GTM modules outside the persuasion graph contract
- replacing the shared product core or the existing harness runtime
- enabling raw cross-tenant memory sharing
- broad channel-mix optimization beyond what the canonical persuasion graph requires
- implementation of benchmark-heavy executive analytics before privacy thresholds are locked

## Dream State Delta

The growth spec is pointed at the right 12-month system, but the delta is still contract safety:

- from "conceptually right objects" to "objects with locked identity, versioning, and transitions"
- from "approval/audit concepts exist" to "`review_object` is the canonical founder workflow primitive"
- from "projection exists" to "projection freshness, skew, and stale-read behavior are explicit"
- from "aggregate-only future learning" to "privacy thresholds are testable and enforced"

## Stale Diagram Audit

Files touched by this review:

- `knowledge/growth-system/design-doc.md`
- `knowledge/growth-system/hold-scope-review.md`
- `knowledge/growth-system/_moc.md`

ASCII diagrams in `knowledge/growth-system/design-doc.md`:

- System boundary diagram: still accurate after adding document-authority language.
- Event spine / graph / projection architecture diagram: still accurate.
- Review object apply flow: directionally accurate, but still incomplete without legal transition rules.
- Rollback flow: still accurate.
- Projection refresh flow: directionally accurate, but incomplete on projection skew behavior.

ASCII diagrams in `knowledge/growth-system/hold-scope-review.md`:

- Full system architecture: accurate for authority and dependency boundaries.
- Dependency graph before/after: accurate at review level.
- Error flow: accurate as the target failure-handling contract.
- Data flow with shadow paths: accurate as the required model.
- Deployment sequence: accurate as rollout order.
- Rollback flowchart: accurate as operational target behavior.

`knowledge/growth-system/_moc.md` contains no ASCII diagrams.

## Unresolved Decisions

These decisions remain open after the review and should be locked before implementation planning for persuasion-specific platform work:

1. the exact stable key and versioning rules for `persuasion_path`
2. deterministic `graph_mutation` categories and merge precedence
3. full `review_object` transition table, terminal states, and dedupe semantics
4. projection version pinning, freshness budgets, and skew handling
5. `control_plane_auth` role matrix for cross-tenant reads, writes, overrides, replay, and benchmark access
6. minimum cohort and slice thresholds for `federated_benchmark`
7. where persuasion-platform primitives land in the phase plans as implementation work items

## Completion Summary

```text
+====================================================================+
|            MEGA PLAN REVIEW - COMPLETION SUMMARY                   |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | Large in-flight surface; review-driven      |
|                      | history; no tracked-source TODO markers     |
| Step 0               | Problem confirmed; authority seam fixed;    |
|                      | core contract locks identified              |
| Section 1  (Arch)    | 5 issues found                              |
| Section 2  (Errors)  | 15 error paths mapped, 4 GAPS               |
| Section 3  (Security)| 7 issues found, 3 High severity             |
| Section 4  (Data/UX) | 10 edge cases mapped, 5 unhandled           |
| Section 5  (Quality) | 4 issues found                              |
| Section 6  (Tests)   | Diagram produced, 3 gaps                    |
| Section 7  (Perf)    | 4 issues found                              |
| Section 8  (Observ)  | 6 gaps found                                |
| Section 9  (Deploy)  | 4 risks flagged                             |
| Section 10 (Future)  | Reversibility: 3/5, debt items: 4           |
+--------------------------------------------------------------------+
| NOT in scope         | written (6 items)                           |
| What already exists  | written                                     |
| Dream state delta    | written                                     |
| Error/rescue registry| 15 methods, 4 CRITICAL GAPS                |
| Failure modes        | 10 total, 4 CRITICAL GAPS                  |
| TODOS.md updates     | not applied in this pass                    |
| Delight opportunities| n/a                                         |
| Diagrams produced    | 6 (arch, dep, error, data, deploy, rollback)|
| Stale diagrams found | 2 partial-completeness warnings             |
| Unresolved decisions | 7 (listed above)                            |
+====================================================================+
```

## Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees? | Logged? |
|---|---|---|---|---|---|
| event ingest | malformed payload | Y | Planned | explicit rejection | Y |
| event ingest | append write failure | **N** | No | **Silent today** | Partial |
| event ingest | duplicate / late event | Y | Planned | nothing if harmless | Y |
| mutation apply | missing path key | Y | Planned | held path | Y |
| mutation apply | merge conflict | Y | Planned | conflict queue | Y |
| replay | determinism mismatch | **N** | No | **Silent trust break risk** | Partial |
| projection refresh | operator stale only | **N** | No | stale / divergent packet | Partial |
| review create | duplicate active review | **N** | No | duplicate queue entries | Partial |
| review apply | stale snapshot | Y | Planned | explicit rejection | Y |
| doctrine eval | registry unavailable | Y | Planned | blocked action | Y |

Rows with `Rescued = N` and no test coverage are release blockers for the persuasion platform.

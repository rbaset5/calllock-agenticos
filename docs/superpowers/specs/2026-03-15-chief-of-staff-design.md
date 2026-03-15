# Chief of Staff Agent — Design Spec

**Date:** 2026-03-15
**Status:** Draft
**Owner:** Founder

## Context

CallLock AgentOS has a rich knowledge graph, structured worker specs, a growth system design, and a LangGraph harness — but no layer that looks at the whole business holistically and helps the founder coordinate parallel agent workstreams. Today the founder manually decides what to work on, manually opens Conductor workspaces, and manually tracks progress. As the number of active workstreams grows, this becomes the bottleneck.

The Chief of Staff is a **founder advisory + execution coordination agent** that reads the full business state, recommends priorities grounded in data, and dispatches approved work to parallel agents.

## Architecture Decision

**Chosen approach:** Hybrid — structured business state in the knowledge graph + Conductor skill for execution.

**Rejected alternatives:**
- *Harness-only:* The harness is a deployed call-processing runtime. Mixing business strategy concerns with tenant-scoped call pipelines creates the wrong abstraction.
- *Conductor-only (flat state):* A single state file gets stale and doesn't track trends. No structured priority or workstream management.
- *Full harness integration with Inngest cron:* Premature — the harness has one worker wired up. Adding a meta-orchestrator before basic workers work adds complexity without value.

## Bootstrap / First Run

On first invocation, if `knowledge/chief-of-staff/` does not exist, the skill:
1. Creates the directory and all seed YAML files with empty/zero values
2. Creates `_moc.md` with standard frontmatter (`graph: chief-of-staff`, `trust_level: provisional`, `owner: founder`)
3. Updates the root `knowledge/_moc.md` to include a link to `[[chief-of-staff/_moc]]`
4. Seeds `priorities.yaml` by reading `knowledge/company/goals-2026.md` and creating one priority entry per goal

This means the very first `/chief-of-staff` invocation bootstraps itself.

## Component 1: Business State Layer

### Location
`knowledge/chief-of-staff/` — follows existing knowledge graph conventions.

### Files

#### `_moc.md`
Map of contents linking all Chief of Staff knowledge nodes. Standard frontmatter with `graph: chief-of-staff`.

#### `priorities.yaml`
Current ranked business priorities with health signals.

```yaml
schema_version: "1.0"
priorities:
  - id: pri-001
    title: "Extract HVAC logic into reusable industry pack"
    goal_ref: "[[company/goals-2026]]"
    status: in_progress    # not_started | in_progress | blocked | done | abandoned
    health: green          # green | yellow | red
    last_updated: 2026-03-15
    notes: "Pack structure done, extraction script working"
    workstreams: []
```

**Cadence:** Updated weekly or when priorities shift.

#### `workstreams.yaml`
Active parallel work being tracked.

```yaml
schema_version: "1.0"
workstreams:
  - id: ws-001
    title: "Wire up remaining 4 worker specs"
    priority_ref: pri-002
    status: not_started    # not_started | in_progress | blocked | done | abandoned
    assigned_to: null      # Conductor workspace name when dispatched
    created: 2026-03-15
    outcome: null           # filled on completion by debrief mode
```

**Cadence:** Updated each session by dispatch and debrief modes.

#### `decisions.yaml`
Append-only log of founder decisions (overrides = training signal per design philosophy).

```yaml
schema_version: "1.0"
decisions:
  - id: dec-001
    date: 2026-03-15
    decision: "Chose hybrid architecture for Chief of Staff"
    context: "Needed durable state + execution capability without new infra"
    alternatives_rejected:
      - "harness-only"
      - "conductor-only flat state"
```

**Cadence:** Appended when significant decisions are made.

#### `health.yaml`
Business health snapshot refreshed each session from live data.

```yaml
schema_version: "1.0"
snapshot_date: 2026-03-15
tenants:
  total: 0
  active: 0
growth:
  active_experiments: 0
  wedge_fitness_latest: null
operations:
  jobs_last_24h: 0
  policy_blocks_last_24h: 0
  verification_failures_last_24h: 0
engineering:
  open_branches: 0
  recent_commits_7d: 0
  pending_prs: 0
```

**Cadence:** Refreshed at the start of each briefing.

### Unified Status Enum
All statuses across priorities, workstreams, and dispatch tasks use the same enum:
`not_started | in_progress | blocked | done | abandoned`

Dispatch tasks additionally use `ready` (equivalent to `not_started` with no blockers) for clarity in the dispatch context.

### Health.yaml Field Sources
| Field | Source |
|-------|--------|
| `tenants.*` | Supabase REST: `tenants` table |
| `growth.*` | Supabase REST: `experiment_history`, `wedge_fitness_snapshots` |
| `operations.*` | Supabase RPC: `get_metric_snapshot(1440)` |
| `engineering.open_branches` | `git branch -r --no-merged main \| wc -l` |
| `engineering.recent_commits_7d` | `git log --oneline --since="7 days ago" main \| wc -l` |
| `engineering.pending_prs` | `gh pr list --state open \| wc -l` |

### Design Rationale
- Separate files per cadence prevents merge conflicts and keeps each file scannable.
- YAML format matches existing worker-specs and industry-pack patterns.
- `schema_version` enables future schema evolution.
- Wiki-link references (`goal_ref`) connect to the existing knowledge graph.

## Component 2: Conductor Skill

### Skill Identity
- **Name:** `chief-of-staff`
- **Trigger:** `/chief-of-staff [mode] [args]`
- **Location:** Skill file in the project (or installed via Conductor skill system)

### Modes

#### Mode 1: `briefing` (default)
**Trigger:** `/chief-of-staff` or `/chief-of-staff briefing`

**Steps:**
1. Read `knowledge/chief-of-staff/*.yaml` for current state
2. Query Supabase REST API via `curl` for live data:
   - Tenant count and status: `GET /rest/v1/tenants?select=status`
   - Recent jobs: `GET /rest/v1/jobs?select=status&created_at=gt.<24h-ago>`
   - Metric events: `GET /rest/v1/metric_events?select=category,event_name&created_at=gt.<24h-ago>`
   - Growth experiments: `GET /rest/v1/experiment_history?select=status`
3. Check git: `git log --oneline -10 main`, `git branch -r --no-merged main`
4. Read `knowledge/company/goals-2026.md` for strategic context
5. Synthesize into structured briefing:
   - Business health (green/yellow/red)
   - Top 3 priorities with status and next step
   - What changed since last session
   - Recommended next actions (3 max)
6. Update `health.yaml` with fresh snapshot

**Output format:**
```
CHIEF OF STAFF BRIEFING — {date}

BUSINESS HEALTH: {color}
{1-3 line summary}

TOP PRIORITIES:
1. {status icon} {title} [{status}]
   → {next step or blocker}

CHANGES SINCE LAST SESSION:
- {git/data changes}

RECOMMENDED NEXT ACTIONS:
a) {action} — {why this matters now}
b) {action} — {why this matters now}
c) {action} — {why this matters now}

Approve an action to plan it, or ask me anything.
```

#### Mode 2: `plan <action description>`
**Trigger:** `/chief-of-staff plan "Wire up product-manager worker"`

**Steps:**
1. Read relevant knowledge nodes (worker specs, architecture docs, existing code patterns)
2. Break the action into concrete, dispatchable tasks
3. Identify dependencies between tasks
4. Identify which tasks can run in parallel
5. Present plan for founder approval

**Output format:**
```
PLAN: {action title}

Tasks:
1. {task title}
   Files: {key file paths}
   Acceptance: {criteria}

2. {task title} [depends on: #1]
   Files: {key file paths}
   Acceptance: {criteria}

Parallel workspaces: {count}
Dependencies: {description}

Approve to dispatch, or modify the plan.
```

#### Mode 3: `dispatch`
**Trigger:** `/chief-of-staff dispatch` (after plan approval, same conversation session)

**Plan-to-dispatch handoff:** Dispatch reads the approved plan from the current conversation context (LLM memory). Plan and dispatch must happen in the same Conductor session. If the session is lost, re-run `plan` to regenerate.

**Concurrency rule:** Only one active dispatch at a time. If `active-dispatch.yaml` exists with `status: dispatched`, dispatch mode refuses and suggests running `debrief` first (or `dispatch --abandon` to discard the stale dispatch).

**Steps:**
1. Check for existing active dispatch; refuse if one exists
2. Create workstream entries in `workstreams.yaml`
3. Write dispatch manifest to `knowledge/chief-of-staff/active-dispatch.yaml`
3. Write `.context/dispatch-<task-id>.md` files for each task containing:
   - Task description and acceptance criteria
   - Relevant file paths to read first
   - Knowledge context (worker specs, patterns to follow)
   - Dependencies and sequencing notes
4. Output human-readable summary of what was prepared

**Dispatch manifest schema:**
```yaml
dispatch:
  id: disp-{date}-{seq}
  plan_ref: "{action title}"
  created: {timestamp}
  dispatch_head_sha: "{git HEAD SHA at dispatch time}"
  status: dispatched    # dispatched | completed | abandoned
  tasks:
    - id: task-1
      title: "{title}"
      context_file: ".context/dispatch-task-1.md"
      depends_on: []
      status: ready       # ready | blocked | in_progress | done
    - id: task-2
      title: "{title}"
      context_file: ".context/dispatch-task-2.md"
      depends_on: [task-1]
      status: blocked
```

#### Mode 4: `debrief`
**Trigger:** `/chief-of-staff debrief` (after agent work completes)

**How debrief sees agent work:** Dispatched agents work in separate Conductor workspaces but share the same git repo. Agents must commit their work to branches. Debrief detects new commits since `dispatch_head_sha` and new/updated branches. If agents wrote `.context/` artifacts and committed them, debrief reads those too.

**Steps:**
1. Read `active-dispatch.yaml` for dispatch context and `dispatch_head_sha`
2. Check git for new commits since `dispatch_head_sha`, new branches, merged PRs
3. Read `.context/dispatch-*.md` files and any agent-written `.context/` artifacts
3. Update `workstreams.yaml` — mark completed workstreams, record outcomes
4. Update `priorities.yaml` — adjust health signals based on progress
5. Update `active-dispatch.yaml` — mark tasks as done
6. Log any decisions made during work in `decisions.yaml`
7. Output summary: what was accomplished, what's still open, what's next

### The Loop
```
briefing → (founder picks action) → plan → (founder approves) → dispatch → (agents work) → debrief → briefing
```

### Approval Model
- **All actions require founder approval** before dispatch
- The skill recommends, the founder decides
- Founder overrides are logged in `decisions.yaml` as training signal

## Component 3: Data Collection

### Supabase Queries
Executed via `curl` to the Supabase REST API using the **`service_role` key** (from `SUPABASE_SERVICE_ROLE_KEY` env var). The service_role key bypasses RLS, which is required for cross-tenant aggregate queries. The key is passed in the `apikey` and `Authorization: Bearer` headers.

**Security:** `curl` commands must use `-s` (silent) to avoid logging headers. The skill must never write the service key to files, `.context/` artifacts, or conversation output.

| Query | Endpoint | Purpose |
|-------|----------|---------|
| Tenant health | `GET /rest/v1/tenants?select=id,status` | Count active tenants (status='active') |
| Recent jobs | `GET /rest/v1/jobs?select=status&created_at=gt.{24h_ago}` | Operational throughput |
| Metric snapshot | `POST /rest/v1/rpc/get_metric_snapshot` with `{"window_minutes": 1440}` | Policy/verification health (uses existing RPC) |
| Growth experiments | `GET /rest/v1/experiment_history?select=status` | Growth loop activity (active = `exploring` or `converging`) |
| Wedge fitness | `GET /rest/v1/wedge_fitness_snapshots?order=snapshot_week.desc&limit=1` | Latest wedge score |

**Failure modes:**
- Supabase unreachable: proceed with cached `health.yaml`, note staleness in briefing output
- Partial failure (some queries succeed, some fail): use what succeeded, note which data is stale
- Service key not set: skip all Supabase queries, warn founder to set `SUPABASE_SERVICE_ROLE_KEY`

### Git Queries
| Query | Command | Purpose |
|-------|---------|---------|
| Recent commits | `git log --oneline -10 main` | Engineering velocity |
| Open branches | `git branch -r --no-merged main` | Active workstreams |
| PR status | `gh pr list --state open` | Pending reviews |

### Knowledge Graph
- Direct file reads via the Read tool
- Follows wiki-link references to resolve connected nodes
- Uses `trust_level` and `last_reviewed` metadata to flag stale content in briefings

## Component 4: Context Handoff (.context/ files)

When dispatching work, the skill writes `.context/dispatch-<task-id>.md` files that new Conductor workspaces automatically pick up.

### File Format
```markdown
# Dispatch: {task title}

## Task
{description of what to do}

## Files to Read First
- {path} — {why}
- {path} — {why}

## Pattern to Follow
{description of existing pattern with file reference}

## Acceptance Criteria
- {criterion}
- {criterion}

## Dependencies
{what must be done before/after this task}

## Context
{relevant knowledge: worker spec excerpts, architecture decisions, etc.}
```

### Lifecycle
1. Created by `dispatch` mode
2. Read by agents in new workspaces
3. Cleaned up by `debrief` mode: deletes files matching `.context/dispatch-*.md` only (preserves other `.context/` files like `notes.md`, `todos.md`)

## File Inventory

### New Files
| File | Purpose |
|------|---------|
| `knowledge/chief-of-staff/_moc.md` | Map of contents |
| `knowledge/chief-of-staff/priorities.yaml` | Ranked business priorities |
| `knowledge/chief-of-staff/workstreams.yaml` | Active parallel work |
| `knowledge/chief-of-staff/decisions.yaml` | Founder decision log |
| `knowledge/chief-of-staff/health.yaml` | Business health snapshot |
| `knowledge/chief-of-staff/active-dispatch.yaml` | Current dispatch manifest |
| Skill file (location TBD by skill system) | The `/chief-of-staff` skill |
| `.context/dispatch-*.md` | Per-task context handoff files (ephemeral) |

### Modified Files
| File | Change |
|------|--------|
| `knowledge/_moc.md` | Add link to `[[chief-of-staff/_moc]]` |

## Verification Plan

### Manual Testing
1. **Briefing mode:** Invoke `/chief-of-staff briefing`. Verify it reads knowledge graph, queries Supabase (or gracefully degrades), checks git, and produces a structured briefing.
2. **Plan mode:** Invoke `/chief-of-staff plan "Write integration tests for customer-analyst"`. Verify it produces concrete, dispatchable tasks with file paths and acceptance criteria.
3. **Dispatch mode:** Approve the plan, invoke `/chief-of-staff dispatch`. Verify it creates workstream entries, writes dispatch manifest, and writes `.context/` files.
4. **Debrief mode:** After making some commits, invoke `/chief-of-staff debrief`. Verify it detects changes, updates workstreams, and summarizes outcomes.
5. **Full loop:** Run briefing → plan → dispatch → (do work) → debrief → briefing and verify state persists correctly.

### Validation
- Run `node scripts/validate-knowledge.ts` to ensure new knowledge files have correct frontmatter
- Verify YAML files parse correctly
- Check that wiki-link references resolve

## Future Extensions (Not In Scope)
- **Inngest cron** to auto-refresh `health.yaml` periodically
- **Trust threshold** for auto-dispatching routine work without approval
- **Trend tracking** in health snapshots (compare week-over-week)
- **Conductor API integration** for programmatic workspace spawning when available

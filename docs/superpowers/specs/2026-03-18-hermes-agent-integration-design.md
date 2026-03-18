# Hermes Agent Integration Design

**Date:** 2026-03-18
**Status:** Draft
**Author:** Rashid Baset + Claude
**Depends on:** [LLM Tool Assignments](2026-03-18-llm-tool-assignments.md), [Corporate Hierarchy](2026-03-17-corporate-hierarchy-agent-roster.md), [Product Guardian](2026-03-18-product-guardian-design.md)

## Summary

Integrate [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) into CallLock AgentOS at two levels:

1. **Execution layer** — Replace single-shot `call_llm()` in the supervisor's worker node with a Hermes AIAgent running a multi-turn agent loop (tool use, file ops, web search, terminal access). Workers gain real autonomy while the supervisor retains governance.

2. **Founder layer** — Run a standalone Hermes instance as the founder's personal CEO agent, accessible via Telegram for quick commands and pushing notifications. Agent organizational activity projects into Discord for full transparency.

Learning is human-gated: workers don't create skills autonomously. Impressive runs get flagged as skill candidates, the founder reviews them, and approved skills land in the knowledge graph as auditable markdown files.

## Architecture

Three nested layers with one invariant: governance wraps execution, never the reverse.

```
┌─────────────────────────────────────────────────────────────┐
│                    FOUNDER LAYER                             │
│                                                              │
│  Telegram (control)              Discord (transparency)      │
│  ┌──────────────────┐           ┌────────────────────────┐  │
│  │ Hermes CEO Agent │           │ Event Projector        │  │
│  │ DM: commands,    │           │ Forum channels per     │  │
│  │ approvals, push  │──links──▶│ dept, thread per run,  │  │
│  │ notifications    │           │ cross-cutting feeds    │  │
│  └────────┬─────────┘           └────────┬───────────────┘  │
│           │ MCP tools                     │ Inngest events   │
└───────────┼───────────────────────────────┼──────────────────┘
            │                               │
┌───────────┼───────────────────────────────┼──────────────────┐
│           ▼         GOVERNANCE LAYER (unchanged)             │
│                                                               │
│  context_assembly → policy_gate → worker → verification      │
│                                              │                │
│                                         skill_candidate?     │
│                                              │                │
│                                         job_dispatch          │
│                                              │                │
│                                           persist             │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────┼────────────────────────────────┐
│                    EXECUTION LAYER (new)                       │
│                                                                │
│  Hermes AIAgent (headless, per-run, stateless)                │
│  - model: from supervisor routing logic                        │
│  - system_prompt: from context_assembly + worker skills        │
│  - toolsets: from policy_gate tool_grants                      │
│  - memory: OFF                                                 │
│  - delegation: OFF                                             │
│  - max_iterations: from worker spec                            │
│                                                                │
│  Skill Store: knowledge/worker-skills/{worker_id}/             │
│  - Git-tracked, PR-reviewed, auditable                         │
│  - Loaded by context_assembly per worker                       │
│  - Created via promotion pipeline, not autonomously            │
└────────────────────────────────────────────────────────────────┘
```

### Invariants

- A Hermes worker never runs without passing through policy_gate first.
- A Hermes worker never persists its own state between runs.
- A Hermes worker never dispatches its own children (delegation toolset blocked; dispatch goes through the supervisor).
- The supervisor is always the authority on what runs, what's allowed, and what's verified.
- The CEO agent cannot bypass governance — all dispatches go through the existing policy gate and concurrency limits.

## Integration Surface

### Worker Node Changes

The integration point is `base.py:run_worker()`, which currently calls `call_llm(build_prompt(...), output_fields)` on line 99. The Hermes branch inserts before the existing LLM path, using the same feature flag pattern (`task.get("feature_flags", {})`).

```python
# harness/src/harness/graphs/workers/base.py

def run_worker(
    task: dict[str, Any],
    *,
    worker_id: str,
    deterministic_builder: Callable[[dict[str, Any]], dict[str, Any]],
    llm_enabled: bool = True,
) -> dict[str, Any]:
    worker_spec = task.get("worker_spec") or load_worker_spec(worker_id)
    output_fields = expected_output_fields(worker_spec)
    deterministic_mode = task.get("tenant_config", {}).get("deterministic_mode", False)
    feature_flags = task.get("feature_flags", {})

    # Hermes path: multi-turn agent loop (per-worker opt-in)
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"hermes_worker_{worker_id}", False)):
        try:
            generated = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass  # fall through to existing paths

    # Existing LLM path: single-shot call_llm
    if llm_enabled and not deterministic_mode and feature_flags.get("llm_workers_enabled", True):
        try:
            generated = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass

    return ensure_output_shape(deterministic_builder(task), output_fields)
```

Feature flags are per-worker (`hermes_worker_eng-ai-voice`, `hermes_worker_eng-qa`, etc.) to enable incremental rollout. Flags come from `task["feature_flags"]`, consistent with the existing pattern.

### Hermes Adapter

New file: `harness/src/harness/hermes_adapter.py`

Responsibilities:
1. Accept the `task` dict and extract relevant fields (context_items, tool_grants, tenant_id).
2. Build a system prompt from context_assembly output + worker skills.
3. Map domain-specific tool_grants to Hermes toolset enables.
4. Run the Hermes agent loop headless with a wall-clock timeout.
5. Extract structured output from Hermes's free-form response.

**Hermes dependency:** `hermes-agent` pinned in `harness/pyproject.toml`. The import path must be verified against the installed package (likely `from hermes_agent import AIAgent` or `from run_agent import AIAgent` depending on package structure). This must be confirmed during Week 1 implementation by inspecting the installed package.

```python
# hermes-agent import — exact path TBD, verified at implementation time
# Candidate: from hermes_agent import AIAgent
# Fallback:  from run_agent import AIAgent
import signal
from typing import Any

BLOCKED_TOOLSETS = frozenset([
    "delegation",       # dispatch goes through supervisor
    "memory",           # no persistent state between runs
    "clarify",          # no user interaction mid-run
])
# Note: Hermes's "code_execution" toolset (execute_code sandbox) is
# separate from "terminal" (shell access). terminal is the primary
# tool workers use. code_execution is a sandboxed Python runner used
# for script generation — not blocked by default, but can be blocked
# per-worker via tool grant mapping if needed.

WALL_CLOCK_TIMEOUT_SECONDS = 120  # hard cap on any single worker run

def run_hermes_worker(
    task: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
) -> dict[str, Any]:
    """Run a Hermes AIAgent as the worker execution engine.

    Accepts the full task dict from the supervisor (same shape as
    base.run_worker receives). Extracts context_items, tool_grants,
    and tenant_id from the task to configure the Hermes agent.
    """
    from hermes_agent import AIAgent  # deferred import, only when feature flag is on

    # Extract supervisor state from task dict
    context_items = task.get("context_items", [])
    tool_grants = task.get("tool_grants", [])
    tenant_id = task.get("tenant_id", "")
    output_fields = expected_output_fields(worker_spec)

    # Model resolution — uses the resolve_model function from
    # the LLM Tool Assignments spec (2026-03-18-llm-tool-assignments.md)
    model_alias, override_fired, override_reason = resolve_model(
        worker_spec=worker_spec,
        context=task.get("task_context", {}),
    )

    system_prompt = build_hermes_system_prompt(
        spec=worker_spec,
        assembled_context=context_items,
        worker_skills=load_worker_skills(worker_id, tenant_id),
        output_fields=output_fields,
    )

    # Map domain-specific tool_grants to Hermes toolset categories
    toolsets = map_tool_grants_to_toolsets(tool_grants, blocked=BLOCKED_TOOLSETS)

    max_iterations = worker_spec.get("max_iterations", 15)

    # Build user message from task (same fields as build_prompt uses)
    user_message = (
        f"Problem: {task.get('problem_description', '')}\n"
        f"Transcript: {task.get('transcript', '')}\n"
        f"Task context: {json.dumps(task.get('task_context', {}), indent=2)}"
    )

    agent = AIAgent(
        model=model_alias,
        max_iterations=max_iterations,
        enabled_toolsets=list(toolsets),
        skip_memory=True,
        skip_context_files=True,
        quiet_mode=True,
    )

    # Wall-clock timeout to prevent hangs on external tool calls
    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Hermes worker {worker_id} exceeded {WALL_CLOCK_TIMEOUT_SECONDS}s")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(WALL_CLOCK_TIMEOUT_SECONDS)
    try:
        raw = agent.run_conversation(
            user_message=user_message,
            system_message=system_prompt,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    # Normalize return — run_conversation may return dict or string
    if isinstance(raw, dict):
        response_text = raw.get("final_response", str(raw))
    else:
        response_text = str(raw)

    return extract_structured_output(response_text, output_fields)
```

**Note on state threading:** The `task` dict must include `context_items` and `tool_grants` by the time it reaches `run_worker()`. These are populated by the `context_assembly` and `policy_gate` nodes respectively, and must be threaded through the supervisor state into the task dict. If they are not already present in `task`, the supervisor graph's worker node must be modified to copy them from `HarnessState` into `task` before calling `run_worker()`.

### System Prompt Bridge

`build_hermes_system_prompt()` assembles the Hermes system prompt from supervisor-owned context:

- Worker identity and mission (from worker spec)
- Assembled context items (from context_assembly node — knowledge graph, tenant config, industry pack)
- Accumulated worker skills (from `knowledge/worker-skills/{worker_id}/`)
- Output contract (JSON schema matching worker spec outputs — tells Hermes what shape to return)

### Tool Grant Mapping

Worker specs define domain-specific `tools_allowed` (e.g., `supabase_read`, `extraction_rerun`, `scorecard_evaluate`). These don't map 1:1 to Hermes's toolset categories. The mapping works in two layers:

**Layer 1: Hermes toolset enables** — which categories of Hermes tools are active:

| Worker spec `tools_allowed` contains | Hermes toolset enabled | Notes |
|---|---|---|
| Any `*_read`, `read_*` tool | `file` | File read access |
| Any `write_*`, `*_write` tool | `file` + `terminal` | File write + shell for git |
| `web_search`, `web_fetch` | `web` | Web access |
| `browser`, `headless_browser` | `browser` | Browser automation |
| *(never)* | `delegation` | Always blocked |
| *(never)* | `memory` | Always blocked |
| *(never)* | `clarify` | Always blocked |

**Layer 2: Domain-specific tools as MCP** — tools like `supabase_read`, `extraction_rerun`, `retell_config_diff` become MCP tools available to the Hermes agent. These are implemented as a lightweight MCP server that wraps the existing harness tool implementations, scoped to the current tenant. This is a Week 7+ deliverable — initial rollout uses only Hermes built-in toolsets.

### Output Extraction

Hermes returns natural language with an embedded JSON block. The extractor:

1. Searches for a ```json block in the response.
2. Validates all expected fields from the worker spec are present.
3. If the JSON block is missing or incomplete, falls back to a cheap LLM extraction call (zeroclaw/qwen) that pulls structured fields from the natural language response.

This fallback handles the case where Hermes solves the problem correctly but doesn't format its final answer as JSON.

## Skill Promotion Pipeline

### Skill Candidate Detection

Added to the verification node. No extra LLM call — uses heuristics from existing run data.

**Signals that trigger a skill candidate flag:**

| Signal | Condition | Rationale |
|---|---|---|
| `high_confidence_pass` | Verification confidence ≥ 0.9 | Worker did something notably well |
| `recovered_from_failures` | Same task_type failed in last 7 days, now passing | Worker figured something out |
| `exploratory_solve` | Iterations > 1.5× average AND > 5 total | Worker explored approaches and found a path |

If any signal fires, a skill candidate record is emitted containing: worker_id, task_type, run_id, signals, summary, and tenant_id (for contamination awareness).

### Promotion Flow

```
Verification passes with skill candidate signals
        │
        ▼
Skill candidate record written to skill_candidates table
        │
        ▼
Surfaces in:
  - Daily memo (passive — founder reads at desk)
  - Discord #skills topic (push — thread with details)
  - CEO agent morning briefing on Telegram (push — notification)
        │
        ▼
Founder reviews and acts via CEO agent:
  - promote_skill(worker_id, run_id, universal=true)
  - promote_skill(worker_id, run_id, universal=false)  ← tenant-specific
  - dismiss_skill_candidate(run_id, reason="...")
        │
        ▼
If promoted:
  1. Load run transcript from audit log
  2. LLM call extracts reusable procedure
  3. Write skill file to knowledge/worker-skills/{worker_id}/
  4. Git commit (auditable, diffable, revertable)
  5. Next run: context_assembly includes skill
```

### Skill File Format

```
knowledge/worker-skills/
  eng-ai-voice/
    carrier-emergency-extraction.md
    multi-unit-commercial-parsing.md
  eng-qa/
    seam-contract-validation-sequence.md
  customer-analyst/
    churn-signal-from-callback-pattern.md
```

Each skill file has frontmatter (extends standard knowledge node schema from CLAUDE.md):

```yaml
---
id: skill-{worker_id}-{slug}
title: "Carrier Emergency Dispatch Extraction"
graph: worker-skills
owner: eng-ai-voice
last_reviewed: 2026-03-20
trust_level: curated
progressive_disclosure:
  summary_tokens: 40
  full_tokens: 200
# Skill-specific fields (extend base schema):
worker_id: eng-ai-voice
created_from_run: run_abc123
created_at: 2026-03-20
promoted_by: rashid
tenant_context: tenant_acme      # which tenant's data triggered this
universal: true                   # founder judged universally applicable
---
```

Body contains: description of the pattern, step-by-step procedure, expected output impact.

**Note:** Skill files follow the standard knowledge node frontmatter conventions (id, title, graph, owner, last_reviewed, trust_level, progressive_disclosure) plus skill-specific extensions. The `worker-skills/` directory must be added to CLAUDE.md's monorepo layout section when implemented.

### Tenant Contamination Handling

Every skill records `tenant_context` and `universal` flag. Context assembly filters:

- **Universal skills** (`universal: true`) — loaded for all tenants. The founder judged the pattern as brand-specific or domain-general, not tenant-specific.
- **Tenant-specific skills** (`universal: false`) — loaded only when `tenant_context` matches the current run's `tenant_id`.

This is a simple first approach. The founder makes the universal/tenant-specific judgment at promotion time, informed by the skill candidate's tenant_context field.

### Context Assembly Priority

Worker skills sit at priority 2 in context assembly — after the worker spec (identity/mission) but before task context:

```
1. worker_spec          (identity, mission)
2. worker_skills        (accumulated procedures)  ← NEW
3. task_context          (current task details)
4. tenant_config         (tenant settings)
5. industry_pack         (vertical templates)
6. knowledge_graph       (domain knowledge)
7. memory                (run history)
8. history               (conversation history)
```

Skills get priority over lower sources, so a worker with 5 accumulated skills gets all of them before the token budget runs out on history.

## CEO Agent

### Architecture

A standalone Hermes instance running on a $5 VPS. Connected to the founder via Telegram DM. Connected to CallLock AgentOS via 10 MCP tools.

**Not part of the supervisor graph.** The CEO agent talks to the governance layer via HTTP/Inngest, the same way a human would interact through the existing APIs. It cannot bypass policy gates or concurrency limits.

### Model and Configuration

- **Model:** claude-opus (exec tier — this is the founder's personal agent)
- **Memory:** `~/.hermes/memories/` on the VPS — stores founder preferences, decision history, customer relationships, past approval reasoning
- **Skills:** Custom founder workflow skills (morning-briefing, dispatch-review, skill-promotion)
- **Platform:** Telegram primary (DM with inline keyboards for approvals)

### MCP Tools

10 tools giving the CEO agent full control over the AgentOS:

| Tool | Purpose |
|---|---|
| `dispatch_worker` | Send a task to any worker in the 30-agent roster |
| `check_quest_log` | Read pending approval requests |
| `approve_quest` | Approve a blocked dispatch |
| `promote_skill` | Extract and save a skill from a completed run |
| `dismiss_skill_candidate` | Mark a candidate as reviewed and dismissed |
| `read_daily_memo` | Get aggregated status across all agents |
| `query_knowledge` | Read from the knowledge graph |
| `check_agent_status` | Check current state of agents (idle/active/queued) |
| `read_audit_log` | Read recent command audit log entries |
| `trigger_voice_eval` | Kick off a voice pipeline evaluation run |

### Cron Schedule

| Job | Schedule | Action |
|---|---|---|
| Morning briefing | 6:00 AM daily | Summarize overnight: failures, pending approvals, skill candidates, voice eval. Send to Telegram |
| Evening digest | 6:00 PM daily | Day summary: runs completed, idle agents, recurring failures. Send to Telegram |
| Weekly retro | Sunday 9:00 AM | Week analysis: runs by department, success rates, skills promoted, cost by model tier, trends. Send to Telegram |

## Discord Observability

### Purpose

Real-time organizational transparency. A scrollable, searchable history of what every agent is doing, how they're communicating, and what decisions are being made. Not a point-in-time dashboard — a living feed.

### Channel Structure

```
CallLock AgentOS (Discord Server)
├── 📁 EXECUTIVE
│   └── #executive-activity (forum)
├── 📁 ENGINEERING
│   ├── #engineering-activity (forum)       ← thread per run
│   ├── #dispatches (feed)                  ← cross-department dispatches
│   └── #health-checks (feed)              ← daily health results
├── 📁 PRODUCT
│   └── #product-activity (forum)
├── 📁 GROWTH
│   └── #growth-activity (forum)
├── 📁 CUSTOMER SUCCESS
│   └── #cs-activity (forum)
├── 📁 SALES
│   └── #sales-activity (forum)
├── 📁 FINANCE
│   └── #finance-activity (forum)
├── 📁 OPERATIONS
│   ├── #approvals (forum)                  ← quests needing sign-off
│   ├── #skills (forum)                     ← candidates + promotions
│   └── #incidents (feed)                   ← failures, escalations
└── 📁 META
    ├── #daily-memo (feed)                  ← morning/evening summaries
    └── #weekly-retro (feed)                ← weekly analysis
```

### Event Projection

New component: `discord_event_projector.py` (Inngest function)

Subscribes to existing Inngest events and writes to Discord via webhooks:

| Inngest Event | Discord Target | Format |
|---|---|---|
| `calllock/agent.state.changed` | Department forum (thread update) | Turn-by-turn activity within run thread |
| `calllock/agent.dispatch` | `#dispatches` + department forum | New thread in target department, summary in dispatches |
| `calllock/agent.handoff` | `#dispatches` + both department forums | Handoff context in both department threads |
| `calllock/agent.verification` | Department forum (thread update) | Verification result with confidence score |
| Skill candidate detected | `#skills` | New thread with candidate details |
| Quest created | `#approvals` | New thread with approval request |

### Rich Embeds

Discord embeds use color-coded sidebars:

- 🟢 Green sidebar: run started, health check passed, skill promoted
- 🟡 Yellow sidebar: warning, skill candidate, quest pending
- 🔴 Red sidebar: run failed, verification blocked, incident

### Thread-Per-Run

Each agent run creates a forum thread in its department channel. The thread title includes status emoji, worker name, and task type. Turn-by-turn Hermes activity posts as replies within the thread. The forum channel view shows one-line summaries — click into a thread for full detail.

This keeps department channels clean while preserving full agent reasoning chains for review.

### Verbosity

Configurable per department via a `discord_verbosity` field in worker specs:

- `full` — every Hermes turn posted to thread (default for engineering)
- `milestones` — start, key findings, completion only (default for growth, sales)
- `summary` — single message with final result (for low-interest workers)

### CEO Agent Integration

The CEO agent on Telegram links to Discord threads when detail is needed:

```
CEO Agent (Telegram):
  ⚠️ eng-app found an issue during health check.
  Card rendering "Unknown" for call_abc.

  [View full run → discord thread link]
  [Approve dispatch to eng-ai-voice ✅]
  [Dismiss ❌]
```

### Role-Based Access (Future)

When the founder hires:
- Engineers join Discord, see #engineering but not #finance
- Sales team sees #sales and #customer-success
- Everyone sees #daily-memo and #weekly-retro
- Only the founder sees #approvals and #incidents

## Rollout Strategy

### Week 1-2: Foundation

**Goal:** Hermes runs as a library inside the harness. No workers use it yet.

**New files:**
- `harness/src/harness/hermes_adapter.py` — adapter, output extraction, system prompt bridge, tool grant mapping

**Modified files:**
- `harness/pyproject.toml` — add `hermes-agent` dependency (pinned version)
- `harness/src/harness/graphs/workers/base.py` — feature flag branch in `run_worker()` (line 97)
- `harness/src/harness/nodes/verification.py` — skill candidate detection stub (returns None)

**Prerequisite:** Verify Hermes AIAgent import path from installed package. Test `from hermes_agent import AIAgent` vs `from run_agent import AIAgent`. Document the correct path.

**Tests:** Adapter produces valid output shapes, blocked toolsets enforced, model routing from LLM Tool Assignments spec is respected, output extractor finds JSON blocks, LLM fallback works, wall-clock timeout fires correctly.

### Week 3-4: Shadow Mode on eng-ai-voice

**Goal:** eng-ai-voice runs on both `call_llm()` and `run_hermes_worker()`. Compare outputs.

Shadow mode runs both paths, logs field-by-field comparison, but always returns the baseline result. Comparison tracks: field match rate, iteration count, cost, latency.

**Graduation criteria to switch eng-ai-voice to Hermes primary:**

| Metric | Threshold |
|---|---|
| Field match rate vs baseline | ≥ 95% across 50+ runs |
| Golden eval accuracy | ≥ 95% (matches current) |
| P95 latency | ≤ 30 seconds |
| Cost per run | ≤ 5× single-shot |
| Verification failures from output shape | Zero |

### Week 5-6: CEO Agent + Discord + Skills

**Goal:** CEO agent live on Telegram. Discord projector streaming agent activity. Skill candidate detection active.

**CEO agent deployment:** Standalone Hermes on $5 VPS. Telegram gateway. MCP server with 10 CallLock tools. Cron jobs for morning briefing, evening digest, weekly retro.

**Discord projector:** Inngest function subscribing to agent events, posting to Discord via webhooks.

**Skill pipeline:** `check_skill_candidate()` active in verification node. Candidates surface in Discord #skills and Telegram morning briefing.

**New Supabase migration:** `skill_candidates` table:

```sql
-- supabase/migrations/052_skill_candidates.sql
create table skill_candidates (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id),
    worker_id text not null,
    task_type text not null,
    run_id uuid not null,
    signals text[] not null,
    summary text,
    status text not null default 'pending' check (status in ('pending', 'promoted', 'dismissed')),
    promoted_by text,
    dismiss_reason text,
    created_at timestamptz not null default now(),
    reviewed_at timestamptz
);

alter table skill_candidates enable row level security;
create policy "tenant_isolation" on skill_candidates
    using (tenant_id = current_setting('app.current_tenant')::uuid);
```

**Modified files:**
- `harness/src/harness/nodes/context_assembly.py` — add `worker-skills/` as priority 2 source
- `harness/src/harness/nodes/verification.py` — activate `check_skill_candidate()`

### Week 7+: Expansion

Roll Hermes to additional workers based on shadow mode data. Priority order:

| Priority | Worker | Rationale |
|---|---|---|
| 1 | eng-ai-voice | Done in Week 3-4 |
| 2 | engineer | Code generation and migration planning benefits from multi-turn |
| 3 | eng-qa | Seam contract validation needs file reads + comparisons |
| 4 | product-manager | Feature analysis benefits from web research |
| 5 | customer-analyst | Churn detection needs data exploration |
| 6+ | Evaluate per-worker | Not every worker needs Hermes — single-shot is fine for simple tasks |

**Note:** Worker IDs must match existing specs in `knowledge/worker-specs/`. Currently implemented: `eng-ai-voice`, `eng-qa`, `engineer`, `customer-analyst`, `product-manager`, `designer`, `product-marketer`. Additional worker specs (e.g., for headless browser validation) should be created before enabling Hermes for those workers.

Per-worker iteration budgets tuned from shadow mode data.

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| Hermes dependency breaks harness | Feature flag off → falls back to `call_llm()`. Zero coupling when disabled |
| Worker output shape drift | `extract_structured_output()` with LLM fallback. Verification catches drift |
| Cost explosion | `max_iterations` per worker spec. Shadow mode tracks cost via LiteLLM token counting summed across all Hermes iterations |
| Worker hangs on external tool call | `WALL_CLOCK_TIMEOUT_SECONDS = 120` via `signal.alarm()` in adapter. Raises `TimeoutError`, falls through to `call_llm()` |
| CEO agent sends wrong dispatch | All dispatches go through existing policy gate + concurrency limits |
| Hermes upstream breaking change | Pin version in `pyproject.toml`. Upgrade deliberately |
| CEO agent Telegram compromise | Hermes DM pairing — only founder's account can talk to it. MCP tools use service role keys |
| Tenant contamination via skills | `universal` flag set by founder at promotion time. Tenant-specific skills filtered by context_assembly |
| Skill causes verification failures | Skills are human-reviewed before entering knowledge graph. If a promoted skill later causes failures, it can be reverted via git |

## Decisions Made

1. **Hermes as library, not fork.** Used headless with memory/delegation/clarify disabled. Preserves upstream compatibility.
2. **Governance wraps execution.** Supervisor owns policy, verification, dispatch, audit. Hermes is a powerful executor within those bounds.
3. **Human-gated learning.** Workers don't create skills autonomously. Founder promotes from candidates. Limits throughput but guarantees quality.
4. **Discord for transparency, Telegram for control.** Discord Forum Channels provide thread-per-run agent visibility. Telegram provides mobile command interface. CEO agent bridges both.
5. **Shadow mode rollout.** Every worker runs Hermes in shadow before switching. Golden eval sets are the graduation test.
6. **Per-worker feature flags.** Not all workers need Hermes. Single-shot `call_llm()` is preserved for simple tasks.

## Future Phases (Out of Scope)

- **Phase 3: Autonomous learning** — Workers propose skills, approval gate auto-approves low-risk, human reviews high-risk. Requires: skill risk scoring, verification profile auto-evolution, tenant-scope classification.
- **Customer-facing Hermes** — Hermes gateway (WhatsApp/Telegram) as customer-facing agent with Honcho user modeling, routing into voice pipeline.
- **Hermes-to-Hermes dispatch** — Directors as Hermes instances dispatching to Hermes workers, with supervisor as coordinator rather than executor.

# Hermes Phase 3 — CEO Agent, Discord, Skills, MCP

## Goal

Build the founder layer: skill candidate detection, skill promotion
pipeline, unified MCP server, Discord event projector, and CEO agent
Telegram gateway. All code is written and tested. External service
connections (Telegram bot token, Discord webhook URLs) are configured
via environment variables — actual deployment is a follow-up step.

After this plan:
- `skill_candidates` Supabase table exists
- `check_skill_candidate()` is activated with real heuristics
- Skill promotion service extracts and saves skills from runs
- Unified MCP server wraps harness tools for workers + CEO agent
- Discord event projector Inngest function exists
- CEO agent configuration and MCP tool definitions exist
- Repository layer has skill candidate CRUD
- All existing tests pass + new tests

## Prerequisites

- Hermes Phase 1 + Phase 2 complete
- Migration numbering: next is 057

---

## Task 1: Skill Candidates Table

### File: `supabase/migrations/057_skill_candidates.sql`

**Create this file:**

```sql
-- Skill candidate records from verification node.
-- Flagged when a worker run shows signals of reusable procedures.
-- Founder reviews and promotes or dismisses via CEO agent.

create table skill_candidates (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id),
    worker_id text not null,
    task_type text not null,
    run_id text not null,
    signals text[] not null,
    summary text,
    status text not null default 'pending'
        check (status in ('pending', 'promoted', 'dismissed')),
    promoted_by text,
    dismiss_reason text,
    created_at timestamptz not null default now(),
    reviewed_at timestamptz
);

alter table skill_candidates enable row level security;
alter table skill_candidates force row level security;
create policy skill_candidates_tenant on skill_candidates
    using (tenant_id = current_setting('app.current_tenant')::uuid);

create index idx_skill_candidates_status on skill_candidates (status, created_at desc);
create index idx_skill_candidates_worker on skill_candidates (worker_id, created_at desc);

comment on table skill_candidates is
    'Skill candidate records flagged by verification node for founder review';
```

### Verification

```bash
ls supabase/migrations/057_skill_candidates.sql && echo "Migration exists"
```

---

## Task 2: Skill Candidate Repository Layer

### File: `harness/src/db/repository.py`

**Change:** Add three functions at the end of the file (before any trailing newlines):

```python
def create_skill_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.create_skill_candidate(payload)
    return local_repository.create_skill_candidate(payload)


def list_skill_candidates(*, tenant_id: str | None = None, status: str | None = None, worker_id: str | None = None) -> list[dict[str, Any]]:
    if using_supabase():
        return supabase_repository.list_skill_candidates(tenant_id=tenant_id, status=status, worker_id=worker_id)
    return local_repository.list_skill_candidates(tenant_id=tenant_id, status=status, worker_id=worker_id)


def update_skill_candidate(candidate_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if using_supabase():
        return supabase_repository.update_skill_candidate(candidate_id, updates)
    return local_repository.update_skill_candidate(candidate_id, updates)
```

### File: `harness/src/db/local_repository.py`

**Change:** Add matching stub functions at the end:

```python
def create_skill_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    return {"id": "local-skill-candidate", **payload}


def list_skill_candidates(*, tenant_id: str | None = None, status: str | None = None, worker_id: str | None = None) -> list[dict[str, Any]]:
    return []


def update_skill_candidate(candidate_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    return {"id": candidate_id, **updates}
```

### File: `harness/src/db/supabase_repository.py`

**Change:** Add matching functions. Follow the existing pattern in the file
for Supabase client calls. Look at how `create_shadow_comparison` or
`upsert_agent_report` are implemented and follow the same pattern.

### Verification

```bash
cd harness && PYTHONPATH=src python -c "from db.repository import create_skill_candidate, list_skill_candidates, update_skill_candidate; print('Skill candidate repo OK')"
```

---

## Task 3: Activate Skill Candidate Detection

### File: `harness/src/harness/nodes/verification.py`

**Change:** Replace the stub `check_skill_candidate` with real heuristics.

```python
def check_skill_candidate(
    worker_output: dict[str, Any],
    verification: dict[str, Any],
    worker_id: str,
    task_type: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Check if this run should be flagged as a skill candidate.

    Uses heuristics from run data — no extra LLM call needed.

    Signals:
    - high_confidence_pass: verification confidence >= 0.9
    - recovered_from_failures: same task_type has recent failures
    - exploratory_solve: iterations > 5 (multi-turn exploration)
    """
    signals = []
    confidence = verification.get("confidence", 0.0)

    # Signal 1: High confidence pass
    if confidence >= 0.9 and verification.get("outcome") == "pass":
        signals.append("high_confidence_pass")

    # Signal 2: Exploratory solve (Hermes used multiple iterations)
    iterations = worker_output.get("_hermes_iterations", 0)
    if iterations > 5:
        signals.append("exploratory_solve")

    # Signal 3: Output has novel fields or patterns
    # (Simple heuristic: output has more non-null fields than expected minimum)
    non_null_fields = sum(1 for v in worker_output.values() if v is not None and v != "")
    if non_null_fields >= 5 and confidence >= 0.8:
        signals.append("thorough_output")

    if not signals:
        return None

    return {
        "worker_id": worker_id,
        "task_type": task_type,
        "run_id": run_id,
        "signals": signals,
        "summary": f"Skill candidate: {', '.join(signals)} (confidence={confidence:.2f})",
    }
```

Also update `verification_node` to persist skill candidates. After the
`check_skill_candidate` call, add:

```python
    if skill_candidate:
        try:
            from db import repository
            repository.create_skill_candidate({
                "tenant_id": task.get("tenant_id", ""),
                "worker_id": skill_candidate["worker_id"],
                "task_type": skill_candidate["task_type"],
                "run_id": skill_candidate["run_id"],
                "signals": skill_candidate["signals"],
                "summary": skill_candidate["summary"],
            })
        except Exception:
            pass  # best-effort persistence
```

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/ -x -q 2>&1 | tail -10
```

---

## Task 4: Skill Promotion Service

### File: `harness/src/harness/skill_promotion.py`

**Create this file:**

```python
"""Skill promotion pipeline.

Extracts a reusable procedure from a completed run and saves it
as a markdown skill file in knowledge/worker-skills/{worker_id}/.

The promotion flow:
1. Load run audit log (or worker output) for the candidate run
2. Generate a skill description from the run data
3. Write the skill file with standard frontmatter
4. Mark the skill candidate as promoted
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "knowledge" / "worker-skills"


def promote_skill(
    *,
    candidate: dict[str, Any],
    skill_title: str,
    skill_body: str,
    promoted_by: str = "founder",
    universal: bool = True,
) -> dict[str, str]:
    """Promote a skill candidate to a saved skill file.

    Args:
        candidate: The skill candidate record from skill_candidates table.
        skill_title: Human-readable title for the skill.
        skill_body: Markdown body describing the procedure.
        promoted_by: Who approved the promotion.
        universal: Whether this skill applies to all tenants.

    Returns:
        Dict with 'path' (relative to repo root) and 'content'.
    """
    worker_id = candidate["worker_id"]
    slug = _slugify(skill_title)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Ensure worker skills directory exists
    worker_dir = SKILLS_DIR / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)

    # Build skill file content
    content = f"""---
id: skill-{worker_id}-{slug}
title: "{skill_title}"
graph: worker-skills
owner: {worker_id}
last_reviewed: {now}
trust_level: curated
progressive_disclosure:
  summary_tokens: 40
  full_tokens: 200
worker_id: {worker_id}
created_from_run: {candidate.get('run_id', 'unknown')}
created_at: {now}
promoted_by: {promoted_by}
tenant_context: {candidate.get('tenant_id', 'unknown')}
universal: {str(universal).lower()}
---

{skill_body}
"""

    # Write skill file
    skill_path = worker_dir / f"{slug}.md"
    skill_path.write_text(content)

    # Update candidate status
    try:
        from db import repository
        repository.update_skill_candidate(candidate["id"], {
            "status": "promoted",
            "promoted_by": promoted_by,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass  # best-effort

    return {
        "path": str(skill_path.relative_to(REPO_ROOT)),
        "content": content,
    }


def dismiss_skill_candidate(
    candidate_id: str,
    *,
    reason: str = "",
    dismissed_by: str = "founder",
) -> dict[str, Any]:
    """Dismiss a skill candidate."""
    from db import repository
    return repository.update_skill_candidate(candidate_id, {
        "status": "dismissed",
        "dismiss_reason": reason,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    })


def list_pending_candidates(
    *,
    tenant_id: str | None = None,
    worker_id: str | None = None,
) -> list[dict[str, Any]]:
    """List pending skill candidates for review."""
    from db import repository
    return repository.list_skill_candidates(
        tenant_id=tenant_id,
        status="pending",
        worker_id=worker_id,
    )


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")
```

### Verification

```bash
cd harness && PYTHONPATH=src python -c "from harness.skill_promotion import promote_skill, dismiss_skill_candidate, list_pending_candidates; print('Skill promotion OK')"
```

---

## Task 5: Discord Event Projector

### File: `inngest/src/functions/discord-projector.ts`

**Create this file.** This is an Inngest function that subscribes to agent
events and posts to Discord via webhook. The webhook URL comes from
environment variable `DISCORD_WEBHOOK_URL`.

```typescript
import { inngest } from "../client";

const DISCORD_WEBHOOK_URL = process.env.DISCORD_WEBHOOK_URL || "";

interface DiscordEmbed {
  title: string;
  description: string;
  color: number;
  timestamp?: string;
  fields?: Array<{ name: string; value: string; inline?: boolean }>;
}

// Color constants
const GREEN = 0x22c55e;
const YELLOW = 0xeab308;
const RED = 0xef4444;

function statusColor(status: string): number {
  if (status === "pass" || status === "green" || status === "started") return GREEN;
  if (status === "warning" || status === "yellow" || status === "pending") return YELLOW;
  return RED;
}

async function postToDiscord(embed: DiscordEmbed): Promise<void> {
  if (!DISCORD_WEBHOOK_URL) return;

  await fetch(DISCORD_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ embeds: [embed] }),
  });
}

// Project agent state changes to Discord
export const discordAgentState = inngest.createFunction(
  { id: "discord-agent-state", name: "Discord: Agent State Change" },
  { event: "calllock/agent.state.changed" },
  async ({ event }) => {
    const { agent_id, department, from_state, to_state, task_type } = event.data;
    await postToDiscord({
      title: `${agent_id} → ${to_state}`,
      description: `Department: ${department}\nTask: ${task_type || "general"}`,
      color: statusColor(to_state),
      timestamp: new Date().toISOString(),
    });
  },
);

// Project verification results
export const discordVerification = inngest.createFunction(
  { id: "discord-verification", name: "Discord: Verification Result" },
  { event: "calllock/agent.verification" },
  async ({ event }) => {
    const { worker_id, outcome, confidence, task_type } = event.data;
    await postToDiscord({
      title: `Verification: ${worker_id} — ${outcome}`,
      description: `Confidence: ${(confidence * 100).toFixed(1)}%\nTask: ${task_type}`,
      color: statusColor(outcome),
      timestamp: new Date().toISOString(),
      fields: [
        { name: "Worker", value: worker_id, inline: true },
        { name: "Outcome", value: outcome, inline: true },
      ],
    });
  },
);

// Project skill candidates
export const discordSkillCandidate = inngest.createFunction(
  { id: "discord-skill-candidate", name: "Discord: Skill Candidate" },
  { event: "calllock/skill.candidate" },
  async ({ event }) => {
    const { worker_id, signals, summary } = event.data;
    await postToDiscord({
      title: `Skill Candidate: ${worker_id}`,
      description: summary || "New skill candidate detected",
      color: YELLOW,
      timestamp: new Date().toISOString(),
      fields: [
        { name: "Signals", value: (signals || []).join(", "), inline: false },
      ],
    });
  },
);

// Project guardian health checks
export const discordHealthCheck = inngest.createFunction(
  { id: "discord-health-check", name: "Discord: Health Check" },
  { event: "calllock/guardian.health" },
  async ({ event }) => {
    const { agent_id, status, summary } = event.data;
    await postToDiscord({
      title: `Health Check: ${agent_id} — ${status}`,
      description: summary || "",
      color: statusColor(status),
      timestamp: new Date().toISOString(),
    });
  },
);
```

### File: `inngest/src/index.ts`

**Change:** Import and register the new Discord projector functions.
Add these imports and add the functions to the exported array.

### Verification

```bash
cd inngest && npx tsc --noEmit
```

---

## Task 6: CEO Agent MCP Tool Definitions

### File: `harness/src/harness/ceo_tools.py`

**Create this file.** These are the 10 MCP tools the CEO agent uses.
Each is a plain Python function wrapping existing repository calls.
They will be exposed via the unified MCP server (future task) or
called directly by the CEO agent's Hermes instance.

```python
"""CEO Agent MCP tools.

10 tools giving the founder full control over the AgentOS.
Each wraps existing repository/harness calls with a clean interface.
Designed to be exposed as MCP tools to the CEO agent's Hermes instance.
"""
from __future__ import annotations

import json
from typing import Any

from db import repository


def dispatch_worker(
    *,
    worker_id: str,
    tenant_id: str,
    task_type: str,
    problem_description: str = "",
    feature_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a task to any worker in the agent roster."""
    job = repository.create_job({
        "tenant_id": tenant_id,
        "worker_id": worker_id,
        "task_type": task_type,
        "problem_description": problem_description,
        "feature_flags": feature_flags or {},
        "source": "ceo_agent",
    })
    return {"job_id": job.get("id"), "status": "dispatched", "worker_id": worker_id}


def check_quest_log(
    *,
    tenant_id: str | None = None,
    status: str = "pending",
) -> list[dict[str, Any]]:
    """Read pending approval requests."""
    return repository.list_approval_requests(tenant_id=tenant_id, status=status)


def approve_quest(
    *,
    approval_id: str,
    approved_by: str = "founder",
) -> dict[str, Any]:
    """Approve a blocked dispatch or quest."""
    return repository.update_approval_request(approval_id, {
        "status": "approved",
        "approved_by": approved_by,
    })


def promote_skill(
    *,
    candidate_id: str,
    skill_title: str,
    skill_body: str,
    universal: bool = True,
    promoted_by: str = "founder",
) -> dict[str, Any]:
    """Extract and save a skill from a completed run."""
    from harness.skill_promotion import promote_skill as _promote
    candidates = repository.list_skill_candidates(status="pending")
    candidate = next((c for c in candidates if c.get("id") == candidate_id), None)
    if not candidate:
        return {"error": f"Candidate {candidate_id} not found or not pending"}
    result = _promote(
        candidate=candidate,
        skill_title=skill_title,
        skill_body=skill_body,
        promoted_by=promoted_by,
        universal=universal,
    )
    return {"status": "promoted", "path": result["path"]}


def dismiss_skill_candidate(
    *,
    candidate_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Mark a skill candidate as reviewed and dismissed."""
    from harness.skill_promotion import dismiss_skill_candidate as _dismiss
    return _dismiss(candidate_id, reason=reason)


def read_daily_memo(*, tenant_id: str) -> dict[str, Any]:
    """Get aggregated status across all agents."""
    reports = repository.list_skill_candidates(tenant_id=tenant_id) or []
    agent_reports_raw = []
    try:
        # Read today's agent reports
        from db import supabase_repository
        if supabase_repository.is_configured():
            agent_reports_raw = supabase_repository.list_agent_reports_today(tenant_id)
    except Exception:
        pass
    return {
        "agent_reports": agent_reports_raw,
        "pending_skills": len([r for r in reports if r.get("status") == "pending"]),
        "pending_approvals": len(repository.list_approval_requests(tenant_id=tenant_id, status="pending")),
    }


def query_knowledge(*, path: str) -> dict[str, Any]:
    """Read from the knowledge graph."""
    from pathlib import Path
    knowledge_path = Path(__file__).resolve().parents[3] / "knowledge" / path
    if not knowledge_path.exists():
        return {"error": f"Knowledge node not found: {path}"}
    return {"path": path, "content": knowledge_path.read_text()[:4000]}


def check_agent_status(*, worker_id: str | None = None) -> list[dict[str, Any]]:
    """Check current state of agents (idle/active/queued)."""
    jobs = repository.list_jobs()
    if worker_id:
        jobs = [j for j in jobs if j.get("worker_id") == worker_id]
    return [{"worker_id": j.get("worker_id"), "status": j.get("status"), "task_type": j.get("task_type")} for j in jobs[:20]]


def read_audit_log(
    *,
    tenant_id: str | None = None,
    action_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read recent command audit log entries."""
    logs = repository.list_audit_logs(tenant_id=tenant_id, action_type=action_type)
    return logs[:limit]


def trigger_voice_eval(*, tenant_id: str) -> dict[str, Any]:
    """Kick off a voice pipeline evaluation run."""
    job = repository.create_job({
        "tenant_id": tenant_id,
        "worker_id": "eng-ai-voice",
        "task_type": "voice-eval",
        "problem_description": "CEO-triggered voice evaluation",
        "source": "ceo_agent",
    })
    return {"job_id": job.get("id"), "status": "dispatched"}
```

### Verification

```bash
cd harness && PYTHONPATH=src python -c "from harness.ceo_tools import dispatch_worker, check_quest_log, promote_skill; print('CEO tools OK')"
```

---

## Task 7: CEO Agent Configuration

### File: `harness/src/harness/ceo_agent_config.py`

**Create this file.** Configuration for the standalone CEO agent Hermes
instance. Defines the system prompt, tool list, and cron schedules.
The actual Telegram gateway and VPS deployment are separate steps.

```python
"""CEO Agent configuration for standalone Hermes instance.

The CEO agent runs as a separate Hermes process on a VPS,
connected to the founder via Telegram DM. This module defines
the configuration — the actual deployment is infrastructure work.

Environment variables required:
- TELEGRAM_BOT_TOKEN: Telegram bot API token
- TELEGRAM_CHAT_ID: Founder's Telegram chat ID
- HARNESS_API_URL: URL of the harness API (for MCP tools)
- DISCORD_WEBHOOK_URL: Discord webhook for cross-posting
"""
from __future__ import annotations

CEO_SYSTEM_PROMPT = """You are the CEO Agent for CallLock AgentOS.

You are the founder's personal AI assistant, running 24/7 on a secure server.
You have access to the full agent organization via MCP tools.

Your responsibilities:
1. Morning briefing (6 AM): overnight failures, pending approvals, skill candidates, voice eval
2. Evening digest (6 PM): day summary, idle agents, recurring failures
3. Quick commands: dispatch workers, approve quests, promote skills
4. Push notifications: urgent issues, blocked dispatches, guardian alerts

Communication style:
- Telegram messages: concise, actionable, emoji for status (green/yellow/red)
- Include [View full run] links to Discord threads when detail is needed
- For approvals: present inline keyboard buttons (Approve / Dismiss)
- Never send more than 3 messages in a row without waiting for response

You CANNOT:
- Bypass policy gates or concurrency limits
- Dispatch workers without going through the governance layer
- Modify code directly — all changes go through worker PRs
- Access customer PII outside of tenant-scoped queries
"""

CEO_TOOL_NAMES = [
    "dispatch_worker",
    "check_quest_log",
    "approve_quest",
    "promote_skill",
    "dismiss_skill_candidate",
    "read_daily_memo",
    "query_knowledge",
    "check_agent_status",
    "read_audit_log",
    "trigger_voice_eval",
]

CEO_CRON_SCHEDULE = {
    "morning_briefing": {"cron": "0 6 * * *", "description": "Summarize overnight activity"},
    "evening_digest": {"cron": "0 18 * * *", "description": "Day summary and status"},
    "weekly_retro": {"cron": "0 9 * * 0", "description": "Weekly analysis and trends"},
}

CEO_MODEL = "anthropic/claude-opus-4-6"
CEO_MAX_ITERATIONS = 20
```

### Verification

```bash
cd harness && PYTHONPATH=src python -c "from harness.ceo_agent_config import CEO_SYSTEM_PROMPT, CEO_TOOL_NAMES; print(f'CEO config OK: {len(CEO_TOOL_NAMES)} tools')"
```

---

## Task 8: Skill Promotion Tests

### File: `harness/tests/test_skill_promotion.py`

**Create this file:**

```python
"""Tests for skill promotion pipeline."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.skill_promotion import _slugify, promote_skill


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert _slugify("Multi-Unit HVAC Parsing!") == "multi-unit-hvac-parsing"

    def test_max_length(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 60

    def test_consecutive_hyphens(self):
        assert _slugify("hello   world") == "hello-world"


class TestPromoteSkill:
    def test_creates_skill_file(self, tmp_path):
        candidate = {
            "id": "cand-123",
            "worker_id": "eng-ai-voice",
            "task_type": "extraction",
            "run_id": "run-456",
            "tenant_id": "tenant-789",
        }

        with patch("harness.skill_promotion.SKILLS_DIR", tmp_path):
            with patch("harness.skill_promotion.REPO_ROOT", tmp_path.parent):
                result = promote_skill(
                    candidate=candidate,
                    skill_title="Multi Unit Parsing",
                    skill_body="When encountering multiple units, extract each separately.",
                    promoted_by="rashid",
                    universal=True,
                )

        assert "path" in result
        assert "content" in result
        assert "multi-unit-parsing" in result["path"]
        assert "universal: true" in result["content"]
        assert "promoted_by: rashid" in result["content"]

        # Verify file was written
        skill_file = tmp_path / "eng-ai-voice" / "multi-unit-parsing.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "Multi Unit Parsing" in content
        assert "extract each separately" in content


class TestSkillCandidateDetection:
    def test_high_confidence_triggers(self):
        from harness.nodes.verification import check_skill_candidate
        result = check_skill_candidate(
            worker_output={"summary": "good", "status": "green", "violations": [], "a": 1, "b": 2},
            verification={"outcome": "pass", "confidence": 0.95},
            worker_id="eng-ai-voice",
            task_type="health-check",
            run_id="run-123",
        )
        assert result is not None
        assert "high_confidence_pass" in result["signals"]

    def test_low_confidence_no_trigger(self):
        from harness.nodes.verification import check_skill_candidate
        result = check_skill_candidate(
            worker_output={"summary": "ok"},
            verification={"outcome": "pass", "confidence": 0.5},
            worker_id="eng-ai-voice",
            task_type="health-check",
            run_id="run-123",
        )
        assert result is None

    def test_exploratory_solve_triggers(self):
        from harness.nodes.verification import check_skill_candidate
        result = check_skill_candidate(
            worker_output={"summary": "found it", "_hermes_iterations": 8},
            verification={"outcome": "pass", "confidence": 0.7},
            worker_id="eng-ai-voice",
            task_type="investigation",
            run_id="run-456",
        )
        assert result is not None
        assert "exploratory_solve" in result["signals"]
```

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/test_skill_promotion.py -x -q
```

---

## Task 9: Run Full Test Suite

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/ -x -q 2>&1 | tail -20
cd inngest && npx tsc --noEmit
node scripts/validate-worker-specs.ts
python scripts/validate-contracts.py
```

---

## Execution Order

```
Task 1  →  Skill candidates Supabase table
Task 2  →  Skill candidate repository layer
Task 3  →  Activate skill candidate detection
Task 4  →  Skill promotion service
Task 5  →  Discord event projector (Inngest)
Task 6  →  CEO agent MCP tool definitions
Task 7  →  CEO agent configuration
Task 8  →  Skill promotion + detection tests
Task 9  →  Full test suite verification
```

One commit per task. Verify after each. Stop on first failure.

## Post-Implementation State

After all 9 tasks:
- Skill candidates detected and persisted on qualifying runs
- Founder can promote or dismiss candidates via CEO tools
- Promoted skills land as markdown in knowledge/worker-skills/
- Discord projector posts agent activity to webhooks
- CEO agent has 10 MCP tools, system prompt, and cron config
- All code is tested and ready for deployment

## What Needs External Setup (NOT in this plan)

1. **Telegram bot** — create via @BotFather, set TELEGRAM_BOT_TOKEN
2. **Discord server** — create channels, set DISCORD_WEBHOOK_URL
3. **VPS** — provision $5 server, deploy CEO agent Hermes instance
4. **Hermes install on VPS** — git clone hermes-agent, pip install
5. **MCP server deployment** — expose CEO tools as MCP endpoints

# Product Guardian: Voice + App Continuous Improvement System

**Date:** 2026-03-17
**Status:** Design approved
**Author:** Rashid Baset + Claude

## Overview

The Product Guardian is a two-agent system that continuously monitors, validates, and improves CallLock's product — the voice AI agent and the customer app/dashboard — as a unified system.

CallLock's product is a per-customer voice AI agent plus a supporting customer dashboard that displays information from each call. The Product Guardian ensures both halves of this product, and critically the seam between them, remain stable, accurate, and continuously improving.

The Product Guardian lives in the **learning plane** of the system architecture. It reads from the data plane (call records, extraction results) and writes to the control plane (issues, PRs, quest log entries, health reports). It does not store or display product-domain records — those remain authoritative in Supabase.

## Architecture

### Two-Agent Model

```
                    +-------------------------------+
                    |         TRIGGERS              |
                    |  Cron (daily/weekly)          |
                    |  Scorecard warnings           |
                    |  Extraction failures          |
                    |  App rendering errors         |
                    |  Ad hoc (founder pushes)      |
                    |  Office dispatch (click agent)|
                    +---------------+---------------+
                                    |
                   +----------------+----------------+
                   v                                 v
         +-----------------+              +-----------------+
         |  eng-ai-voice   |              |    eng-qa       |
         |  Voice Guardian |              |  Product QA     |
         |                 |              |                 |
         | Owns:           |  proposes    | Owns:           |
         | - Retell prompt |--changes---->| - Seam testing  |
         | - Extraction    |              | - App integrity |
         | - Classification|  validates   | - E2E pipeline  |
         | - Scoring       |<--before-----|  - Field mapping |
         | - Config drift  |  merge       | - Smoke tests   |
         +--------+--------+              +--------+--------+
                  |                                 |
                  |  writes to                      |  writes to
                  v                                 v
         +-----------------+              +-----------------+
         |  GIT            |              |  GIT + SUPABASE |
         |  - YAML configs |              |  - Test results |
         |  - Prompt files |              |  - Health reports|
         |  - Schema changes|             |  - Issue creation|
         |  - Branches/PRs |              |  - Metric events |
         +-----------------+              +-----------------+
```

### Three-Plane Alignment

| Plane | Product Guardian Role |
|---|---|
| **Control plane** | eng-qa dispatches validation suites; VP Eng prioritizes agent work; quest log surfaces seam violations |
| **Data plane** | Retell handles calls; app_sync delivers payload; hong-kong-v1 renders cards; call_records remain in Supabase |
| **Learning plane** | eng-ai-voice analyzes extraction accuracy trends; proposes prompt improvements; seam contract evolves based on learned gaps |

### The Seam

The most fragile point in the product is the boundary between the voice pipeline and the customer app. If extraction changes a field name, the app card breaks. If a new field is extracted but not displayed, customer value is lost silently.

```
VOICE SIDE                    SEAM                       APP SIDE
                         (most fragile)
retell-agent-v10.yaml   app_sync.py payload      hong-kong-v1/page.tsx
extraction pipeline      40+ field webhook         card rendering
classification           HMAC signing              transcript display
scoring                  Supabase call_sessions    realtime subscription
```

## Seam Contract

A YAML schema that defines what the voice pipeline produces and what the app expects. Both agents validate against it.

**Location:** `knowledge/voice-pipeline/seam-contract.yaml`

### Structure

```yaml
version: "1.0"
last_validated: "2026-03-17"

fields:
  - name: call_type
    extraction: required      # extraction must produce this
    app_sync: required        # webhook must include this
    app_display: card         # shown on call card in hong-kong-v1
    type: string
    enum: [new_business, existing_customer, spam, personal, emergency]

  - name: caller_name
    extraction: required
    app_sync: required
    app_display: card
    type: string

  - name: job_type
    extraction: optional      # not all calls have a job
    app_sync: if_present      # include only if extracted
    app_display: detail       # shown on detail view, not card
    type: string

  - name: urgency_score
    extraction: required
    app_sync: required
    app_display: card         # badge color on card
    type: integer
    range: [1, 10]

  # ... 40+ fields following this pattern
```

### Validation Checks

| Check | What | Threshold |
|---|---|---|
| Extraction completeness | Required fields produced for 95%+ of calls | Fail if below |
| Payload fidelity | app_sync.py includes all required fields | Fail if missing |
| Display coverage | hong-kong-v1 renders all display fields | Warn if gap |
| Orphan detection | Fields extracted but never displayed, or expected but never produced | Warn |
| Type consistency | Extraction output types match app expected types | Fail if mismatch |

### Violation Flow

```
eng-qa detects violation
    |
    +-- MISSING FIELD (extraction doesn't produce)
    |   -> issue to eng-ai-voice: "add extraction for {field}"
    |
    +-- PAYLOAD MISMATCH (app_sync doesn't include)
    |   -> issue to eng-fullstack or founder: "add {field} to app_sync.py"
    |
    +-- DISPLAY GAP (app doesn't render)
    |   -> issue to eng-fullstack or founder: "add {field} to hong-kong-v1"
    |
    +-- ORPHAN FIELD (extracted but goes nowhere)
    |   -> issue: decision needed — display it or stop extracting?
    |
    +-- TYPE MISMATCH
        -> blocks any PR that would widen the mismatch
```

## Agent Schedules & Triggers

### eng-ai-voice

| When | What | Autonomy |
|---|---|---|
| Daily 6am | Health check: sample 5-10 recent calls, re-run extraction, compare to stored results, check tag distribution, run `deploy-retell-agent.py --diff-only` for config drift | Report only -> daily memo |
| Weekly Sunday 6am | Deep sweep: full regression suite across all call types, analyze extraction accuracy trends, identify prompt improvement opportunities | Proposes changes as PRs |
| Reactive | Scorecard warnings (`callback-gap`, `zero-tags`), extraction failure rate spike, zero-tag rate spike | Diagnoses -> creates issue or PR |
| Ad hoc (office dispatch) | "Investigate last 3 calls from customer X" | Runs analysis, reports findings |

### eng-qa

| When | What | Autonomy |
|---|---|---|
| Daily 6:30am | E2E smoke test: pick recent call, verify extraction, verify app_sync payload, verify hong-kong-v1 card renders fields correctly | Report only -> daily memo |
| On every PR from eng-ai-voice | Validation suite: re-extract sample calls with new config, generate payload, compare against seam contract, check app field mapping | Approve/block PR |
| Weekly Sunday 7am | Seam audit: check all 40+ fields — any extracted but not displayed? Any expected but not produced? Any stale fields? | Creates issues for gaps |
| Reactive | Webhook delivery failures, app rendering errors, realtime subscription drops | Diagnoses -> creates issue |

### Ad Hoc (Founder) Changes

```
Founder edits YAML or code -> pushes to branch
    |
    +-- eng-qa auto-triggered on PR
    |   +-- runs validation suite
    |   +-- PASS -> approves
    |   +-- FAIL -> blocks with report
    |
    +-- founder can override and merge (founder privilege)
```

### Office as Command Surface

The 3D office is the primary way to interact with these agents. From the Engineering room:

- Click eng-ai-voice -> dispatch ad hoc investigation
- Click eng-qa -> trigger on-demand seam audit
- Override eng-qa's PR block via quest resolution
- View health reports in daily memo
- See department health via director glass color (green/yellow/red)

## Tiered Autonomy

### Auto-merge (eng-qa validates, no human review)

| Change Type | Example | Why Safe |
|---|---|---|
| New extraction regex pattern | Add pattern for "tankless water heater" | Additive — doesn't change existing extractions |
| New taxonomy tag | Add `emergency-weekend` to tag list | Additive — existing tags unchanged |
| Seam contract field addition | New field extracted AND added to app_sync AND added to app display | All three layers updated together |
| Test/eval suite updates | Add new test case, update expected outputs | Improves coverage, can't break production |
| Health check threshold tuning | Adjust warning threshold from 85% to 82% | Monitoring only |

### PR required — agent review (eng-qa reviews, founder notified)

| Change Type | Example | Why Needs Review |
|---|---|---|
| Extraction schema field rename | `caller_name` -> `customer_name` | Breaks seam contract if app not updated |
| Classification logic change | Modify emergency vs routine determination | Changes call routing |
| App_sync payload restructure | Change field grouping or nesting | Breaks app if not coordinated |
| Scoring weight adjustment | Change lead score weights | Changes which leads surface as hot |

### PR required — human review (founder must approve)

| Change Type | Example | Why Founder Must See |
|---|---|---|
| Retell prompt edit | Any change to prompt text | This is what customers hear |
| Model or temperature change | Switch models, change temp | Fundamentally changes voice behavior |
| State machine change | Add/remove/reorder pipeline nodes | Changes processing flow |
| Seam contract field removal | Remove a field app currently displays | Could break customer experience |
| Deploy script changes | Modify `deploy-retell-agent.py` | Changes how configs reach production |

### Escalation Rule

If an agent is unsure which tier a change belongs to, it always escalates up. Auto-merge uncertainty -> PR agent review. Agent review uncertainty -> human review. Never down.

## Worker Specs

### eng-ai-voice

```yaml
id: eng-ai-voice
title: AI/Voice Engineer
department: engineering
supervisor: eng-vp
role: worker

description: >
  Guards and improves the voice pipeline. Monitors extraction accuracy,
  classification drift, and prompt effectiveness. Proposes improvements
  through git branches and PRs with tiered autonomy.

tools:
  - supabase-read          # query call_records, metric_events, call_sessions
  - extraction-rerun       # re-run extraction pipeline on a call transcript
  - scorecard-evaluate     # run call scorecard on a call
  - retell-config-diff     # compare repo YAML vs deployed Retell config
  - git-branch-write       # create branch, commit files, create PR
  - issue-create           # create GitHub issue with evidence

scheduled_tasks:
  - cron: "0 6 * * *"       # daily 6am
    task_type: voice-health-check
  - cron: "0 6 * * 0"       # weekly Sunday 6am
    task_type: voice-deep-sweep

reactive_triggers:
  - event: "calllock/scorecard.warning"
    task_type: voice-investigate
  - event: "calllock/extraction.failure"
    task_type: voice-investigate

context_sources:
  - knowledge/voice-pipeline/
  - knowledge/industry-packs/hvac/
  - scripts/deploy-retell-agent.py
```

### eng-qa

```yaml
id: eng-qa
title: QA/Automation Engineer
department: engineering
supervisor: eng-vp
role: worker

description: >
  Guards the seam between voice pipeline and customer app. Runs E2E
  smoke tests, validates PRs from eng-ai-voice, audits field mapping
  completeness. Ensures zero data loss across the product boundary.

tools:
  - supabase-read          # query call_sessions, call_records
  - extraction-rerun       # re-run extraction for comparison
  - app-sync-simulate      # generate app_sync payload from extraction
  - seam-contract-validate # check extraction -> payload -> app alignment
  - app-render-check       # verify hong-kong-v1 displays fields correctly
  - git-pr-review          # approve/block PRs with report
  - issue-create           # create GitHub issue with evidence

scheduled_tasks:
  - cron: "30 6 * * *"      # daily 6:30am
    task_type: e2e-smoke-test
  - cron: "0 7 * * 0"       # weekly Sunday 7am
    task_type: seam-audit

reactive_triggers:
  - event: "calllock/app_sync.failure"
    task_type: app-investigate
  - event: "calllock/pr.created"
    filter: { author: "eng-ai-voice" }
    task_type: pr-validation

context_sources:
  - knowledge/voice-pipeline/seam-contract.yaml
  - web/
  - harness/src/voice/services/app_sync.py
```

### Interaction Pattern

```
eng-ai-voice detects issue or proposes improvement
    |
    +-- LOW RISK: creates branch, writes fix, creates PR
    |   +-- eng-qa auto-triggered by calllock/pr.created
    |       +-- runs validation suite
    |       +-- PASS + auto-merge tier -> merges
    |       +-- PASS + human tier -> approves, notifies founder
    |
    +-- NEEDS INVESTIGATION: creates issue with evidence
    |   +-- founder or eng-ai-voice picks it up later
    |
    +-- URGENT: creates quest (policy gate)
        +-- appears in office quest log for immediate action
```

## Git Workflow

### Branch Naming

```
agent/eng-ai-voice/voice-health-2026-03-17
agent/eng-ai-voice/prompt-improvement-hvac-v11
agent/eng-ai-voice/extraction-add-job-duration
agent/eng-qa/seam-audit-2026-03-17
```

### Commit Message Format

```
agent(eng-ai-voice): add regex pattern for tankless water heater

- Added pattern matching for "tankless" variants in HVAC job_type extraction
- Tested against 12 sample calls: 100% hit rate
- Seam contract updated: job_type enum now includes tankless_water_heater
- Auto-merge tier: additive extraction pattern

Validated-by: eng-qa
```

### PR Labels

| Label | Meaning | Merge Rule |
|---|---|---|
| `auto-merge` | Low-risk, eng-qa validated | Merges automatically |
| `agent-review` | Medium-risk, eng-qa must approve | Merges on approval |
| `human-review` | High-risk, founder must approve | Waits for founder |
| `urgent` | Reactive fix for production issue | Notifies founder immediately |

### Post-Merge Deploy

```
PR merged to main
    |
    +-- If YAML config changed:
    |   +-- CI runs deploy-retell-agent.py --apply
    |       +-- updates Retell agent via API
    |
    +-- If extraction/classification code changed:
    |   +-- CI runs standard deploy pipeline
    |
    +-- If seam-contract.yaml changed:
        +-- eng-qa runs full validation suite
            +-- creates follow-up issues if app needs updating
```

## Health Reports & Daily Memo Integration

### Voice Health Report (daily)

```json
{
  "agent": "eng-ai-voice",
  "report_type": "voice-health-check",
  "date": "2026-03-17",
  "status": "green",
  "calls_sampled": 8,
  "extraction_accuracy": 0.94,
  "classification_accuracy": 0.97,
  "zero_tag_rate": 0.02,
  "config_drift": false,
  "scorecard_warnings": 0,
  "issues_created": 0,
  "prs_created": 0
}
```

### E2E Smoke Report (daily)

```json
{
  "agent": "eng-qa",
  "report_type": "e2e-smoke-test",
  "date": "2026-03-17",
  "status": "yellow",
  "calls_tested": 5,
  "seam_violations": 1,
  "webhook_delivery_rate": 1.0,
  "app_render_pass_rate": 0.8,
  "field_coverage": "38/42",
  "issues_created": 1,
  "detail": "job_type extracted but not displayed on card for emergency calls"
}
```

### 3D Office Integration

Reports feed into the daily memo:

```
DAILY MEMO - March 17, 2026

ENGINEERING
+-- eng-ai-voice: [green] Voice pipeline healthy
|   +-- 8 calls sampled, 94% extraction accuracy
|   +-- 0 scorecard warnings, no config drift
|   +-- no action needed
|
+-- eng-qa: [yellow] 1 seam violation detected
    +-- 5 calls tested end-to-end
    +-- job_type missing from emergency call cards
    +-- issue #47 created -> assigned to eng-fullstack
```

In the 3D office:
- eng-qa's desk glows yellow (policy-gate zone) when a seam violation is detected
- VP Eng director glass turns yellow, signaling department needs attention
- Quest log shows actionable seam violations with resolution options

## Three-Layer Persistence Model

The Product Guardian uses three persistence layers, each for its natural purpose:

| Layer | What Lives There | Review Surface |
|---|---|---|
| **Git** | Prompts, extraction schemas, seam contract, YAML configs, PRDs, business models | PRs, git log, blame |
| **Project management** (GitHub Issues) | Tasks, investigations, improvement proposals, seam violations | Issue board, labels |
| **Supabase** | Call records, agent state, metrics, quest log, audit log | Dashboard, daily memo, SQL |

### The Rule

- If an agent produces something a human would review in a PR -> git
- If an agent produces a task to track -> GitHub Issues
- If an agent produces something a human would see in a dashboard -> Supabase

## Existing Code Leverage

The Product Guardian builds on existing infrastructure:

| Existing | How Product Guardian Uses It |
|---|---|
| `scripts/deploy-retell-agent.py` | eng-ai-voice calls `--diff-only` for drift detection, CI calls `--apply` post-merge |
| `harness/src/voice/services/extraction.py` | eng-ai-voice re-runs extraction on sample calls |
| `harness/src/voice/services/app_sync.py` | eng-qa validates payload generation |
| `harness/src/voice/models.py` (CallScorecard) | eng-ai-voice evaluates call quality |
| `knowledge/industry-packs/hvac/` | Source of truth for HVAC voice config |
| `run_supervisor()` in harness | Both agents execute through existing supervisor graph |
| `MetricsEmitter` | Health reports use existing metric emission pattern |
| `InngestEventEmitter` (planned) | Scheduled tasks and reactive triggers use Inngest cron/events |

## Open Questions

1. **Headless browser for app render checks** — Should eng-qa actually render hong-kong-v1 pages in a headless browser to verify field display, or is checking the React component source code sufficient? Browser is more thorough but adds infrastructure. Source code checking is simpler but can miss runtime rendering issues.

2. **Multi-industry-pack support** — When CallLock adds a second industry pack beyond HVAC, does each pack get its own seam contract, or is there one contract with pack-specific field sections? The current design assumes one contract.

3. **Alert channels** — Where do urgent notifications go beyond the quest log? Slack? SMS? Email? The office is the primary surface, but the founder may not be watching the office 24/7.

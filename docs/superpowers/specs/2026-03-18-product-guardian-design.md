# Product Guardian: Full-Surface Continuous Monitoring & Change Gate

**Date:** 2026-03-18
**Status:** Design approved
**Author:** Rashid Baset + Claude
**Supersedes:** 2026-03-17-product-guardian-design.md (voice + app seam only)

## Implementation Status

| Component | Status | Plan Task | Files |
|---|---|---|---|
| eng-qa → eng-product-qa rename | ✅ Done | Task 1 | `knowledge/worker-specs/eng-product-qa.yaml` |
| Three-contract split | ✅ Done | Task 2 | `voice-contract.yaml`, `app-contract.yaml`, `seam-contract.yaml` v2.0 |
| eng-app worker spec | ✅ Done | Task 3 | `knowledge/worker-specs/eng-app.yaml` |
| agent_reports table | ✅ Done | Task 5 | `supabase/migrations/052_agent_reports.sql` |
| guardian_overrides table | ✅ Done | Task 6 | `supabase/migrations/053_guardian_overrides.sql` |
| Guardian dispatch event | ✅ Done | Task 7 | `inngest/src/functions/guardian-dispatch.ts` |
| Guardian watchdog | ✅ Done | Task 8 | `inngest/src/functions/guardian-watchdog.ts` |
| Contract validation CI | ✅ Done | Tasks 9-10 | `scripts/validate-contracts.py`, `.github/workflows/contract-validate.yml` |
| PR gate workflow | ✅ Done | Task 11 | `.github/workflows/product-guardian.yml` |
| Visual regression infra | ✅ Done | Task 12 | `knowledge/voice-pipeline/app-baselines/` |


## Overview

The Product Guardian is a three-agent system under VP Engineering that continuously monitors, validates, and gates changes across the entire CallLock product: the voice AI pipeline, the customer app, and the seams between them.

It expands the original two-agent design (eng-ai-voice + eng-qa) to cover the full product surface with a new agent (eng-app) and a renamed cross-cutting coordinator (eng-product-qa). The system uses a **contract-first** approach — three YAML contracts define what the voice pipeline produces, what the app renders, and how they align. No change ships without updating the relevant contracts.

The Product Guardian lives in the **learning plane** of the system architecture. It reads from the data plane (call records, extraction results, app state) and writes to the control plane (issues, PRs, quest log entries, health reports). It does not store or display product-domain records — those remain authoritative in Supabase.

## Migration from v1 Spec

This spec renames `eng-qa` → `eng-product-qa` and restructures the seam contract. The following changes must be applied to existing files:

| File | Change |
|---|---|
| `knowledge/worker-specs/eng-qa.yaml` | Rename to `eng-product-qa.yaml`, update `worker_id` to `eng-product-qa` |
| `knowledge/worker-specs/eng-ai-voice.yaml` | Update `git_workflow.validated_by` from `eng-qa` to `eng-product-qa` |
| `docs/superpowers/specs/2026-03-17-corporate-hierarchy-agent-roster.md` | Replace `eng-qa` with `eng-product-qa` in roster, hierarchy tree, and status table |
| `docs/superpowers/specs/2026-03-18-llm-tool-assignments.md` | Replace `eng-qa` with `eng-product-qa` in Engineering table row |
| `knowledge/voice-pipeline/seam-contract.yaml` | Update header comment (`eng-qa` → `eng-product-qa`), restructure into three contracts (see Contract Migration below) |

**Note:** These migration changes are applied during implementation, not at spec-approval time. The on-disk files (`eng-qa.yaml`, `eng-ai-voice.yaml`, `seam-contract.yaml`) currently still reference `eng-qa`. The implementation plan will include a migration step as the first task.

### Contract Migration

The existing `seam-contract.yaml` (v1.0, 31 active fields) is split into three contracts:

1. **voice-contract.yaml** — derived from fields where `extraction != not_applicable` in the current seam contract. Field names are preserved exactly as-is (e.g., `customer_name`, `urgency_tier`, `caller_type`).
2. **app-contract.yaml** — derived from fields where `app_display != not_shown`. Defines pages and must_render elements based on the current card/detail display rules.
3. **seam-contract.yaml v2.0** — retains the same file path but is restructured from a flat `fields` list to a `field_mappings` list that cross-references voice-contract and app-contract. The existing `validation_rules` section moves into the `invariants` section.

The current `reserved_fields` section stays in the voice contract only.

## Architecture

### Three-Agent Model

```
                    +-------------------------------+
                    |         TRIGGERS              |
                    |  Cron (daily/weekly)          |
                    |  PRs from Product or Eng      |
                    |  Reactive events              |
                    |  Ad hoc (founder dispatch)    |
                    +---------------+---------------+
                                    |
              +---------------------+---------------------+
              v                     v                     v
    +-----------------+   +-----------------+   +-------------------+
    |  eng-ai-voice   |   |    eng-app      |   | eng-product-qa    |
    |  Voice Guardian |   |  App Guardian   |   | Product QA        |
    |                 |   |                 |   |                   |
    | Owns:           |   | Owns:           |   | Owns:             |
    | - Extraction    |   | - Page render   |   | - Seam contracts  |
    | - Classification|   | - Realtime subs |   | - Cross-surface   |
    | - Scoring       |   | - Data display  |   |   validation      |
    | - Retell config |   | - UX integrity  |   | - Change gate     |
    | - Voice contract|   | - App contract  |   | - E2E scenarios   |
    |                 |   |                 |   | - Data integrity  |
    +---------+-------+   +--------+--------+   +---------+---------+
              |                    |                       |
              v                    v                       v
        Voice Contract       App Contract           Seam Contract
        (extraction          (what renders          (alignment
         fields, enums,       in browser,            across voice
         thresholds)          realtime behavior)     and app)
```

**Key principle:** Each agent validates against its own contract. eng-product-qa validates the alignment across contracts. No agent owns another agent's surface — they collaborate through contracts.

### Three-Plane Alignment

| Plane | Product Guardian Role |
|---|---|
| **Control plane** | eng-product-qa gates PRs; VP Eng prioritizes agent work; quest log surfaces violations |
| **Data plane** | Retell handles calls; app_sync delivers payload; CallLock App renders cards; call_records remain in Supabase |
| **Learning plane** | eng-ai-voice analyzes extraction trends; eng-app tracks rendering reliability; seam contracts evolve based on learned gaps |

## Contract System

Three YAML contracts, each owned by one agent, stored in `knowledge/voice-pipeline/`.

### Voice Contract

Owned by eng-ai-voice. Defines what the voice pipeline **produces**.

```yaml
# knowledge/voice-pipeline/voice-contract.yaml
version: "1.0"
owner: eng-ai-voice
industry_pack: hvac

fields:
  # Field names match the existing seam-contract.yaml exactly.
  # Only extraction-side fields are shown here (extraction != not_applicable).

  - name: customer_name
    extraction: required
    type: string
    fallback: "Unknown"

  - name: customer_phone
    extraction: required
    type: string

  - name: urgency_tier
    extraction: required
    type: string
    enum: [emergency, urgent, routine, estimate]
    accuracy_threshold: 0.97

  - name: caller_type
    extraction: required
    type: string
    enum: [residential, commercial, unknown, vendor, job_applicant, spam]

  - name: problem_description
    extraction: required
    type: string

  - name: safety_emergency
    extraction: required
    type: boolean
    default: false

  - name: appointment_booked
    extraction: required
    type: boolean
    default: false

  # ... remaining 24 extraction-produced fields from seam-contract.yaml v1.0
  # Full list: service_address, dashboard_urgency, primary_intent, route,
  # end_call_reason, hvac_issue_type, equipment_type, equipment_brand,
  # equipment_age, appointment_date_time, callback_type, problem_duration,
  # revenue_tier, revenue_estimate, tag_categories, tags, quality_score,
  # scorecard_warnings, sales_lead_notes, call_summary

retell_config:
  model_constraints: [temperature, max_tokens]
  prompt_hash: "sha256:..."  # drift detection baseline
```

### App Contract

Owned by eng-app. Defines what the app **must render and how it must behave**.

```yaml
# knowledge/voice-pipeline/app-contract.yaml
version: "1.0"
owner: eng-app

pages:
  - path: /calls
    must_render:
      - element: call-card
        fields: [customer_name, customer_phone, problem_description, urgency_tier, safety_emergency, appointment_booked, callback_type, created_at]
        realtime: true  # must appear without refresh
      - element: call-detail
        fields: [transcript, service_address, hvac_issue_type, equipment_type, equipment_brand, equipment_age, appointment_date_time, end_call_reason]
        realtime: false  # detail view loads on click

  - path: /overview
    must_render:
      - element: stats-summary
        fields: [total_calls, hot_leads, callback_rate]

behaviors:
  - name: realtime-card-appearance
    trigger: "new call completed"
    expected: "card appears in /calls within 5 seconds without page refresh"

  - name: card-click-detail
    trigger: "user clicks call card"
    expected: "detail view opens with all detail fields populated"
```

### Seam Contract

Owned by eng-product-qa. Defines the **alignment rules** between voice and app contracts.

```yaml
# knowledge/voice-pipeline/seam-contract.yaml
version: "2.0"
owner: eng-product-qa

field_mappings:
  # Field names match seam-contract.yaml v1.0 exactly.
  - voice_field: customer_name
    supabase: jsonb  # extracted_fields.customer_name
    app_element: call-card
    app_display: card
    required_chain: [extraction, app_sync, render]

  - voice_field: urgency_tier
    supabase: column  # call_records.urgency_tier
    app_element: call-card
    app_display: card
    required_chain: [extraction, app_sync, render]

  - voice_field: problem_description
    supabase: jsonb  # extracted_fields.problem_description
    app_element: call-card
    app_display: card
    required_chain: [extraction, app_sync, render]

  - voice_field: transcript
    supabase: column  # call_records.transcript
    app_element: call-detail
    app_display: detail
    required_chain: [app_sync, render]  # not from extraction — from Retell directly

  # ... remaining 27 active fields mapped end-to-end
  # Full field list derived from seam-contract.yaml v1.0 fields section

invariants:
  - name: no-orphan-extraction
    rule: "every field in voice-contract with extraction:required must appear in at least one field_mapping"

  - name: no-orphan-display
    rule: "every field in app-contract must_render must have a source in field_mappings"

  - name: no-broken-chain
    rule: "every field_mapping must have all links in required_chain passing"
```

### Validation Checks

| Check | Owner | Threshold |
|---|---|---|
| Extraction completeness — required fields produced for 95%+ of calls | eng-ai-voice | Fail if below |
| Page render — all must_render fields visible in headless browser | eng-app | Fail if missing |
| Realtime delivery — new calls appear in app within 5s | eng-app | Fail if timeout |
| Data accuracy — app display matches Supabase records | eng-app | Fail if mismatch |
| No orphan extraction — extracted fields have a mapping | eng-product-qa | Warn |
| No orphan display — displayed fields have a source | eng-product-qa | Warn |
| No broken chain — every mapping has all links passing | eng-product-qa | Fail |
| Type consistency — extraction types match app expected types | eng-product-qa | Fail |

### Violation Flow

```
eng-product-qa detects violation
    |
    +-- MISSING EXTRACTION (voice-contract field not produced)
    |   → issue to eng-ai-voice: "add extraction for {field}"
    |
    +-- PAYLOAD MISMATCH (app_sync doesn't include field)
    |   → issue to eng-fullstack or founder: "add {field} to app_sync.py"
    |
    +-- RENDER GAP (app doesn't display field)
    |   → issue to eng-fullstack or founder: "add {field} to CallLock App"
    |
    +-- ORPHAN FIELD (extracted but goes nowhere)
    |   → issue: decision needed — display it or stop extracting?
    |
    +-- TYPE MISMATCH
    |   → blocks any PR that would widen the mismatch
    |
    +-- DATA INCONSISTENCY (app shows stale/wrong data)
        → issue to eng-app to investigate; eng-product-qa escalates if RLS
```

## Worker Specs

### eng-ai-voice (existing, unchanged)

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
  - supabase-read
  - extraction-rerun
  - scorecard-evaluate
  - retell-config-diff
  - git-branch-write
  - issue-create

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
  - knowledge/voice-pipeline/voice-contract.yaml
  - knowledge/industry-packs/hvac/
  - scripts/deploy-retell-agent.py
```

### eng-app (new)

**Note:** The YAML blocks in this spec are abbreviated for readability. The full worker spec files must follow the `schema_version: 1.1` JSON format established in `eng-qa.yaml` and `eng-ai-voice.yaml`, including `mission`, `scope.can_do`, `scope.cannot_do`, `inputs`, `outputs`, `success_metrics`, `approval_boundaries`, `validation_checks`, `dependencies`, and `interaction_with` fields.

```yaml
id: eng-app
title: App Guardian Engineer
department: engineering
supervisor: eng-vp
role: worker

description: >
  Guards the CallLock App. Runs headless browser checks to verify
  pages render correctly, realtime subscriptions deliver updates,
  and data displayed matches what's in Supabase. Validates against
  the app contract.

tools:
  - supabase-read
  - headless-browser
  - app-contract-validate
  - git-pr-review
  - issue-create

scheduled_tasks:
  - cron: "30 6 * * *"       # daily 6:30am
    task_type: app-health-check
  - cron: "30 6 * * 0"       # weekly Sunday 6:30am
    task_type: app-deep-sweep

reactive_triggers:
  # eng-app only fires on dispatch from eng-product-qa for PR validation.
  # It does NOT independently listen for calllock/pr.created — eng-product-qa
  # is the sole entry point for all PR gating to avoid duplicate/conflicting reviews.
  - event: "calllock/guardian.dispatch"
    filter: { target: "eng-app" }
    task_type: app-pr-validation
  - event: "calllock/app.error"
    task_type: app-investigate
  - event: "calllock/realtime.drop"
    task_type: app-investigate

context_sources:
  - knowledge/voice-pipeline/app-contract.yaml
  - web/src/lib/transforms.ts
  - web/src/types/call.ts
  - web/src/components/mail/mail-display.tsx
  - web/src/components/mail/mail-list.tsx
```

### Headless Browser Check Flow

For each page in the app contract:

```
1. Load page in headless browser (Playwright)
2. Wait for realtime subscription to connect
3. For each must_render element:
   a. Query Supabase for the source data
   b. Find the element in the DOM
   c. Verify each field is present and matches Supabase
   d. Screenshot the element (evidence for reports)
4. For each behavior:
   a. Simulate the trigger (e.g., insert a test call record)
   b. Wait for expected outcome (e.g., card appears)
   c. Verify within timeout (e.g., 5 seconds)
   d. Screenshot before/after
5. Clean up test data
```

### eng-product-qa (renamed from eng-qa, expanded)

```yaml
id: eng-product-qa
title: Product QA Engineer
department: engineering
supervisor: eng-vp
role: worker

description: >
  Guards product quality across all surfaces. Owns the seam contract
  that maps voice pipeline fields to app rendering. Gates all PRs
  that touch voice or app code. Dispatches surface agents for
  validation via Inngest events. Ensures contract-first discipline.
  Monitors data integrity including tenant isolation.

tools:
  - supabase-read
  - seam-contract-validate
  - extraction-rerun
  - app-sync-simulate
  - git-pr-review
  - issue-create
  - inngest-emit            # emits calllock/guardian.dispatch events

scheduled_tasks:
  - cron: "0 7 * * *"         # daily 7am
    task_type: cross-surface-health
  - cron: "0 7 * * 0"         # weekly Sunday 7am
    task_type: seam-audit

reactive_triggers:
  # eng-product-qa is the SOLE entry point for PR-based change gating.
  # eng-app and eng-ai-voice do NOT independently listen for calllock/pr.created.
  # eng-product-qa dispatches them via calllock/guardian.dispatch events.
  - event: "calllock/pr.created"
    filter:
      paths:
        - "web/**"
        - "knowledge/voice-pipeline/**"
        - "harness/src/voice/**"
        - "scripts/deploy-retell-agent.py"
    task_type: change-gate-review
  - event: "calllock/app_sync.failure"
    task_type: seam-investigate

context_sources:
  - knowledge/voice-pipeline/seam-contract.yaml
  - knowledge/voice-pipeline/voice-contract.yaml
  - knowledge/voice-pipeline/app-contract.yaml

llm_model: codex  # expanded responsibility warrants stronger model than qwen
llm_escalation:
  - condition: "manipulates_production_data"
    model: nanoclaw
  - condition: "multi_client_context"
    model: claude-sonnet
```

### Dispatch Mechanism

eng-product-qa has `role: worker` (not `role: director`). The supervisor graph's `_job_dispatch_node` only processes dispatch requests for directors. Instead, eng-product-qa dispatches surface agents via **Inngest events**:

```
eng-product-qa emits calllock/guardian.dispatch event:
  { "target": "eng-app", "task_type": "app-pr-validation", "pr_id": 123 }

Inngest function receives event → calls run_supervisor(worker_id="eng-app", ...)
eng-app runs headless checks → persists report to agent_reports table
eng-product-qa reads report at next step (or polls agent_reports)
```

This keeps eng-product-qa as a worker (no director privileges) while allowing cross-agent coordination through the existing Inngest event infrastructure.

## Change Gate

When Product proposes a feature or Engineering pushes a fix that touches voice or app, eng-product-qa intercepts.

### Change Flow

```
Product says: "Show job duration on call cards"
   OR
Engineering says: "Fix urgency badge color mapping"
        |
        v
PR created (any branch → main)
        |
        v
eng-product-qa auto-triggered
        |
        +-- 1. Classify affected surfaces
        |      - touches web/** → app surface
        |      - touches knowledge/voice-pipeline/** → voice surface
        |      - touches harness/src/voice/** → voice surface
        |      - touches both → cross-surface
        |
        +-- 2. Check contract compliance
        |      - Does the PR update the relevant contract(s)?
        |      - If adding a field: is it in voice-contract AND
        |        seam-contract AND app-contract?
        |      - If removing a field: is it removed from all three?
        |
        +-- 3. Dispatch surface agents
        |      - app surface → eng-app runs headless checks
        |      - voice surface → eng-ai-voice runs extraction regression
        |      - cross-surface → both run, eng-product-qa waits for both
        |
        +-- 4. Gate decision
               - All pass + contracts updated → APPROVE
               - Checks pass but contracts not updated → BLOCK
                 "PR adds job_duration to card but app-contract.yaml
                  not updated. Add the field to app-contract.yaml."
               - Checks fail → BLOCK with evidence
               - Founder can override any block
```

### The Contract-First Rule

No surface change ships without a contract update. If Product wants "show job duration on cards," the PR must include:

1. `voice-contract.yaml` — add `job_duration` with `extraction: required`
2. `app-contract.yaml` — add `job_duration` to call-card `must_render` fields
3. `seam-contract.yaml` — add the field mapping with `required_chain`
4. The actual code changes

eng-product-qa blocks if any contract is missing from the PR.

## Tiered Autonomy

### Auto-merge (eng-product-qa validates, no human review)

| Change Type | Example | Why Safe |
|---|---|---|
| New field addition (all three contracts + code) | Add `job_duration` to extraction, app, and seam contract | All three layers updated together |
| New extraction regex pattern | Add pattern for "tankless water heater" | Additive — doesn't change existing extractions |
| New taxonomy tag | Add `emergency-weekend` to tag list | Additive — existing tags unchanged |
| Test/eval suite updates | Add new test case, update expected outputs | Improves coverage, can't break production |
| Health check threshold tuning | Adjust warning threshold from 85% to 82% | Monitoring only |

### PR required — agent review (eng-product-qa reviews, founder notified)

| Change Type | Example | Why Needs Review |
|---|---|---|
| Extraction schema field rename | `caller_name` → `customer_name` | Breaks seam contract if app not updated |
| Classification logic change | Modify emergency vs routine determination | Changes call routing |
| App_sync payload restructure | Change field grouping or nesting | Breaks app if not coordinated |
| Scoring weight adjustment | Change lead score weights | Changes which leads surface as hot |
| App layout changes | Reorganize call card fields | Changes customer experience |

### PR required — human review (founder must approve)

| Change Type | Example | Why Founder Must See |
|---|---|---|
| Retell prompt edit | Any change to prompt text | This is what customers hear |
| Model or temperature change | Switch models, change temp | Fundamentally changes voice behavior |
| State machine change | Add/remove/reorder pipeline nodes | Changes processing flow |
| Contract field removal | Remove a field from any contract | Could break customer experience |
| Deploy script changes | Modify `deploy-retell-agent.py` | Changes how configs reach production |

### Escalation Rule

If an agent is unsure which tier a change belongs to, it always escalates up. Auto-merge uncertainty → PR agent review. Agent review uncertainty → human review. Never down.

## Schedule & Interaction Patterns

### Daily Schedule

```
6:00 AM  eng-ai-voice    Voice health check
         - Sample 5-10 recent calls, re-extract, compare
         - Check tag distribution, config drift
         - Report → voice health report

6:30 AM  eng-app          App health check
         - Load each page in headless browser
         - Verify fields render, realtime works
         - Screenshot evidence
         - Report → app health report

7:00 AM  eng-product-qa   Cross-surface health
         - Read both reports from eng-ai-voice and eng-app
         - Run seam contract invariants
         - Check: any orphan fields? broken chains? mismatches?
         - Run data integrity checks
         - Report → cross-surface report
         - All three reports feed into daily memo
```

### Weekly Schedule (Sundays)

```
6:00 AM  eng-ai-voice    Voice deep sweep
         - Full regression across all call types
         - Extraction accuracy trends
         - Prompt improvement proposals → PRs

6:30 AM  eng-app          App deep sweep
         - Full page audit (every page, every element)
         - Realtime latency measurement
         - Rendering edge cases

7:00 AM  eng-product-qa   Seam audit
         - All fields across all three contracts
         - Orphan detection, type mismatches, stale fields
         - Creates issues for any gaps found
```

### Agent Interaction Patterns

**Pattern 1: Product feature request**
```
Product agent creates spec: "Add job_duration to call cards"
    → eng-product-qa triggered on PR
    → Checks: voice-contract, app-contract, seam-contract all updated?
    → Dispatches eng-ai-voice: "can you extract job_duration reliably?"
    → Dispatches eng-app: "does job_duration render on the card?"
    → Both pass → approves PR
    → Either fails → blocks with specific reason
```

**Pattern 2: eng-ai-voice self-improvement**
```
eng-ai-voice weekly sweep finds prompt improvement
    → Creates PR with voice config change
    → eng-product-qa auto-triggered
    → Checks: does this change affect any contract field?
    → If yes → dispatches eng-app to verify app still works
    → If no (internal-only change) → validates alone
    → Tiered approval based on change type
```

**Pattern 3: Something breaks in production**
```
calllock/app.error fires (card not rendering)
    → eng-app investigates: what's broken?
    → Finds: urgency_tier coming as null, app expects string enum
    → Creates issue with evidence (screenshot + Supabase query)
    → eng-product-qa sees required-field-null in seam contract
    → Escalates: assigns to eng-ai-voice if extraction changed,
      eng-fullstack if app_sync changed
```

**Pattern 4: Founder ad hoc**
```
Founder clicks eng-app in 3D office
    → "Check if the last 5 calls render correctly"
    → eng-app loads app, finds the 5 calls, verifies each card
    → Reports back with screenshots and pass/fail per field
```

## Data Integrity Monitoring

### Ownership

| Data Concern | Owner | How Checked |
|---|---|---|
| Extraction data correct in Supabase | eng-ai-voice | Re-extract → compare to stored result |
| App displays match Supabase records | eng-app | Headless browser reads card → queries Supabase → compares |
| Field mappings consistent (no nulls where required) | eng-product-qa | SQL queries against seam contract field list |
| Tenant isolation (RLS holding) | eng-product-qa | Attempts cross-tenant query, expects failure |
| No orphan records | eng-product-qa | Checks referential integrity between call_sessions, call_records, metric_events |
| Stale data detection | eng-app | Compares latest Supabase timestamp to what app shows, flags if gap > threshold |

### eng-product-qa Daily Data Checks

Added to the 7am cross-surface health check:

```yaml
data_integrity_checks:
  - name: required-fields-not-null
    description: >
      For each required column in call_records (urgency_tier, caller_type,
      primary_intent, route, end_call_reason, revenue_tier, quality_score, tags)
      and each required JSONB key in extracted_fields (customer_name,
      problem_description, safety_emergency, appointment_booked, etc.),
      check for null values in recent records.
    query_template: >
      SELECT id FROM call_records
      WHERE {column} IS NULL
      AND created_at > now() - interval '24 hours'
    for_each_field: seam-contract.field_mappings where required_chain includes 'extraction'
    threshold: 0

  - name: tenant-isolation
    method: >
      Set app.current_tenant to tenant_A,
      attempt to read tenant_B records,
      expect zero rows returned
    frequency: daily

  - name: orphan-records
    query: >
      SELECT cr.id FROM call_records cr
      LEFT JOIN call_sessions cs ON cr.session_id = cs.id
      WHERE cs.id IS NULL
      AND cr.created_at > now() - interval '24 hours'
    threshold: 0

  - name: realtime-freshness
    method: >
      Insert test record, measure time until
      Supabase realtime delivers to subscriber
    threshold_ms: 5000
```

## Health Reports & Daily Memo Integration

### Report Storage

All agent health reports are persisted to the `agent_reports` Supabase table:

```sql
CREATE TABLE agent_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL,        -- 'eng-ai-voice', 'eng-app', 'eng-product-qa'
  report_type text NOT NULL,     -- 'voice-health-check', 'app-health-check', etc.
  report_date date NOT NULL,
  status text NOT NULL,          -- 'green', 'yellow', 'red'
  payload jsonb NOT NULL,        -- full report JSON
  created_at timestamptz DEFAULT now(),
  tenant_id uuid REFERENCES tenants(id)
);

ALTER TABLE agent_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_reports FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_reports_tenant ON agent_reports
  USING (tenant_id = current_tenant_id());

CREATE INDEX idx_agent_reports_lookup ON agent_reports(agent_id, report_date);
```

eng-product-qa queries this table at 7am to read the day's voice and app reports:
```sql
SELECT * FROM agent_reports
WHERE agent_id IN ('eng-ai-voice', 'eng-app')
AND report_date = current_date;
```

The daily memo aggregation endpoint (`/api/memo/generate`) also reads from this table.

### Voice Health Report (daily, from eng-ai-voice)

```json
{
  "agent": "eng-ai-voice",
  "report_type": "voice-health-check",
  "date": "2026-03-18",
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

### App Health Report (daily, from eng-app)

```json
{
  "agent": "eng-app",
  "report_type": "app-health-check",
  "date": "2026-03-18",
  "status": "green",
  "pages_checked": 2,
  "elements_verified": 5,
  "fields_passing": 18,
  "fields_failing": 0,
  "realtime_tests": 1,
  "realtime_passing": 1,
  "screenshots": ["calls-card.png", "calls-detail.png", "overview.png"],
  "issues_created": 0
}
```

### Cross-Surface Report (daily, from eng-product-qa)

```json
{
  "agent": "eng-product-qa",
  "report_type": "cross-surface-health",
  "date": "2026-03-18",
  "status": "green",
  "voice_report_status": "green",
  "app_report_status": "green",
  "seam_invariants_passing": 3,
  "seam_invariants_failing": 0,
  "field_mappings_total": 42,
  "field_mappings_healthy": 42,
  "orphan_fields": 0,
  "data_integrity": {
    "required_fields_null": 0,
    "tenant_isolation": "pass",
    "orphan_records": 0,
    "realtime_freshness_ms": 1200
  },
  "issues_created": 0
}
```

### Daily Memo Format

```
ENGINEERING
+-- eng-ai-voice: [green] Voice pipeline healthy
|   +-- 8 calls sampled, 94% extraction accuracy
|   +-- 0 scorecard warnings, no config drift
|
+-- eng-app: [green] App rendering verified
|   +-- 2 pages checked, 18/18 fields passing
|   +-- Realtime delivery: 1.2s avg
|
+-- eng-product-qa: [green] All seam invariants passing
    +-- 42/42 field mappings healthy, 0 orphans
    +-- Tenant isolation: pass
    +-- 0 data integrity issues
```

### 3D Office Integration

```
ENGINEERING ROOM
+-- eng-ai-voice desk: green/yellow/red based on voice health
+-- eng-app desk: green/yellow/red based on app health
+-- eng-product-qa desk: green/yellow/red based on seam + data health
+-- VP Eng director glass: worst color of the three
```

## Git Workflow

### Branch Naming

```
agent/eng-ai-voice/voice-health-2026-03-18
agent/eng-ai-voice/prompt-improvement-hvac-v11
agent/eng-app/app-health-2026-03-18
agent/eng-app/render-fix-urgency-badge
agent/eng-product-qa/seam-audit-2026-03-18
```

### Commit Message Format

```
agent(eng-app): verify call card renders urgency badge correctly

- Added headless browser check for urgency_score field on call-card
- Verified badge color maps to score range (1-3 green, 4-6 yellow, 7-10 red)
- App contract updated: urgency_score display verified
- Auto-merge tier: validation-only change

Validated-by: eng-product-qa
```

### PR Labels

| Label | Meaning | Merge Rule |
|---|---|---|
| `auto-merge` | Low-risk, eng-product-qa validated | Merges automatically |
| `agent-review` | Medium-risk, eng-product-qa must approve | Merges on approval |
| `human-review` | High-risk, founder must approve | Waits for founder |
| `urgent` | Reactive fix for production issue | Notifies founder immediately |

## Three-Layer Persistence Model

| Layer | What Lives There | Review Surface |
|---|---|---|
| **Git** | Prompts, extraction schemas, contracts, YAML configs | PRs, git log, blame |
| **GitHub Issues** | Tasks, investigations, improvement proposals, violations | Issue board, labels |
| **Supabase** | Call records, agent state, metrics, quest log, audit log, screenshots | CallLock App, daily memo, SQL |

### The Rule

- If an agent produces something a human would review in a PR → git
- If an agent produces a task to track → GitHub Issues
- If an agent produces something a human would see in a dashboard → Supabase

## Existing Code Leverage

| Existing | How Product Guardian Uses It |
|---|---|
| `scripts/deploy-retell-agent.py` | eng-ai-voice calls `--diff-only` for drift detection |
| `harness/src/voice/services/extraction.py` | eng-ai-voice re-runs extraction on sample calls |
| `harness/src/voice/services/app_sync.py` | eng-product-qa validates payload generation |
| `harness/src/voice/models.py` (CallScorecard) | eng-ai-voice evaluates call quality |
| `knowledge/industry-packs/hvac/` | Source of truth for HVAC voice config |
| `run_supervisor()` in harness | All three agents execute through existing supervisor graph |
| `MetricsEmitter` | Health reports use existing metric emission pattern |
| `InngestEventEmitter` | Scheduled tasks and reactive triggers use Inngest cron/events |
| `web/` (CallLock App) | eng-app loads and validates in headless browser |

## Implementation Prerequisites

The following new tools and infrastructure are required before these agents can execute:

| Tool | Agent | Requires | Notes |
|---|---|---|---|
| `headless-browser` | eng-app | Playwright runner, auth token for app, test tenant with known data | Blocked by Open Question 1 (test tenant) |
| `app-contract-validate` | eng-app | Contract YAML parser, DOM element matcher | Derives expected elements from app-contract.yaml, checks against Playwright DOM |
| `seam-contract-validate` | eng-product-qa | Cross-contract YAML parser, invariant checker | Reads all three contracts, evaluates invariant rules |
| `app-sync-simulate` | eng-product-qa | Extraction result → webhook payload generator | Exists conceptually in eng-qa.yaml but has no implementation reference |
| `inngest-emit` | eng-product-qa | Inngest SDK client for emitting `calllock/guardian.dispatch` events | Uses existing InngestEventEmitter pattern |
| `agent_reports` table | all three | Supabase migration | See Report Storage section for schema |

Existing tools that already have implementation references:
- `supabase-read` → Supabase client (existing)
- `extraction-rerun` → `harness/src/voice/extraction/pipeline.py` (existing)
- `retell-config-diff` → `scripts/deploy-retell-agent.py --diff-only` (existing)
- `scorecard-evaluate` → `harness/src/voice/models.py` (existing)
- `git-branch-write`, `git-pr-review`, `issue-create` → GitHub API (existing pattern)

## CEO Review Expansions (2026-03-18)

The following capabilities were accepted during SELECTIVE EXPANSION CEO review and are in-scope for implementation.

### 1. Visual Regression Testing

eng-app takes baseline screenshots of each page/element defined in the app contract. On subsequent checks and PR validations, it compares current screenshots against baselines using pixel-diff comparison.

- Baselines stored in `knowledge/voice-pipeline/app-baselines/` (PNG files, git-tracked)
- Diff threshold: configurable per element (default 1% pixel difference)
- On visual regression detected: include side-by-side diff image in PR review comment
- Baseline update: when an app contract change is approved, eng-app regenerates baselines

### 2. Self-Healing Auto-Fix PRs

For common failure patterns with known fix templates, the guardian can create fix PRs instead of just filing issues.

**Auto-fixable patterns:**

| Pattern | Agent | Fix |
|---|---|---|
| Missing extraction field (in contract but not extracted) | eng-ai-voice | Add extraction rule from known template |
| Type mismatch (string where integer expected) | eng-ai-voice | Add type coercion to extraction output |
| Field in voice-contract but missing from seam-contract | eng-product-qa | Add field_mapping entry |
| New field extracted but app-contract not updated | eng-product-qa | Add to app-contract must_render (detail, not card) |

**Safety rules:**
- Auto-fix PRs are always `agent-review` tier minimum (never auto-merge)
- eng-product-qa validates any auto-fix PR before it can merge
- Auto-fix PRs include a `[auto-fix]` label and link to the triggering violation
- Maximum 3 auto-fix PRs per day to prevent runaway behavior

### 3. Contract-as-Code CI Validation

A GitHub Actions workflow (`.github/workflows/contract-validate.yml`) that runs on every commit:

```yaml
# Validates contract consistency statically — no agents needed
triggers: [push, pull_request]
steps:
  - Parse voice-contract.yaml, app-contract.yaml, seam-contract.yaml
  - Check invariants:
    - no-orphan-extraction: every required voice field has a seam mapping
    - no-orphan-display: every app must_render field has a seam source
    - no-broken-chain: every seam mapping references valid voice + app fields
    - type-consistency: field types match across all three contracts
  - Output: pass/fail with specific violations listed
```

This catches contract inconsistencies instantly, before the agents run their more thorough runtime checks.

### 4. Founder Override Audit Trail

When the founder overrides eng-product-qa's PR block:

```sql
CREATE TABLE guardian_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pr_number integer NOT NULL,
  pr_url text NOT NULL,
  override_by text NOT NULL,        -- 'founder' or GitHub username
  override_reason text,             -- optional free-text reason
  original_block_reason text NOT NULL,
  agent_id text NOT NULL,           -- which agent blocked
  created_at timestamptz DEFAULT now(),
  tenant_id uuid REFERENCES tenants(id)
);

ALTER TABLE guardian_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardian_overrides FORCE ROW LEVEL SECURITY;
CREATE POLICY guardian_overrides_tenant ON guardian_overrides
  USING (tenant_id = current_tenant_id());
```

eng-product-qa can later query this table to learn which blocks were false positives and adjust its sensitivity.

### 5. Guardian Self-Monitoring Watchdog

A daily cron (7:30 AM, after all three agents should have reported):

```
Check agent_reports for today:
  - eng-ai-voice report exists? (expected by 6:15 AM)
  - eng-app report exists? (expected by 6:45 AM)
  - eng-product-qa report exists? (expected by 7:15 AM)

If any missing:
  → Slack alert: "Guardian agent {name} did not report today"
  → Quest log entry with urgency: high
```

Implemented as an Inngest cron function, separate from the guardian agents themselves — so if the agents are down, the watchdog still fires.

### 6. Technical Decisions from CEO Review

| Decision | Choice | Rationale |
|---|---|---|
| PR trigger mechanism | GitHub Actions workflow (`.github/workflows/product-guardian.yml`) | Simpler than webhook, repo already uses Actions |
| Dispatch timeout behavior | 5-minute timeout, BLOCK on timeout | Safe default prevents silent pass; message: "Guardian check timed out — please re-run" |
| Agent dispatch coordination | Inngest events with timeout polling of agent_reports | role:worker can't use supervisor job_dispatch |

## Antspace-Inspired Patterns (2026-03-18)

Four patterns extracted from the Antspace environment-runner reverse-engineering analysis, applied to the Product Guardian and supervisor graph.

### 1. Pre-Persist Guardian Gate

A `guardian_gate` node now sits between verification and persist in the supervisor graph. Inspired by Antspace's pre-stop hook (multi-condition validation before session end). The gate checks:

- Verification verdict passed (or is an expected block)
- Required output fields present (no nulls where seam contract says required)
- Tenant ID set (prevents orphan records)

Records that fail the gate persist with `quarantine: true` — they're in Supabase for audit but invisible to app-facing queries. This means **eng-app headless browser checks will never show quarantined data**, and eng-product-qa can still query quarantined records for investigation.

Implementation: `harness/src/harness/nodes/guardian_gate.py`

### 2. Unified MCP Server (pulled to Week 5-6)

A single MCP server wrapping all harness tool implementations, tenant-scoped. Both Hermes workers and the CEO agent share the same tool surface. Modeled after Antspace's embedded Supabase MCP (6 tools auto-provisioned per session).

### 3. Explicit `run_status` Lifecycle

Every supervisor run now tracks a `run_status` field through explicit phases:

```
queued → context_assembly → policy_check → executing → verifying → gate_check → dispatching → persisting → completed|quarantined|failed
```

The watchdog, Discord projector, and CEO agent all observe `run_status` instead of inferring state from `current_state`. The guardian self-monitoring watchdog (Section 5 above) can now check `run_status` for stuck runs (e.g., `executing` for > 5 minutes).

Implementation: `harness/src/harness/state.py` (RunStatus type), `supervisor.py` (_NODE_TO_RUN_STATUS mapping)

### 4. NDJSON Streaming

Real-time run status streaming via `GET /runs/{run_id}/stream` returning `application/x-ndjson`. Each supervisor node transition emits one JSON line. Terminal statuses (`completed`, `quarantined`, `failed`) close the stream. Heartbeats every 15s keep connections alive.

Consumers:
- **Discord projector**: connects to stream per run, posts thread updates in real-time
- **CEO agent**: subscribes to high-priority runs for push notifications
- **Watchdog**: monitors for runs stuck in non-terminal status

Implementation: `harness/src/harness/streaming.py`, endpoint in `server.py`

## Open Questions

1. **Test tenant for headless browser checks** — eng-app needs a tenant with known test data to validate against. Should this be a dedicated test tenant, or should it validate against real customer data (read-only)?

2. **Multi-industry-pack support** — When CallLock adds a second industry pack beyond HVAC, does each pack get its own voice contract, or is there one contract with pack-specific field sections?

3. **Alert channels** — Watchdog sends Slack alerts + quest log entries.
   Discord integration planned (see Hermes integration design spec).
   SMS for critical alerts TBD.

4. ~~**eng-fullstack dependency**~~ — Resolved. eng-fullstack worker spec added. Functions as a triage agent: reads guardian issues, examines code, suggests fixes. With Hermes integration, will be able to create fix PRs autonomously.

# Product Guardian Full-Surface System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three-agent Product Guardian system (eng-ai-voice, eng-app, eng-product-qa) with contract-first validation, PR change gating, visual regression testing, self-healing auto-fix PRs, and a guardian watchdog.

**Architecture:** Rename eng-qa → eng-product-qa, split the monolithic seam-contract.yaml into three contracts (voice, app, seam v2.0), create the eng-app worker spec, add Supabase tables for agent reports and founder overrides, add a `calllock/guardian.dispatch` Inngest event for cross-agent coordination, a CI workflow for contract consistency, and Playwright-based visual regression testing.

**Tech Stack:** Python (harness), TypeScript (Inngest functions, validation scripts), Playwright (headless browser), YAML (contracts, worker specs), SQL (Supabase migrations), GitHub Actions (CI)

**Spec:** `docs/superpowers/specs/2026-03-18-product-guardian-design.md` + `.context/attachments/pasted_text_2026-03-18_13-48-46.txt`

---

## File Structure

### Files to Create

| File | Responsibility |
|---|---|
| `knowledge/worker-specs/eng-product-qa.yaml` | Renamed + expanded eng-qa spec |
| `knowledge/worker-specs/eng-app.yaml` | New App Guardian worker spec |
| `knowledge/voice-pipeline/voice-contract.yaml` | Voice pipeline extraction contract |
| `knowledge/voice-pipeline/app-contract.yaml` | App rendering contract |
| `supabase/migrations/052_agent_reports.sql` | agent_reports table |
| `supabase/migrations/053_guardian_overrides.sql` | guardian_overrides table |
| `inngest/src/events/guardian-schemas.ts` | Guardian dispatch event schema |
| `inngest/src/functions/guardian-dispatch.ts` | Guardian dispatch Inngest function |
| `inngest/src/functions/guardian-watchdog.ts` | Watchdog cron function |
| `scripts/validate-contracts.py` | Three-contract consistency validator |
| `.github/workflows/contract-validate.yml` | CI workflow for contract validation |
| `.github/workflows/product-guardian.yml` | PR gate workflow (triggers eng-product-qa) |

### Files to Modify

| File | Change |
|---|---|
| `knowledge/voice-pipeline/seam-contract.yaml` | Restructure from v1.0 flat fields to v2.0 field_mappings |
| `knowledge/worker-specs/eng-ai-voice.yaml` | Update `validated_by: eng-qa` → `eng-product-qa`, add `voice-contract.yaml` to context_sources |
| `docs/superpowers/specs/2026-03-17-corporate-hierarchy-agent-roster.md` | Replace `eng-qa` with `eng-product-qa` in roster |
| `docs/superpowers/specs/2026-03-18-llm-tool-assignments.md` | Replace `eng-qa` with `eng-product-qa` in Engineering table |
| `inngest/src/events/schemas.ts` | Export guardian schemas |
| `inngest/src/index.ts` | Register `guardianDispatch` and `guardianWatchdog` in the functions array |

### Files to Delete

| File | Reason |
|---|---|
| `knowledge/worker-specs/eng-qa.yaml` | Replaced by `eng-product-qa.yaml` |

---

## Phase 1: Migration & Contracts (Tasks 1–4)

### Task 1: Rename eng-qa → eng-product-qa

**Files:**
- Create: `knowledge/worker-specs/eng-product-qa.yaml`
- Delete: `knowledge/worker-specs/eng-qa.yaml`
- Modify: `knowledge/worker-specs/eng-ai-voice.yaml:129` (`validated_by`)
- Modify: `docs/superpowers/specs/2026-03-17-corporate-hierarchy-agent-roster.md`
- Modify: `docs/superpowers/specs/2026-03-18-llm-tool-assignments.md`

- [ ] **Step 1: Copy eng-qa.yaml to eng-product-qa.yaml**

Copy `knowledge/worker-specs/eng-qa.yaml` to `knowledge/worker-specs/eng-product-qa.yaml`.

- [ ] **Step 2: Update worker_id and title in eng-product-qa.yaml**

In the new file, change:
```json
"worker_id": "eng-qa"  →  "worker_id": "eng-product-qa"
"title": "QA/Automation Engineer"  →  "title": "Product QA Engineer"
```

Update the mission to match the design spec:
```json
"mission": "Guard product quality across all surfaces. Own the seam contract that maps voice pipeline fields to app rendering. Gate all PRs that touch voice or app code. Dispatch surface agents for validation via Inngest events. Ensure contract-first discipline. Monitor data integrity including tenant isolation."
```

- [ ] **Step 3: Update eng-product-qa scope**

Replace `can_do` with expanded scope from design spec:
```json
"can_do": [
  "validate seam contract alignment across all three contracts",
  "re-run extraction pipeline for comparison testing",
  "simulate app_sync payload generation from extraction results",
  "dispatch eng-app and eng-ai-voice via calllock/guardian.dispatch events",
  "approve or block pull requests with detailed validation reports",
  "create GitHub issues for seam violations and display gaps",
  "audit all field mappings for orphans and mismatches",
  "run data integrity checks (required fields, tenant isolation, orphan records)",
  "create auto-fix PRs for common failure patterns (max 3/day)"
]
```

Add `inngest_emit` to `tools_allowed`:
```json
"tools_allowed": [
  "supabase_read",
  "extraction_rerun",
  "app_sync_simulate",
  "seam_contract_validate",
  "git_pr_review",
  "issue_create",
  "inngest_emit"
]
```

- [ ] **Step 4: Update scheduled_tasks and reactive_triggers**

Replace the scheduled tasks:
```json
"scheduled_tasks": [
  {
    "cron": "0 7 * * *",
    "task_type": "cross-surface-health",
    "description": "Read voice and app reports, run seam contract invariants, check data integrity, report to daily memo"
  },
  {
    "cron": "0 7 * * 0",
    "task_type": "seam-audit",
    "description": "All fields across all three contracts. Orphan detection, type mismatches, stale fields. Creates issues for gaps."
  }
]
```

Update reactive_triggers — eng-product-qa is now the sole PR entry point:
```json
"reactive_triggers": [
  {
    "event": "calllock/pr.created",
    "filter": {
      "paths": [
        "web/**",
        "knowledge/voice-pipeline/**",
        "harness/src/voice/**",
        "scripts/deploy-retell-agent.py"
      ]
    },
    "task_type": "change-gate-review",
    "description": "Gate PRs touching voice or app surfaces. Classify affected surfaces, check contract compliance, dispatch surface agents, make gate decision."
  },
  {
    "event": "calllock/app_sync.failure",
    "task_type": "seam-investigate",
    "description": "Diagnose app_sync delivery failures"
  }
]
```

- [ ] **Step 5: Add LLM model and context_sources**

Add to the spec:
```json
"llm_model": "codex",
"llm_escalation": [
  {"condition": "manipulates_production_data", "model": "nanoclaw"},
  {"condition": "multi_client_context", "model": "claude-sonnet"}
],
"context_sources": [
  "knowledge/voice-pipeline/seam-contract.yaml",
  "knowledge/voice-pipeline/voice-contract.yaml",
  "knowledge/voice-pipeline/app-contract.yaml"
]
```

- [ ] **Step 6: Update interaction_with**

```json
"interaction_with": {
  "eng-ai-voice": "Dispatches for voice surface validation on PRs. Reads voice health reports. Validates extraction changes against voice contract.",
  "eng-app": "Dispatches for app surface validation on PRs. Reads app health reports. Validates rendering changes against app contract.",
  "eng-fullstack": "Creates issues when app needs UI changes to display new fields.",
  "eng-vp": "Reports department health status for daily memo and office dashboard."
}
```

- [ ] **Step 7: Update eng-ai-voice.yaml validated_by**

In `knowledge/worker-specs/eng-ai-voice.yaml`, change:
```json
"validated_by": "eng-qa"  →  "validated_by": "eng-product-qa"
```

- [ ] **Step 8: Update roster doc**

In `docs/superpowers/specs/2026-03-17-corporate-hierarchy-agent-roster.md`, find and replace all occurrences of `eng-qa` with `eng-product-qa` and update the title from "QA/Automation Engineer" to "Product QA Engineer".

- [ ] **Step 9: Update LLM tool assignments doc**

In `docs/superpowers/specs/2026-03-18-llm-tool-assignments.md`, find and replace `eng-qa` with `eng-product-qa`.

- [ ] **Step 10: Delete eng-qa.yaml**

```bash
rm knowledge/worker-specs/eng-qa.yaml
```

- [ ] **Step 11: Run validation**

```bash
node scripts/validate-worker-specs.ts
```

Expected: All specs pass, including the new eng-product-qa.yaml.

- [ ] **Step 12: Commit**

```bash
git add knowledge/worker-specs/eng-product-qa.yaml knowledge/worker-specs/eng-ai-voice.yaml docs/superpowers/specs/
git rm knowledge/worker-specs/eng-qa.yaml
git commit -m "refactor: rename eng-qa to eng-product-qa with expanded scope"
```

---

### Task 2: Split seam-contract.yaml into three contracts

**Files:**
- Create: `knowledge/voice-pipeline/voice-contract.yaml`
- Create: `knowledge/voice-pipeline/app-contract.yaml`
- Modify: `knowledge/voice-pipeline/seam-contract.yaml` (v1.0 → v2.0)

The current seam-contract.yaml has 31 active fields. The split is determined by two properties per field:
- `extraction != not_applicable` → field goes into voice-contract.yaml
- `app_display != not_shown` → field goes into app-contract.yaml
- All 31 active fields get a mapping in seam-contract.yaml v2.0

- [ ] **Step 1: Create voice-contract.yaml**

Create `knowledge/voice-pipeline/voice-contract.yaml` containing only fields where `extraction != not_applicable` from the current seam contract. Use the exact field structure from the design spec (Section: Voice Contract).

Fields to include (from seam-contract.yaml analysis):
- **extraction: required** (17 fields): customer_name, customer_phone, urgency_tier, dashboard_urgency, caller_type, primary_intent, route, end_call_reason, problem_description, safety_emergency, appointment_booked, revenue_tier, revenue_estimate, tag_categories, tags, quality_score, scorecard_warnings
- **extraction: optional** (9 fields): service_address, hvac_issue_type, equipment_type, equipment_brand, equipment_age, appointment_date_time, callback_type, problem_duration, sales_lead_notes

Preserve the exact same field properties (type, enum, fallback, default, description) from the original seam contract.

Add the `retell_config` section:
```yaml
retell_config:
  model_constraints: [temperature, max_tokens]
  prompt_hash: "sha256:pending"  # set on first baseline
```

Add the `reserved_fields` section (copy from seam-contract.yaml v1.0).

- [ ] **Step 2: Create app-contract.yaml**

Create `knowledge/voice-pipeline/app-contract.yaml` containing page definitions and behaviors. Derive from fields where `app_display != not_shown` in the current seam contract.

Card fields (app_display == card): customer_name, customer_phone, problem_description, urgency_tier, safety_emergency, appointment_booked, callback_type, created_at
Detail fields (app_display == detail): transcript, service_address, hvac_issue_type, equipment_type, equipment_brand, equipment_age, appointment_date_time, end_call_reason

Use the exact structure from the design spec (Section: App Contract), including the `behaviors` section for realtime-card-appearance and card-click-detail.

- [ ] **Step 3: Restructure seam-contract.yaml to v2.0**

Replace the flat `fields` list with `field_mappings` that cross-reference voice and app contracts. Use the exact structure from the design spec (Section: Seam Contract).

Each field mapping has: voice_field, supabase (column or jsonb), app_element, app_display, required_chain.

Add the `invariants` section:
```yaml
invariants:
  - name: no-orphan-extraction
    rule: "every field in voice-contract with extraction:required must appear in at least one field_mapping"
  - name: no-orphan-display
    rule: "every field in app-contract must_render must have a source in field_mappings"
  - name: no-broken-chain
    rule: "every field_mapping must have all links in required_chain passing"
```

Remove the `validation_rules` section (moved to invariants). Remove the `reserved_fields` section (moved to voice contract). Update version to "2.0", owner to "eng-product-qa".

- [ ] **Step 4: Verify field counts**

Manual check:
- voice-contract.yaml should have 26 extraction fields (17 required + 9 optional) + reserved fields
- app-contract.yaml should have 2 pages, with card (8 fields) and detail (8 fields)
- seam-contract.yaml v2.0 should have ~31 field_mappings + 3 invariants
- No field from the original should be lost

- [ ] **Step 5: Commit**

```bash
git add knowledge/voice-pipeline/voice-contract.yaml knowledge/voice-pipeline/app-contract.yaml knowledge/voice-pipeline/seam-contract.yaml
git commit -m "refactor: split seam-contract into voice, app, and seam v2.0 contracts"
```

---

### Task 3: Create eng-app worker spec

**Files:**
- Create: `knowledge/worker-specs/eng-app.yaml`

- [ ] **Step 1: Create eng-app.yaml**

Create `knowledge/worker-specs/eng-app.yaml` following the `schema_version: 1.1` JSON format established by eng-ai-voice.yaml and eng-product-qa.yaml.

```json
{
  "schema_version": "1.1",
  "worker_id": "eng-app",
  "version": "0.1.0",
  "title": "App Guardian Engineer",
  "department": "engineering",
  "supervisor": "eng-vp",
  "role": "worker",
  "mission": "Guard the CallLock App. Run headless browser checks to verify pages render correctly, realtime subscriptions deliver updates, and data displayed matches what's in Supabase. Validate against the app contract.",
  "scope": {
    "can_do": [
      "load CallLock App pages in headless browser (Playwright)",
      "verify all must_render fields are visible in the DOM",
      "compare displayed data against Supabase source records",
      "test realtime subscription delivery within timeout",
      "take baseline and comparison screenshots for visual regression",
      "validate PR changes render correctly in headless browser",
      "create GitHub issues for rendering gaps or realtime failures",
      "generate pixel-diff images for visual regression reports"
    ],
    "cannot_do": [
      "modify CallLock App source code",
      "modify voice pipeline code or prompts",
      "deploy changes to production",
      "access customer PII beyond what renders in the app",
      "auto-merge any PR — only validates and reports"
    ]
  },
  "execution_scope": "internal",
  "inputs": [
    "knowledge/voice-pipeline/app-contract.yaml",
    "call_records from Supabase (read-only)",
    "CallLock App running in headless browser",
    "calllock/guardian.dispatch events from eng-product-qa"
  ],
  "outputs": [
    "app health reports (daily)",
    "app deep sweep reports (weekly)",
    "PR validation reports (pass/fail with screenshot evidence)",
    "GitHub issues for rendering gaps",
    "visual regression diff images"
  ],
  "tools_allowed": [
    "supabase_read",
    "headless_browser",
    "app_contract_validate",
    "git_pr_review",
    "issue_create"
  ],
  "success_metrics": [
    {"name": "field_render_rate", "target": 1.0, "eval_dataset": "evals/eng-app/field-render.json"},
    {"name": "realtime_delivery_rate", "target": 1.0, "eval_dataset": "evals/eng-app/realtime-delivery.json"},
    {"name": "data_accuracy_rate", "target": 1.0, "eval_dataset": "evals/eng-app/data-accuracy.json"},
    {"name": "visual_regression_rate", "target": 0, "eval_dataset": "evals/eng-app/visual-regression.json"}
  ],
  "approval_boundaries": [
    "Cannot approve any PR — only validates and reports",
    "Cannot modify app contract directly — only proposes changes via issues",
    "Cannot override eng-product-qa gate decision"
  ],
  "validation_checks": {
    "field_render": {
      "description": "All must_render fields in app-contract visible in headless browser",
      "check": "DOM element exists and contains expected value"
    },
    "realtime_delivery": {
      "description": "New call records appear in app within 5 seconds",
      "check": "Insert test record, wait for DOM update, verify within timeout"
    },
    "data_accuracy": {
      "description": "Displayed values match Supabase source records",
      "check": "Query Supabase, compare to DOM text content"
    },
    "visual_regression": {
      "description": "Screenshots match baselines within threshold",
      "check": "Pixel-diff comparison, threshold per element (default 1%)"
    }
  },
  "scheduled_tasks": [
    {
      "cron": "30 6 * * *",
      "task_type": "app-health-check",
      "description": "Load each page in headless browser, verify must_render fields, test realtime, take screenshots, report to agent_reports"
    },
    {
      "cron": "30 6 * * 0",
      "task_type": "app-deep-sweep",
      "description": "Full page audit — every page, every element, realtime latency measurement, rendering edge cases"
    }
  ],
  "reactive_triggers": [
    {
      "event": "calllock/guardian.dispatch",
      "filter": {"target": "eng-app"},
      "task_type": "app-pr-validation",
      "description": "Run headless browser validation for PR changes, dispatched by eng-product-qa"
    },
    {
      "event": "calllock/app.error",
      "task_type": "app-investigate",
      "description": "Investigate app rendering errors"
    },
    {
      "event": "calllock/realtime.drop",
      "task_type": "app-investigate",
      "description": "Investigate realtime subscription drops"
    }
  ],
  "context_sources": [
    "knowledge/voice-pipeline/app-contract.yaml",
    "web/src/lib/transforms.ts",
    "web/src/types/call.ts",
    "web/src/components/mail/mail-display.tsx",
    "web/src/components/mail/mail-list.tsx"
  ],
  "dependencies": [
    "knowledge/voice-pipeline/app-contract.yaml",
    "web/src/lib/transforms.ts",
    "web/src/types/call.ts"
  ],
  "interaction_with": {
    "eng-product-qa": "Receives dispatch events for PR validation. Reports app health to agent_reports. Escalates rendering failures.",
    "eng-vp": "Reports department health status for daily memo and office dashboard."
  },
  "git_workflow": {
    "branch_pattern": "agent/eng-app/{task-description}",
    "commit_prefix": "agent(eng-app):",
    "pr_labels": ["auto-merge", "agent-review", "human-review", "urgent"],
    "validated_by": "eng-product-qa"
  }
}
```

- [ ] **Step 2: Run validation**

```bash
node scripts/validate-worker-specs.ts
```

Expected: All specs pass, including the new eng-app.yaml.

- [ ] **Step 3: Commit**

```bash
git add knowledge/worker-specs/eng-app.yaml
git commit -m "feat: add eng-app worker spec for App Guardian"
```

---

### Task 4: Update eng-ai-voice context sources

**Files:**
- Modify: `knowledge/worker-specs/eng-ai-voice.yaml:114-119` (context_sources)

- [ ] **Step 1: Add voice-contract.yaml to context_sources**

In eng-ai-voice.yaml, update context_sources to include the new voice contract:
```json
"context_sources": [
  "knowledge/voice-pipeline/voice-contract.yaml",
  "knowledge/voice-pipeline/seam-contract.yaml",
  "knowledge/industry-packs/hvac/",
  "scripts/deploy-retell-agent.py"
]
```

- [ ] **Step 2: Run validation**

```bash
node scripts/validate-worker-specs.ts
```

- [ ] **Step 3: Commit**

```bash
git add knowledge/worker-specs/eng-ai-voice.yaml
git commit -m "chore: add voice-contract.yaml to eng-ai-voice context sources"
```

---

## Phase 2: Infrastructure (Tasks 5–8)

### Task 5: Supabase migration — agent_reports table

**Files:**
- Create: `supabase/migrations/052_agent_reports.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- Agent health reports from Product Guardian agents.
-- Each agent writes a daily report; eng-product-qa reads them at 7am
-- for the cross-surface health check.

CREATE TABLE agent_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id text NOT NULL,
  report_type text NOT NULL,
  report_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('green', 'yellow', 'red')),
  payload jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  tenant_id uuid NOT NULL REFERENCES tenants(id)
);

ALTER TABLE agent_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_reports FORCE ROW LEVEL SECURITY;

CREATE POLICY agent_reports_tenant ON agent_reports
  USING (tenant_id = current_tenant_id());

-- Lookup index: agent + date (used by eng-product-qa at 7am)
CREATE INDEX idx_agent_reports_lookup
  ON agent_reports (agent_id, report_date);

-- Tenant index for RLS performance
CREATE INDEX idx_agent_reports_tenant
  ON agent_reports (tenant_id);
```

- [ ] **Step 2: Commit**

```bash
git add supabase/migrations/052_agent_reports.sql
git commit -m "feat: add agent_reports table for Product Guardian health reports"
```

---

### Task 6: Supabase migration — guardian_overrides table

**Files:**
- Create: `supabase/migrations/053_guardian_overrides.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- Founder override audit trail.
-- When the founder overrides eng-product-qa's PR block,
-- the override is logged here for learning and governance.

CREATE TABLE guardian_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pr_number integer NOT NULL,
  pr_url text NOT NULL,
  override_by text NOT NULL,
  override_reason text,
  original_block_reason text NOT NULL,
  agent_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  tenant_id uuid NOT NULL REFERENCES tenants(id)
);

ALTER TABLE guardian_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardian_overrides FORCE ROW LEVEL SECURITY;

CREATE POLICY guardian_overrides_tenant ON guardian_overrides
  USING (tenant_id = current_tenant_id());

CREATE INDEX idx_guardian_overrides_tenant
  ON guardian_overrides (tenant_id);
```

- [ ] **Step 2: Commit**

```bash
git add supabase/migrations/053_guardian_overrides.sql
git commit -m "feat: add guardian_overrides table for founder override audit trail"
```

---

### Task 7: Guardian dispatch Inngest event and function

**Files:**
- Create: `inngest/src/events/guardian-schemas.ts`
- Create: `inngest/src/functions/guardian-dispatch.ts`
- Modify: `inngest/src/events/schemas.ts` (re-export)

- [ ] **Step 1: Create guardian event schema**

Create `inngest/src/events/guardian-schemas.ts`:

```typescript
/**
 * Event emitted by eng-product-qa to dispatch surface agents.
 * eng-product-qa has role:worker so it cannot use the supervisor's
 * job_dispatch_node. Instead it emits this event, which triggers
 * an Inngest function that calls run_supervisor() for the target agent.
 */
export interface GuardianDispatchPayload {
  /** Target worker_id: "eng-app" or "eng-ai-voice" */
  target: string;
  /** Task to execute: "app-pr-validation", "voice-pr-validation" */
  task_type: string;
  /** PR number if triggered by a PR */
  pr_id?: number;
  /** PR URL for context */
  pr_url?: string;
  /** Additional context for the target agent */
  task_context: Record<string, unknown>;
  /** Always "eng-product-qa" */
  origin: "eng-product-qa";
  /** Tenant scope (UUID) */
  tenant_id: string;
  /** Dispatch timeout in ms (default 300000 = 5 min) */
  timeout_ms: number;
}

/**
 * Watchdog check payload — emitted by cron, checks that all
 * guardian agents reported today.
 */
export interface GuardianWatchdogPayload {
  /** Date to check reports for (YYYY-MM-DD) */
  check_date: string;
  /** Tenant scope (UUID) */
  tenant_id: string;
}
```

- [ ] **Step 2: Create guardian dispatch Inngest function**

Create `inngest/src/functions/guardian-dispatch.ts`:

```typescript
import { inngest } from "../client";

/**
 * Receives calllock/guardian.dispatch events from eng-product-qa
 * and triggers run_supervisor() for the target agent.
 *
 * eng-product-qa emits:
 *   { target: "eng-app", task_type: "app-pr-validation", pr_id: 123 }
 *
 * This function calls the harness API to run the target agent
 * within the supervisor graph (policy_gate → worker → verification → persist).
 */
export const guardianDispatch = inngest.createFunction(
  {
    id: "guardian-dispatch",
    name: "Guardian Agent Dispatch",
  },
  { event: "calllock/guardian.dispatch" },
  async ({ event, step }) => {
    const { target, task_type, pr_id, pr_url, task_context, tenant_id, timeout_ms } = event.data;

    // Call run_supervisor for the target agent via harness API
    const result = await step.run(`dispatch-${target}`, async () => {
      const response = await fetch(`${process.env.HARNESS_API_URL}/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${process.env.HARNESS_API_KEY}`,
        },
        body: JSON.stringify({
          worker_id: target,
          tenant_id,
          task: {
            task_type,
            pr_id,
            pr_url,
            ...task_context,
          },
        }),
        signal: AbortSignal.timeout(timeout_ms),
      });

      if (!response.ok) {
        throw new Error(`Harness dispatch failed: ${response.status} ${await response.text()}`);
      }

      return response.json();
    });

    // Persist report reference so eng-product-qa can read it
    await step.run("log-dispatch-result", async () => {
      return {
        target,
        task_type,
        pr_id,
        status: result.verification?.verdict ?? "unknown",
        report_id: result.report_id,
      };
    });

    return result;
  }
);
```

- [ ] **Step 3: Re-export from schemas.ts**

In `inngest/src/events/schemas.ts`, add at the end:
```typescript
export { GuardianDispatchPayload, GuardianWatchdogPayload } from "./guardian-schemas";
```

- [ ] **Step 4: Register guardianDispatch in inngest/src/index.ts**

In `inngest/src/index.ts`, add the import at the top with the other function imports:
```typescript
import { guardianDispatch } from "./functions/guardian-dispatch.js";
```

Then add `guardianDispatch` to the `functions` array (after `callRecordsRetention`):
```typescript
export const functions = [
  // ... existing functions ...
  callRecordsRetention,
  guardianDispatch,
];
```

- [ ] **Step 5: Commit**

```bash
git add inngest/src/events/guardian-schemas.ts inngest/src/functions/guardian-dispatch.ts inngest/src/events/schemas.ts inngest/src/index.ts
git commit -m "feat: add guardian dispatch Inngest event and function"
```

---

### Task 8: Guardian watchdog Inngest cron

**Files:**
- Create: `inngest/src/functions/guardian-watchdog.ts`
- Modify: `inngest/src/index.ts` (register watchdog function)

- [ ] **Step 1: Create the watchdog function**

```typescript
import { inngest } from "../client";

/**
 * Watchdog cron: fires at 7:30 AM daily, after all three guardian
 * agents should have reported. Checks agent_reports table and
 * alerts if any report is missing.
 *
 * Separate from the guardian agents — if they're down, this still fires.
 */
export const guardianWatchdog = inngest.createFunction(
  {
    id: "guardian-watchdog",
    name: "Guardian Self-Monitoring Watchdog",
  },
  { cron: "30 7 * * *" },
  async ({ step }) => {
    const today = new Date().toISOString().split("T")[0];

    const missing = await step.run("check-reports", async () => {
      const expected = [
        { agent_id: "eng-ai-voice", expected_by: "6:15 AM" },
        { agent_id: "eng-app", expected_by: "6:45 AM" },
        { agent_id: "eng-product-qa", expected_by: "7:15 AM" },
      ];

      const response = await fetch(
        `${process.env.SUPABASE_URL}/rest/v1/agent_reports?report_date=eq.${today}&select=agent_id`,
        {
          headers: {
            apikey: process.env.SUPABASE_SERVICE_ROLE_KEY!,
            Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY!}`,
          },
        }
      );

      const reports = await response.json();
      const reportedAgents = new Set(reports.map((r: any) => r.agent_id));

      return expected
        .filter((e) => !reportedAgents.has(e.agent_id))
        .map((e) => ({ ...e, date: today }));
    });

    if (missing.length > 0) {
      // Alert via Slack webhook
      await step.run("alert-missing", async () => {
        const slackUrl = process.env.SLACK_WEBHOOK_URL;
        if (!slackUrl) return { skipped: true, reason: "no SLACK_WEBHOOK_URL" };

        const agentList = missing
          .map((m: any) => `• *${m.agent_id}* (expected by ${m.expected_by})`)
          .join("\n");

        await fetch(slackUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: `🚨 Guardian watchdog: ${missing.length} agent(s) did not report today (${today}):\n${agentList}`,
          }),
        });

        return { alerted: true, missing_count: missing.length };
      });

      // Also create quest log entry
      await step.run("create-quest", async () => {
        for (const m of missing) {
          await fetch(`${process.env.SUPABASE_URL}/rest/v1/quest_log`, {
            method: "POST",
            headers: {
              apikey: process.env.SUPABASE_SERVICE_ROLE_KEY!,
              Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY!}`,
              "Content-Type": "application/json",
              Prefer: "return=minimal",
            },
            body: JSON.stringify({
              tenant_id: process.env.DEFAULT_TENANT_ID,
              agent_id: m.agent_id,
              department: "engineering",
              summary: `Guardian agent ${m.agent_id} did not report today (expected by ${m.expected_by})`,
              urgency: "high",
              status: "pending",
            }),
          });
        }
        return { quests_created: missing.length };
      });
    }

    return { date: today, missing_count: missing.length, missing };
  }
);
```

- [ ] **Step 2: Register guardianWatchdog in inngest/src/index.ts**

In `inngest/src/index.ts`, add the import at the top:
```typescript
import { guardianWatchdog } from "./functions/guardian-watchdog.js";
```

Add `guardianWatchdog` to the `functions` array (after `guardianDispatch`):
```typescript
export const functions = [
  // ... existing functions ...
  guardianDispatch,
  guardianWatchdog,
];
```

- [ ] **Step 3: Commit**

```bash
git add inngest/src/functions/guardian-watchdog.ts inngest/src/index.ts
git commit -m "feat: add guardian watchdog cron to alert on missing agent reports"
```

---

## Phase 3: Contract Validation CI (Tasks 9–10)

### Task 9: Contract consistency validation script

**Files:**
- Create: `scripts/validate-contracts.py`

Uses Python + PyYAML, matching the existing `scripts/validate-seam-contract.py` pattern. The TypeScript validate-*.ts scripts don't have a YAML parser available — the worker specs are JSON despite the `.yaml` extension. The contracts are real YAML, so Python is the right tool.

- [ ] **Step 1: Create the validation script**

Create `scripts/validate-contracts.py`:

```python
#!/usr/bin/env python3
"""
Validate consistency across the three Product Guardian contracts.

Checks:
  1. no-orphan-extraction: every required voice field has a seam mapping
  2. no-orphan-display: every app must_render field has a seam source
  3. no-broken-chain: every seam mapping references valid voice/app fields
  4. type-consistency: field types match across contracts

Exit 0 on pass, 1 on failure.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "knowledge" / "voice-pipeline"


def load_contract(name: str) -> dict:
    path = PIPELINE_DIR / name
    if not path.exists():
        print(f"ERROR: {name} not found at {path}")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    voice = load_contract("voice-contract.yaml")
    app = load_contract("app-contract.yaml")
    seam = load_contract("seam-contract.yaml")

    errors: list[str] = []

    # --- Invariant 1: no-orphan-extraction ---
    voice_required = {
        f["name"] for f in (voice.get("fields") or [])
        if f.get("extraction") == "required"
    }
    seam_voice_fields = {
        m["voice_field"] for m in (seam.get("field_mappings") or [])
    }
    for field in sorted(voice_required - seam_voice_fields):
        errors.append(
            f'no-orphan-extraction: voice-contract required field "{field}" has no seam mapping'
        )

    # --- Invariant 2: no-orphan-display ---
    app_must_render: set[str] = set()
    for page in app.get("pages") or []:
        for element in page.get("must_render") or []:
            app_must_render.update(element.get("fields") or [])

    seam_displayed = {
        m["voice_field"] for m in (seam.get("field_mappings") or [])
        if m.get("app_display") not in (None, "not_shown")
    }
    for field in sorted(app_must_render - seam_displayed):
        errors.append(
            f'no-orphan-display: app-contract must_render field "{field}" has no seam source'
        )

    # --- Invariant 3: no-broken-chain ---
    all_voice_names = {f["name"] for f in (voice.get("fields") or [])}
    for mapping in seam.get("field_mappings") or []:
        chain = mapping.get("required_chain") or []
        if "extraction" in chain and mapping["voice_field"] not in all_voice_names:
            errors.append(
                f'no-broken-chain: seam mapping "{mapping["voice_field"]}" not found in voice-contract'
            )

    # --- Type consistency ---
    voice_types = {f["name"]: f.get("type") for f in (voice.get("fields") or [])}
    # App contract doesn't define per-field types — types are authoritative in voice contract.
    # Check that seam mappings don't reference fields with missing type definitions.
    for mapping in seam.get("field_mappings") or []:
        vf = mapping["voice_field"]
        if vf in voice_types and voice_types[vf] is None:
            errors.append(f'type-consistency: voice field "{vf}" has no type defined')

    # --- Report ---
    if errors:
        print(f"\n❌ Contract validation failed ({len(errors)} error{'s' if len(errors) != 1 else ''}):\n")
        for err in errors:
            print(f"  • {err}")
        sys.exit(1)

    voice_count = len(voice.get("fields") or [])
    app_pages = len(app.get("pages") or [])
    app_fields = len(app_must_render)
    seam_mappings = len(seam.get("field_mappings") or [])
    print(f"\n✅ Contract validation passed")
    print(f"   Voice: {voice_count} fields")
    print(f"   App: {app_pages} pages, {app_fields} must_render fields")
    print(f"   Seam: {seam_mappings} field mappings, 3 invariants checked")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test locally**

```bash
python scripts/validate-contracts.py
```

Expected: `✅ Contract validation passed` (assuming contracts were created correctly in Task 2).

- [ ] **Step 3: Commit**

```bash
git add scripts/validate-contracts.py
git commit -m "feat: add contract consistency validation script"
```

---

### Task 10: Contract validation CI workflow

**Files:**
- Create: `.github/workflows/contract-validate.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Contract Validation

on:
  push:
    branches: ["main"]
    paths:
      - "knowledge/voice-pipeline/**"
  pull_request:
    paths:
      - "knowledge/voice-pipeline/**"

jobs:
  validate-contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install pyyaml
      - run: python scripts/validate-contracts.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/contract-validate.yml
git commit -m "feat: add contract validation CI workflow"
```

---

### Task 11: PR gate GitHub Actions workflow

**Files:**
- Create: `.github/workflows/product-guardian.yml`

- [ ] **Step 1: Create the workflow**

This workflow fires when PRs touch voice or app paths, triggering eng-product-qa via the Inngest API.

```yaml
name: Product Guardian PR Gate

on:
  pull_request:
    paths:
      - "web/**"
      - "knowledge/voice-pipeline/**"
      - "harness/src/voice/**"
      - "scripts/deploy-retell-agent.py"

jobs:
  guardian-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Fetch changed file paths for eng-product-qa to classify surfaces
      - name: Get Changed Files
        id: changed
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          FILES=$(gh pr view ${{ github.event.pull_request.number }} --json files --jq '.files[].path' | tr '\n' ',')
          echo "files=${FILES}" >> $GITHUB_OUTPUT

      # Emit calllock/pr.created event to Inngest
      # eng-product-qa's reactive trigger picks this up
      - name: Trigger Product Guardian
        env:
          INNGEST_EVENT_URL: ${{ secrets.INNGEST_EVENT_URL }}
          INNGEST_EVENT_KEY: ${{ secrets.INNGEST_EVENT_KEY }}
        run: |
          curl -X POST "$INNGEST_EVENT_URL" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $INNGEST_EVENT_KEY" \
            -d '{
              "name": "calllock/pr.created",
              "data": {
                "pr_number": ${{ github.event.pull_request.number }},
                "pr_url": "${{ github.event.pull_request.html_url }}",
                "branch": "${{ github.head_ref }}",
                "changed_file_paths": "${{ steps.changed.outputs.files }}"
              }
            }'

      # Wait for guardian to complete (polls agent_reports)
      # Filters by PR number in payload to handle concurrent PRs.
      # Timeout: 5 minutes (matches dispatch timeout)
      - name: Wait for Guardian Result
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        timeout-minutes: 6
        run: |
          PR=${{ github.event.pull_request.number }}
          echo "Waiting for Product Guardian to process PR #${PR}..."

          for i in $(seq 1 30); do
            sleep 10
            # Filter by agent, report type, and PR number in payload
            RESULT=$(curl -s \
              "${SUPABASE_URL}/rest/v1/agent_reports?agent_id=eq.eng-product-qa&report_type=eq.change-gate-review&payload->>pr_number=eq.${PR}&order=created_at.desc&limit=1&select=status,payload" \
              -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
              -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
              | jq -r ".[0].status // empty")

            if [ -n "$RESULT" ]; then
              echo "Guardian verdict: $RESULT"
              if [ "$RESULT" = "red" ]; then
                echo "::error::Product Guardian BLOCKED this PR"
                exit 1
              fi
              exit 0
            fi
          done

          echo "::error::Product Guardian timed out — BLOCK (safe default)"
          exit 1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/product-guardian.yml
git commit -m "feat: add Product Guardian PR gate GitHub Actions workflow"
```

---

## Phase 4: Visual Regression Testing (Task 12)

### Task 12: Visual regression baseline infrastructure

**Files:**
- Create: `knowledge/voice-pipeline/app-baselines/` (directory)
- Create: `knowledge/voice-pipeline/app-baselines/.gitkeep`

This task sets up the directory structure and documents the baseline process. The actual Playwright runner and screenshot comparison tooling depend on the headless-browser tool implementation, which is an implementation prerequisite listed in the design spec (blocked by Open Question 1: test tenant).

- [ ] **Step 1: Create baselines directory**

```bash
mkdir -p knowledge/voice-pipeline/app-baselines
touch knowledge/voice-pipeline/app-baselines/.gitkeep
```

- [ ] **Step 2: Add baseline README**

Create `knowledge/voice-pipeline/app-baselines/README.md`:

```markdown
# App Visual Regression Baselines

PNG screenshots of each page/element defined in app-contract.yaml.
Generated by eng-app during app health checks. Updated when app
contract changes are approved.

## How baselines work

1. eng-app takes screenshots during daily health checks
2. On subsequent checks, screenshots are pixel-diff compared to baselines
3. Threshold: 1% pixel difference (configurable per element)
4. On visual regression: side-by-side diff image included in report
5. When an app contract change is approved, eng-app regenerates baselines

## Files

- `calls-card.png` — Call card component on /calls page
- `calls-detail.png` — Call detail view on /calls page
- `overview-stats.png` — Stats summary on /overview page

## Prerequisites

- Playwright installed with chromium browser
- Test tenant with known data (see Open Question 1 in design spec)
- CallLock App running at accessible URL
```

- [ ] **Step 3: Commit**

```bash
git add knowledge/voice-pipeline/app-baselines/
git commit -m "feat: add visual regression baselines directory structure"
```

---

## Phase 5: Design Spec Sync (Task 13)

### Task 13: Update design spec references

**Files:**
- Modify: `docs/superpowers/specs/2026-03-18-product-guardian-design.md`

- [ ] **Step 1: Add implementation status section**

At the top of the design spec, add:
```markdown
## Implementation Status

| Component | Status | Plan Task | Files |
|---|---|---|---|
| eng-qa → eng-product-qa rename | ✅ Done | Task 1 | knowledge/worker-specs/eng-product-qa.yaml |
| Three-contract split | ✅ Done | Task 2 | voice-contract.yaml, app-contract.yaml, seam-contract.yaml v2.0 |
| eng-app worker spec | ✅ Done | Task 3 | knowledge/worker-specs/eng-app.yaml |
| agent_reports table | ✅ Done | Task 5 | supabase/migrations/052_agent_reports.sql |
| guardian_overrides table | ✅ Done | Task 6 | supabase/migrations/053_guardian_overrides.sql |
| Guardian dispatch event | ✅ Done | Task 7 | inngest/src/functions/guardian-dispatch.ts |
| Guardian watchdog | ✅ Done | Task 8 | inngest/src/functions/guardian-watchdog.ts |
| Contract validation CI | ✅ Done | Tasks 9-10 | scripts/validate-contracts.py, .github/workflows/contract-validate.yml |
| PR gate workflow | ✅ Done | Task 11 | .github/workflows/product-guardian.yml |
| Visual regression infra | ✅ Done | Task 12 | knowledge/voice-pipeline/app-baselines/ |
```

- [ ] **Step 2: Update Open Question 3 (alert channels)**

Now partially answered — the watchdog uses Slack webhooks. Update the note:
```
3. **Alert channels** — Watchdog sends Slack alerts + quest log entries.
   Discord integration planned (see Hermes integration design spec).
   SMS for critical alerts TBD.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-03-18-product-guardian-design.md
git commit -m "docs: add implementation status to Product Guardian design spec"
```

---

## Open Items (Not in This Plan)

These are explicitly deferred. They require separate planning sessions:

1. **Headless browser tool implementation** — Playwright runner that eng-app uses. Blocked by test tenant decision (Open Question 1).
2. **Self-healing auto-fix PR logic** — The template-based auto-fix system. Requires the contract validation tooling to be proven first.
3. **Agent report persistence from harness** — The actual code in `persist_node` that writes to `agent_reports`. Requires harness modifications.
4. **eng-product-qa change-gate-review task logic** — The LLM-powered PR classification and gating logic. Requires the contracts and dispatch infrastructure to exist first.
5. **eng-fullstack agent** — Referenced as issue assignee but doesn't exist yet (Open Question 4).
6. **Hermes integration** — Worker execution upgrade. See `docs/superpowers/specs/2026-03-18-hermes-agent-integration-design.md`.

---

## Summary

| Phase | Tasks | What It Delivers |
|---|---|---|
| 1: Migration & Contracts | 1–4 | eng-qa renamed, three contracts split, eng-app spec created |
| 2: Infrastructure | 5–8 | Supabase tables, Inngest events, watchdog cron |
| 3: Contract Validation CI | 9–11 | Static contract checking on every commit + PR gate |
| 4: Visual Regression | 12 | Baseline directory structure |
| 5: Design Spec Sync | 13 | Spec updated with implementation status |

Total: 13 tasks, ~48 steps. Each phase is independently committable and testable.

**Note:** Tasks 7 and 8 include steps to register functions in `inngest/src/index.ts`. Without this registration, Inngest won't discover or execute the guardian dispatch or watchdog functions.

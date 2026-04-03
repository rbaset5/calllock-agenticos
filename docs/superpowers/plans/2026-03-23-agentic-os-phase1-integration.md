# CallLock Agentic OS Phase 1 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first real CallLock operating-system slice by landing the voice Truth Plane, Governance wiring, Execution org split, founder read models, founder cockpit, and prompt-focused Improvement Lab without inventing a parallel backend.

**Architecture:** Phase 1 is backend-first and reuses existing runtime stores wherever possible. The voice locked-eval runner becomes the first constitutional gate, rollout boundaries live on governed task/run context, founder-facing truth is projected from existing records, and the web cockpit ships as a new 2D route group inside `office-dashboard` while the existing 3D page remains untouched.

**Tech Stack:** Python (harness, voice pipeline, FastAPI), JSON-in-`.yaml` worker specs, JSONL/YAML eval fixtures, Supabase/local repository stores, Next.js (`office-dashboard`), TypeScript, Playwright/lint/build verification

**Specs:** `docs/superpowers/specs/2026-03-23-founder-control-surface-design.md`, `docs/superpowers/specs/2026-03-23-truth-plane-design.md`, `docs/superpowers/specs/2026-03-23-governance-plane-design.md`, `docs/superpowers/specs/2026-03-23-execution-org-design.md`, `docs/superpowers/specs/2026-03-23-improvement-lab-design.md`

---

## Resolved Phase 1 Decisions

- The first binding truth loop is `voice extraction quality`.
- Phase 1 binding metrics are:
  - `safety_emergency_exact`
  - `urgency_tier_no_regression`
  - `route_no_regression`
  - `seam_survivability`
  - `empty_structured_output_rate`
- `customer_phone_exact` is tracked, but not binding until the gold dataset is mature.
- Phase 1 canary mode uses a fixed/manual canary snapshot; automated canary refresh starts in Phase 2.
- Rollout boundaries live in governed task/run context at `task.task_context.rollout_boundary` and are copied into approval payloads when escalated.
- Truth persistence uses existing stores:
  - rich artifacts in `artifacts`
  - historical run record in `eval_runs` with `level="core"` and `target="voice_locked"`
  - founder/daily summary projection in `agent_reports` with `report_type="voice-locked-eval"`
- `voice-truth` is a role and report identity in Phase 1; its runtime is the dedicated locked-eval runner, not the generic supervisor worker loop.
- The founder cockpit ships in `office-dashboard/src/app/founder/**`, not in customer `web/`, and the existing 3D office root page stays available.
- Improvement Lab v1 is limited to prompt body text, instruction ordering, few-shot/example wording, and prompt-level tool-description wording.

## File Structure

### Files to Create

| File | Responsibility |
|---|---|
| `decisions/architecture/DEC-2026-03-23-truth-org.md` | Binding architectural decision for Program / Execution / Truth / Governance split |
| `knowledge/worker-specs/voice-builder.yaml` | Execution-owned voice builder spec in repo-valid JSON format |
| `knowledge/worker-specs/voice-truth.yaml` | Founder-reporting truth worker spec in repo-valid JSON format |
| `knowledge/voice-pipeline/voice-eval-spec.yaml` | Locked voice eval contract |
| `evals/voice/gold_calls.jsonl` | Locked gold-call dataset |
| `evals/voice/canary_calls.jsonl` | Fixed/manual canary snapshot for Phase 1 |
| `evals/voice/README.md` | Labeling policy, dataset integrity, refresh rules |
| `harness/src/harness/evals/voice_metrics.py` | Pure metric and threshold helpers |
| `harness/src/harness/evals/voice_locked_eval.py` | Dedicated locked voice runner + persistence helpers |
| `harness/src/harness/verification/voice_gate.py` | Truth/gate bridge for governed voice changes |
| `harness/src/harness/improvement/voice_lab.py` | Prompt-focused Improvement Lab orchestration |
| `harness/tests/test_voice_eval_fixtures.py` | Fixture/spec validation tests |
| `harness/tests/test_voice_locked_eval.py` | Locked voice runner tests |
| `harness/tests/test_voice_gate.py` | Governance/truth gate tests |
| `harness/tests/test_founder_cockpit.py` | Founder read-model tests |
| `harness/tests/test_voice_lab.py` | Improvement Lab tests |
| `office-dashboard/src/app/founder/layout.tsx` | Founder cockpit layout shell |
| `office-dashboard/src/app/founder/page.tsx` | Home / Briefing route |
| `office-dashboard/src/app/founder/truth/page.tsx` | Truth route |
| `office-dashboard/src/app/founder/approvals/page.tsx` | Approvals route |
| `office-dashboard/src/app/founder/runs/page.tsx` | Runs route |
| `office-dashboard/src/app/founder/decisions/page.tsx` | Decisions route |
| `office-dashboard/src/components/founder/FounderShell.tsx` | Shared founder navigation and page framing |
| `office-dashboard/src/components/founder/BriefingView.tsx` | Home / Briefing renderer |
| `office-dashboard/src/components/founder/TruthView.tsx` | Truth renderer |
| `office-dashboard/src/components/founder/ApprovalsView.tsx` | Approvals renderer |
| `office-dashboard/src/components/founder/RunsView.tsx` | Runs renderer |
| `office-dashboard/src/components/founder/DecisionsView.tsx` | Decisions renderer |
| `office-dashboard/src/lib/founder-api.ts` | Thin fetch layer from cockpit UI to harness HTTP endpoints |
| `office-dashboard/.env.local.example` | Documents the harness base URL expected by the founder cockpit |

### Files to Modify

| File | Change |
|---|---|
| `AGENT.md` | Append truth-org addendum and active-loop ordering |
| `knowledge/worker-specs/_moc.md` | Register `voice-builder` and `voice-truth` |
| `knowledge/worker-specs/eng-ai-voice.yaml` | Deprecate as operational role, point to split roles |
| `knowledge/worker-specs/eng-product-qa.yaml` | Clarify truth/governance ownership and input chain |
| `scripts/validate-worker-specs.ts` | Keep compatibility with repo-valid JSON specs; no schema rewrite unless required |
| `harness/src/harness/evals/registry.py` | Discover `evals/voice/*.jsonl` and classify voice datasets |
| `harness/src/harness/evals/runner.py` | Dispatch `target="voice_locked"` to the dedicated voice runner |
| `harness/src/harness/evals/__init__.py` | Export the dedicated voice runner as needed |
| `harness/src/harness/approvals.py` | Copy rollout boundary and truth verdict into approval payloads |
| `harness/src/harness/ceo_tools.py` | Add founder truth read tool and retarget voice-eval trigger |
| `harness/src/harness/cockpit.py` | Add founder Home/Truth/Approvals/Runs/Decisions read models |
| `harness/src/harness/models.py` | Add request models for founder cockpit and voice lab if needed |
| `harness/src/harness/nodes/verification.py` | Promote voice-gate verdicts into runtime `verification` state |
| `harness/src/harness/server.py` | Expose founder cockpit endpoints and updated voice eval/improvement endpoints |
| `harness/src/harness/verification/__init__.py` | Export `run_voice_gate` helpers |
| `harness/src/harness/graphs/workers/eng_product_qa.py` | Call voice gate for governed voice/product changes |
| `harness/src/harness/improvement/experiments.py` | Reuse experiments table while storing richer artifacts for voice lab runs |
| `harness/tests/test_approvals.py` | Assert rollout boundary / truth verdict propagation |
| `harness/tests/test_evals.py` | Cover `target="voice_locked"` path |
| `harness/tests/test_persist_agent_report.py` | Cover `voice-locked-eval` report projection if helper lands there |
| `harness/tests/test_server.py` | Cover new founder endpoints and voice eval trigger behavior |
| `harness/tests/test_worker_registry.py` | Cover new worker ids / aliasing |
| `office-dashboard/src/app/page.tsx` | Add a founder cockpit entry link while keeping the 3D page intact |
| `office-dashboard/src/app/globals.css` | Add shared founder cockpit styling tokens if needed |

---

## Task 1: Land the Constitutional Repo Artifacts and Worker Split

**Files:**
- Create: `decisions/architecture/DEC-2026-03-23-truth-org.md`
- Create: `knowledge/worker-specs/voice-builder.yaml`
- Create: `knowledge/worker-specs/voice-truth.yaml`
- Modify: `AGENT.md`
- Modify: `knowledge/worker-specs/_moc.md`
- Modify: `knowledge/worker-specs/eng-ai-voice.yaml`
- Modify: `knowledge/worker-specs/eng-product-qa.yaml`
- Test: `harness/tests/test_worker_registry.py`

- [ ] **Step 1: Write the failing worker/org test**

Add assertions to `harness/tests/test_worker_registry.py` that the roster and worker-spec loader recognize:

```python
def test_voice_split_specs_exist() -> None:
    from harness.graphs.workers.base import load_worker_spec

    builder = load_worker_spec("voice-builder")
    truth = load_worker_spec("voice-truth")

    assert builder["worker_id"] == "voice-builder"
    assert truth["worker_id"] == "voice-truth"
```

Also assert the deprecated voice role still exists for compatibility:

```python
legacy = load_worker_spec("eng-ai-voice")
assert "deprecated" in legacy["mission"].lower()
```

- [ ] **Step 2: Run the worker registry test and validation to confirm the current gap**

Run:

```bash
pytest harness/tests/test_worker_registry.py -v
node scripts/validate-worker-specs.ts
```

Expected:
- `pytest` fails because `voice-builder.yaml` and `voice-truth.yaml` do not exist yet
- worker-spec validation still passes for the current roster

- [ ] **Step 3: Create the decision record**

Create `decisions/architecture/DEC-2026-03-23-truth-org.md` with:
- the four-function split
- explicit builder/judge separation
- eval loop order (`voice`, then `app`, then `outbound`)
- founder override rule

- [ ] **Step 4: Append the truth-org addendum to `AGENT.md`**

Append a short section that states:

```md
Voice extraction quality is the first active constitutional truth loop.
Builders may propose changes; only truth may certify them.
Governance owns approvals, rollout boundaries, quarantine, and overrides.
```

- [ ] **Step 5: Create repo-valid `voice-builder.yaml`**

Use the existing JSON-in-`.yaml` worker-spec format, not plain YAML. Include:

```json
{
  "schema_version": "1.1",
  "worker_id": "voice-builder",
  "version": "0.1.0",
  "department": "engineering",
  "supervisor": "eng-vp",
  "role": "worker",
  "mission": "Own prompt/config candidate generation for the voice workflow without certifying shipping quality.",
  "scope": {
    "can_do": [
      "propose prompt and prompt-adjacent config variants",
      "run offline voice lab experiments",
      "prepare candidate refs for truth evaluation"
    ],
    "cannot_do": [
      "declare a candidate passed",
      "edit the locked eval spec during evaluation",
      "ship or deploy voice changes directly"
    ]
  }
}
```

Fill in the rest of the required repo keys:
- `execution_scope`
- `inputs`
- `outputs`
- `tools_allowed`
- `success_metrics`
- `approval_boundaries`
- `dependencies`
- `git_workflow`

- [ ] **Step 6: Create repo-valid `voice-truth.yaml`**

Use the same JSON-in-`.yaml` structure. Key differences:
- `department: "truth"`
- `supervisor: "founder"`
- mission focused on locked evals, canary review, and veto authority
- `cannot_do` explicitly forbids prompt mutation and threshold lowering

- [ ] **Step 7: Update the existing worker specs**

In `knowledge/worker-specs/eng-ai-voice.yaml`:
- mark the role deprecated but still present for compatibility
- point human readers to `voice-builder` + `voice-truth`
- remove any implication that it is the final validator

In `knowledge/worker-specs/eng-product-qa.yaml`:
- state that it consumes truth outputs and owns cross-surface validation
- do not make it the voice-truth owner

In `_moc.md`:
- list the two new workers and their responsibilities

- [ ] **Step 8: Run validation and tests**

Run:

```bash
node scripts/validate-worker-specs.ts
pytest harness/tests/test_worker_registry.py -v
```

Expected:
- worker-spec validation passes
- the new worker test passes

- [ ] **Step 9: Commit**

```bash
git add AGENT.md decisions/architecture/DEC-2026-03-23-truth-org.md knowledge/worker-specs/
git commit -m "feat: establish truth org and voice worker split"
```

---

## Task 2: Add the Locked Voice Contract and Phase 1 Datasets

**Files:**
- Create: `knowledge/voice-pipeline/voice-eval-spec.yaml`
- Create: `evals/voice/gold_calls.jsonl`
- Create: `evals/voice/canary_calls.jsonl`
- Create: `evals/voice/README.md`
- Test: `harness/tests/test_voice_eval_fixtures.py`

- [ ] **Step 1: Write failing fixture validation tests**

Create `harness/tests/test_voice_eval_fixtures.py` with checks like:

```python
from pathlib import Path
import json
import yaml


def test_voice_eval_spec_exists() -> None:
    path = Path("knowledge/voice-pipeline/voice-eval-spec.yaml")
    assert path.exists()


def test_gold_calls_fixture_has_cases() -> None:
    path = Path("evals/voice/gold_calls.jsonl")
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(lines) >= 10
```

Include one schema assertion for a case:

```python
assert {"case_id", "segment", "expected"} <= set(lines[0])
```

- [ ] **Step 2: Run the new fixture test to verify it fails**

Run:

```bash
pytest harness/tests/test_voice_eval_fixtures.py -v
```

Expected: fail because the files do not exist yet.

- [ ] **Step 3: Create `voice-eval-spec.yaml`**

Include the Phase 1 contract:
- binding metrics now
- advisory metrics now
- future binding metrics
- `current production` as the no-regression baseline
- fixed/manual canary snapshot rule
- pass/block/escalate semantics

Keep the file human-readable YAML, because it is a truth contract, not a worker spec.

- [ ] **Step 4: Create the gold dataset**

Create `evals/voice/gold_calls.jsonl` with at least 10 bootstrap cases for Phase 1 wiring. Each line should follow:

```json
{
  "case_id": "voice-seed-001",
  "segment": "urgent",
  "input_source": "retell_full_call",
  "retell_call_fixture_path": "tests/fixtures/voice/seed-001.json",
  "expected": {
    "urgency_tier": "urgent",
    "route": "dispatch",
    "safety_emergency": false,
    "required_fields": {
      "customer_name": "Jane Doe",
      "problem_description": "No heat on first floor"
    }
  }
}
```

Bootstrap with existing seed-set examples where possible. Do not pretend the bootstrap set is mature.

- [ ] **Step 5: Create the Phase 1 canary snapshot**

Create `evals/voice/canary_calls.jsonl` as a fixed snapshot of recent representative calls. Phase 1 should treat this file as manually refreshed between evaluation cycles.

- [ ] **Step 6: Add dataset rules**

Create `evals/voice/README.md` and document:
- the dataset cannot be edited in the same change under evaluation
- gold vs canary roles
- labeling policy for binding vs advisory fields
- refresh procedure for the canary snapshot

- [ ] **Step 7: Run the fixture tests**

Run:

```bash
pytest harness/tests/test_voice_eval_fixtures.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add knowledge/voice-pipeline/voice-eval-spec.yaml evals/voice/ harness/tests/test_voice_eval_fixtures.py
git commit -m "feat: add locked voice eval contract and phase1 datasets"
```

---

## Task 3: Build the Dedicated Voice Truth Runner and Persistence Path

**Files:**
- Create: `harness/src/harness/evals/voice_metrics.py`
- Create: `harness/src/harness/evals/voice_locked_eval.py`
- Modify: `harness/src/harness/evals/registry.py`
- Modify: `harness/src/harness/evals/runner.py`
- Modify: `harness/src/harness/evals/__init__.py`
- Test: `harness/tests/test_voice_locked_eval.py`
- Test: `harness/tests/test_evals.py`

- [ ] **Step 1: Write the failing locked-eval tests**

Create `harness/tests/test_voice_locked_eval.py` with focused unit tests:

```python
def test_voice_locked_eval_blocks_on_binding_regression() -> None:
    result = run_voice_locked_eval(candidate_config_ref="candidate-a", baseline_config_ref="prod-a")
    assert result["verdict"] == "block"
```

Add a pass-path test:

```python
def test_voice_locked_eval_persists_agent_report_summary() -> None:
    result = run_voice_locked_eval(candidate_config_ref="candidate-ok", baseline_config_ref="prod-a")
    assert result["report_type"] == "voice-locked-eval"
```

Update `harness/tests/test_evals.py` with:

```python
def test_voice_locked_target_dispatches() -> None:
    result = run_eval_suite(level="core", target="voice_locked")
    assert result["target"] == "voice_locked"
```

- [ ] **Step 2: Run the eval tests to capture the failure**

Run:

```bash
pytest harness/tests/test_voice_locked_eval.py harness/tests/test_evals.py -v
```

Expected: fail because the dedicated runner does not exist yet.

- [ ] **Step 3: Implement pure voice metric helpers**

In `voice_metrics.py`, add pure functions for:
- loading the eval spec
- loading JSONL datasets
- computing binding and advisory metric summaries
- computing threshold checks
- mapping verdict to `overall_score`

Use a simple score mapping so the existing `eval_runs` table can be reused without migration:

```python
VERDICT_TO_SCORE = {
    "pass": 1.0,
    "escalate": 0.5,
    "block": 0.0,
}
```

- [ ] **Step 4: Implement the dedicated runner**

In `voice_locked_eval.py`, implement:
- replay of the extraction path against the gold dataset
- threshold evaluation
- optional Phase 1 canary evaluation against the fixed snapshot
- creation of a rich artifact via `create_artifact(...)`
- persistence to `eval_runs` with:
  - `level="core"`
  - `target="voice_locked"`
  - `overall_score=VERDICT_TO_SCORE[verdict]`
  - `dataset_results` containing the structured summary payload
- projection to `agent_reports` with:
  - `agent_id="voice-truth"`
  - `report_type="voice-locked-eval"`
  - `status` mapped to `green|yellow|red`

- [ ] **Step 5: Extend the eval registry and runner**

In `registry.py`:
- keep current `*.json` discovery for existing workers
- add discovery for `evals/voice/*.jsonl`
- tag those datasets as `worker_id="voice"` and metric by file stem

In `runner.py`:
- if `target == "voice_locked"`, bypass the generic boolean suite and call `run_voice_locked_eval(...)`
- preserve existing behavior for everything else

- [ ] **Step 6: Run the tests**

Run:

```bash
pytest harness/tests/test_voice_eval_fixtures.py harness/tests/test_voice_locked_eval.py harness/tests/test_evals.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add harness/src/harness/evals/ harness/tests/test_voice_eval_fixtures.py harness/tests/test_voice_locked_eval.py harness/tests/test_evals.py
git commit -m "feat: add locked voice truth runner and persistence"
```

---

## Task 4: Wire Governance, Rollout Boundaries, and the Voice Gate

**Files:**
- Create: `harness/src/harness/verification/voice_gate.py`
- Modify: `harness/src/harness/verification/__init__.py`
- Modify: `harness/src/harness/approvals.py`
- Modify: `harness/src/harness/nodes/verification.py`
- Modify: `harness/src/harness/graphs/workers/eng_product_qa.py`
- Modify: `harness/src/harness/server.py`
- Test: `harness/tests/test_voice_gate.py`
- Test: `harness/tests/test_approvals.py`

- [ ] **Step 1: Write the failing governance/gate tests**

Create `harness/tests/test_voice_gate.py` with cases like:

```python
def test_voice_gate_blocks_failed_binding_metrics() -> None:
    result = run_voice_gate({"changed_files": ["harness/src/voice/extraction/pipeline.py"]})
    assert result["verdict"] == "block"


def test_voice_gate_escalates_borderline_canary() -> None:
    result = run_voice_gate({"changed_files": ["scripts/deploy-retell-agent.py"]})
    assert result["verdict"] == "escalate"
```

Extend `harness/tests/test_approvals.py` to assert escalation payload copies rollout boundary:

```python
assert request["payload"]["rollout_boundary"] == "canary_only"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest harness/tests/test_voice_gate.py harness/tests/test_approvals.py -v
```

Expected: fail because the voice gate and rollout-boundary propagation do not exist yet.

- [ ] **Step 3: Implement `voice_gate.py`**

Add:
- path classifier for voice-sensitive changes
- call into `run_voice_locked_eval(...)`
- final `pass|block|escalate` verdict for the voice path
- returned evidence refs from the truth artifact

Use:

```python
VOICE_GATED_PATHS = (
    "knowledge/voice-pipeline/",
    "knowledge/industry-packs/",
    "harness/src/voice/",
    "scripts/deploy-retell-agent.py",
)
```

- [ ] **Step 4: Wire rollout boundary propagation**

In `approvals.py`, enrich the approval payload:

```python
"payload": {
    ...
    "rollout_boundary": state.get("task", {}).get("task_context", {}).get("rollout_boundary"),
    "truth_gate": state.get("verification", {}),
}
```

Do not introduce a new table. Keep the rollout boundary canonical in task/run context and project it when escalated.

- [ ] **Step 5: Seed rollout boundaries for governed voice/product changes**

Add a default boundary assignment in the request-construction path for governed work:
- `eval_only` for new voice/product change reviews
- `canary_only` only after an explicit approved promotion
- `approved_for_ship` only after the truth pass and governance allow path complete

At minimum, implement this in the direct server/build-task path and normalize missing values to `eval_only` inside `eng_product_qa` so the runtime never evaluates a governed voice change without a boundary.

- [ ] **Step 6: Call the voice gate from `eng_product_qa`**

In `eng_product_qa.py`:
- if `change-gate-review` touches voice-governed paths, call `run_voice_gate(...)`
- include the resulting truth verdict and artifact refs in the returned summary
- keep non-voice contract checks working as they do today

- [ ] **Step 7: Promote voice-gate verdicts into runtime `verification` state**

In `harness/src/harness/nodes/verification.py`, detect gated Product Guardian outputs and translate them into the canonical verification payload used by the supervisor:

```python
{
    "passed": verdict == "pass",
    "verdict": verdict,
    "reasons": reasons,
    "findings": findings,
    "artifact_refs": artifact_refs,
}
```

This is the enforcement seam that makes approvals, blocks, and dispatch control actually work. Do not leave the voice gate as worker-output decoration.

- [ ] **Step 8: Run tests**

Run:

```bash
pytest harness/tests/test_voice_gate.py harness/tests/test_approvals.py harness/tests/test_eng_product_qa.py harness/tests/test_verification_outcomes.py -v
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add harness/src/harness/verification/ harness/src/harness/approvals.py harness/src/harness/graphs/workers/eng_product_qa.py harness/tests/test_voice_gate.py harness/tests/test_approvals.py
git commit -m "feat: wire voice truth gate into governance flow"
```

---

## Task 5: Add Founder Read Models, CEO Tooling, and Cockpit Endpoints

**Files:**
- Modify: `harness/src/harness/cockpit.py`
- Modify: `harness/src/harness/ceo_tools.py`
- Modify: `harness/src/harness/models.py`
- Modify: `harness/src/harness/server.py`
- Test: `harness/tests/test_founder_cockpit.py`
- Test: `harness/tests/outbound/test_ceo_tools.py`
- Test: `harness/tests/test_server.py`

- [ ] **Step 1: Write the failing founder read-model tests**

Create `harness/tests/test_founder_cockpit.py` with:

```python
def test_founder_home_projection_prioritizes_exceptions() -> None:
    payload = founder_home_view()
    assert "briefing" in payload
    assert "approvals" in payload
    assert "truth_status" in payload
```

Add:

```python
def test_truth_view_marks_non_voice_loops_not_active_yet() -> None:
    payload = founder_truth_view()
    assert payload["loops"]["app"]["state"] == "not_active_yet"
```

Add explicit source-of-truth coverage:

```python
def test_founder_home_reads_active_priority_from_agent_md() -> None:
    payload = founder_home_view()
    assert payload["active_priority"]["source"] == "AGENT.md"


def test_founder_decisions_include_guardian_overrides() -> None:
    payload = founder_decisions_view()
    assert "overrides" in payload
```

Extend `harness/tests/outbound/test_ceo_tools.py` for the new voice truth tool:

```python
def test_read_voice_truth_status_returns_latest_projection() -> None:
    payload = read_voice_truth_status(tenant_id="...")
    assert "latest_verdict" in payload
```

Extend `harness/tests/test_server.py` to cover the approval mutations the cockpit will call:

```python
def test_founder_approval_actions_support_approve_reject_and_cancel(client):
    ...
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest harness/tests/test_founder_cockpit.py harness/tests/outbound/test_ceo_tools.py harness/tests/test_server.py -v
```

Expected: fail because the new projections and endpoints do not exist yet.

- [ ] **Step 3: Implement the founder read-model functions**

In `cockpit.py`, add:
- `founder_home_view(...)`
- `founder_truth_view(...)`
- `founder_approvals_view(...)`
- `founder_runs_view(...)`
- `founder_decisions_view(...)`

Rules:
- derive from existing `approval_requests`, `agent_reports`, `jobs`, repo `decisions/`, repo `errors/`, `guardian_overrides`, and `AGENT.md`
- do not create a new durable aggregation store
- mark non-voice loops as `not_active_yet`

- [ ] **Step 4: Extend CEO tools**

In `ceo_tools.py`:
- add `read_voice_truth_status(...)`
- change `trigger_voice_eval(...)` to call the locked truth path directly (`run_eval_suite(level="core", target="voice_locked")`) or queue an explicit eval request handled by the server, rather than dispatching a generic `voice-truth` supervisor worker

- [ ] **Step 5: Expose HTTP endpoints**

In `server.py`, add:

```python
@app.get("/cockpit/founder/home")
@app.get("/cockpit/founder/truth")
@app.get("/cockpit/founder/approvals")
@app.get("/cockpit/founder/runs")
@app.get("/cockpit/founder/decisions")
```

Keep these read-only in Phase 1.

- [ ] **Step 6: Run tests**

Run:

```bash
pytest harness/tests/test_founder_cockpit.py harness/tests/outbound/test_ceo_tools.py harness/tests/test_server.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add harness/src/harness/cockpit.py harness/src/harness/ceo_tools.py harness/src/harness/models.py harness/src/harness/server.py harness/tests/test_founder_cockpit.py harness/tests/outbound/test_ceo_tools.py harness/tests/test_server.py
git commit -m "feat: add founder truth projections and cockpit endpoints"
```

---

## Task 6: Build the Founder Cockpit in `office-dashboard`

**Files:**
- Create: `office-dashboard/src/app/founder/layout.tsx`
- Create: `office-dashboard/src/app/founder/page.tsx`
- Create: `office-dashboard/src/app/founder/truth/page.tsx`
- Create: `office-dashboard/src/app/founder/approvals/page.tsx`
- Create: `office-dashboard/src/app/founder/runs/page.tsx`
- Create: `office-dashboard/src/app/founder/decisions/page.tsx`
- Create: `office-dashboard/src/components/founder/FounderShell.tsx`
- Create: `office-dashboard/src/components/founder/BriefingView.tsx`
- Create: `office-dashboard/src/components/founder/TruthView.tsx`
- Create: `office-dashboard/src/components/founder/ApprovalsView.tsx`
- Create: `office-dashboard/src/components/founder/RunsView.tsx`
- Create: `office-dashboard/src/components/founder/DecisionsView.tsx`
- Create: `office-dashboard/src/lib/founder-api.ts`
- Create: `office-dashboard/.env.local.example`
- Modify: `office-dashboard/src/app/page.tsx`
- Modify: `office-dashboard/src/app/globals.css`

- [ ] **Step 1: Create the founder API client**

In `office-dashboard/src/lib/founder-api.ts`, add fetch helpers:

```ts
export async function getFounderHome() {
  return fetchJson(`${process.env.NEXT_PUBLIC_HARNESS_BASE_URL}/cockpit/founder/home`);
}
```

Repeat for truth, approvals, runs, and decisions.

Create `office-dashboard/.env.local.example` with:

```bash
NEXT_PUBLIC_HARNESS_BASE_URL=http://localhost:8000
```

Use a small shared helper that throws a clear error if the env var is missing.

This is the Phase 1 integration path. Do not rely on same-origin relative fetches unless a later rewrite/proxy is added explicitly.

- [ ] **Step 2: Create the shared shell**

In `FounderShell.tsx`, add:
- compact nav for the five routes
- active priority banner
- shared right-drawer slot for detail inspection

- [ ] **Step 3: Build the five Phase 1 routes**

Implement:
- `page.tsx` for `Home / Briefing`
- `truth/page.tsx`
- `approvals/page.tsx`
- `runs/page.tsx`
- `decisions/page.tsx`

Each page should render server-fetched data through a dedicated component.

- [ ] **Step 4: Wire first-class approval actions**

In `ApprovalsView.tsx`, make the required v1 founder actions explicit:
- `Approve` -> `POST /approvals/{id}` with `status="approved"`
- `Deny` -> `POST /approvals/{id}` with `status="rejected"`
- `Escalate / defer` -> `POST /approvals/{id}` with `status="cancelled"` and a note explaining it was deferred by the founder

Do not ship a passive approvals queue.

- [ ] **Step 5: Keep the 3D dashboard available, but not primary**

In `office-dashboard/src/app/page.tsx`, add a clear link/button into `/founder` and leave the current 3D scene intact.

- [ ] **Step 6: Style for dense, serious, exception-first operation**

Update `globals.css` only as needed to support:
- compact data cards
- strong hierarchy
- no ornamental dashboard chrome

- [ ] **Step 7: Verify the app compiles**

Run:

```bash
cd office-dashboard
npm run lint
npm run build
```

Expected:
- lint passes
- production build succeeds

- [ ] **Step 8: Manually smoke the approval actions**

With the harness running locally, verify that:
- approving a pending approval updates the row and removes it from the queue
- denying a pending approval updates the row to rejected
- deferring a pending approval updates the row to cancelled with the founder note

- [ ] **Step 9: Commit**

```bash
git add office-dashboard/src
git commit -m "feat: add founder cockpit routes to office dashboard"
```

---

## Task 7: Add the Prompt-Focused Improvement Lab and Promotion Boundary

**Files:**
- Create: `harness/src/harness/improvement/voice_lab.py`
- Modify: `harness/src/harness/improvement/experiments.py`
- Modify: `harness/src/harness/ceo_tools.py`
- Modify: `harness/src/harness/server.py`
- Test: `harness/tests/test_voice_lab.py`
- Test: `harness/tests/test_improvement_and_content.py`

- [ ] **Step 1: Write the failing voice-lab tests**

Create `harness/tests/test_voice_lab.py`:

```python
def test_voice_lab_keeps_winner_and_returns_promotion_candidate() -> None:
    result = run_voice_lab_experiment(...)
    assert result["outcome"] == "keep"
    assert "promotion_candidate" in result
```

Add a boundary test:

```python
def test_voice_lab_rejects_non_prompt_adjacent_mutation() -> None:
    with pytest.raises(ValueError):
        run_voice_lab_experiment(mutation={"field": "temperature"})
```

- [ ] **Step 2: Run the failing lab tests**

Run:

```bash
pytest harness/tests/test_voice_lab.py harness/tests/test_improvement_and_content.py -v
```

Expected: fail because the voice-lab orchestration does not exist yet.

- [ ] **Step 3: Implement the voice lab**

In `voice_lab.py`, implement a controlled loop that:
- validates mutation surfaces are Phase 1-legal
- runs offline comparisons
- stores experiment summary in `experiments`
- stores rich experiment details in `artifacts`
- returns `keep|revert` plus an optional `promotion_candidate`

Allowed Phase 1 mutation surfaces:
- prompt body text
- instruction ordering
- few-shot/example wording
- prompt-level tool-description wording

- [ ] **Step 4: Reuse existing experiment storage**

In `experiments.py`, keep `experiments` as the summary log.
Do not add a new table in Phase 1.
Add artifact creation for richer comparison payloads if the helper lives there.

- [ ] **Step 5: Expose founder/operator entry points**

In `ceo_tools.py` and `server.py`:
- add a `run_voice_lab_experiment(...)` entry
- keep promotion explicit; the lab does not call the locked truth gate automatically

- [ ] **Step 6: Run tests**

Run:

```bash
pytest harness/tests/test_voice_lab.py harness/tests/test_improvement_and_content.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add harness/src/harness/improvement/ harness/src/harness/ceo_tools.py harness/src/harness/server.py harness/tests/test_voice_lab.py harness/tests/test_improvement_and_content.py
git commit -m "feat: add prompt-focused voice improvement lab"
```

---

## Task 8: Full-System Verification and Handoff

**Files:**
- Modify as needed from prior tasks only

- [ ] **Step 1: Run the Python test sweep for the new slice**

Run:

```bash
pytest \
  harness/tests/test_worker_registry.py \
  harness/tests/test_voice_eval_fixtures.py \
  harness/tests/test_voice_locked_eval.py \
  harness/tests/test_voice_gate.py \
  harness/tests/test_founder_cockpit.py \
  harness/tests/test_voice_lab.py \
  harness/tests/test_approvals.py \
  harness/tests/test_evals.py \
  harness/tests/test_server.py \
  harness/tests/outbound/test_ceo_tools.py \
  harness/tests/test_improvement_and_content.py -v
```

Expected: all pass.

- [ ] **Step 2: Run worker-spec validation**

Run:

```bash
node scripts/validate-worker-specs.ts
```

Expected: `Validated ... worker specs.`

- [ ] **Step 3: Run office-dashboard verification**

Run:

```bash
cd office-dashboard
npm run lint
npm run build
```

Expected: both commands succeed.

- [ ] **Step 4: Smoke the founder endpoints locally**

Run the harness server, then verify:

```bash
curl http://localhost:8000/cockpit/founder/home
curl http://localhost:8000/cockpit/founder/truth
curl http://localhost:8000/cockpit/founder/approvals
```

Expected:
- JSON payloads render
- voice truth is active
- app/outbound/compliance are marked `not_active_yet`

- [ ] **Step 5: Write implementation notes**

Update the plan or a short execution note with:
- any deliberately deferred items
- any places where the seed dataset still limits constitutional authority
- any follow-up needed for Phase 2 canary automation and app-truth rollout

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: land calllock agentic os phase1 foundation"
```

---

## Acceptance Checklist

- `voice-builder` and `voice-truth` exist and validate in the repo’s current worker-spec format
- the locked voice eval contract and bootstrap datasets exist
- a dedicated voice truth runner emits `pass|block|escalate`
- governed voice changes can be blocked or escalated through `eng-product-qa`
- rollout boundaries live in task/run context and are copied into approval payloads
- founder read models are exposed through harness endpoints
- the founder cockpit exists as a separate 2D route group in `office-dashboard`
- the Improvement Lab can keep/revert prompt candidates without claiming shipping authority

## Out of Scope for This Plan

- app truth as a constitutional gate
- outbound truth as a constitutional gate
- generic cross-surface override generalization beyond existing guardian records
- automated canary snapshot management
- broad extraction-code mutation in the Improvement Lab
- turning the 3D office into the main founder operating surface

# Truth Plane Design

**Date:** 2026-03-23
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [CallLock AgentOS Architecture](calllock-agentos-architecture.md), [Product Guardian Design](2026-03-18-product-guardian-design.md), [Founder Control Surface Design](2026-03-23-founder-control-surface-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Design the first real Truth Plane for CallLock by making voice extraction quality the first constitutional evaluation loop. The Truth Plane's primary job in v1 is to serve as a shipping gate for voice changes. It must decide whether a proposed change is allowed to continue by producing one of three outcomes:

- `pass`
- `block`
- `escalate`

This spec intentionally adopts a hybrid rollout. A small set of critical metrics becomes binding immediately, while broader quality metrics remain advisory until the gold dataset matures.

In v1, the Truth Plane's `pass` / `block` / `escalate` output is the final gate verdict for the voice shipping path.

## Goals

- Make voice extraction quality the first real locked eval loop
- Turn truth into a shipping gate, not just reporting
- Separate evaluation from builder judgment
- Bind only the metrics the current data can responsibly support
- Preserve room to ratchet more metrics into binding status as the dataset matures

## Non-Goals

- Solving all future truth loops in one spec
- Building a general-purpose eval platform for every worker
- Replacing health checks with the entire truth system
- Making every metric binding immediately
- Folding truth, governance, and execution into one runtime component
- Treating production detection events as constitutional truth

## Recommendation

Use a `hybrid constitutional rollout`.

That means:

- a small set of critical voice metrics is binding now
- broader quality metrics are computed and surfaced now
- additional metrics become binding only after the labeled gold set is strong enough

This is preferable to a fully advisory system because it creates a real constitutional boundary now. It is preferable to a fully locked broad score stack because the current dataset and existing eval surfaces are not yet mature enough to justify a comprehensive binding contract.

## Purpose

The Truth Plane exists to answer one question:

`Did the proposed voice change improve reality enough to be allowed to ship?`

It is not:

- broad analytics
- a generic reporting layer
- a builder-owned health dashboard
- free-form human judgment dressed up as evaluation

Its primary job in v1 is `shipping gate first`.

## Current Repo Grounding

The Truth Plane design must be grounded in the current voice/eval surfaces:

- voice field contract in [`knowledge/voice-pipeline/voice-contract.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/voice-pipeline/voice-contract.yaml)
- seam contract in [`knowledge/voice-pipeline/seam-contract.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/voice-pipeline/seam-contract.yaml)
- existing seed eval set in [`knowledge/voice-pipeline/eval/golden-set.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/voice-pipeline/eval/golden-set.yaml)
- current health-check logic in [`harness/src/voice/services/health_check.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/voice/services/health_check.py)
- current scorecard logic in [`harness/src/voice/extraction/call_scorecard.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/voice/extraction/call_scorecard.py)

This spec does not discard those pieces. It reorganizes them into a constitutional truth loop with explicit authority and outputs.

## Truth Plane Objects

The Truth Plane should be built around five core objects.

### 1. Eval Spec

The locked scoring contract. This is the canonical definition of:

- which datasets are used
- which metrics are binding
- which metrics are advisory
- which thresholds apply
- which shipping rules apply

It must be versioned and locked during a single evaluation run.

### 2. Gold Dataset

A human-labeled dataset used for deterministic replay and grading.

Rules:

- not editable as part of the same change being judged
- versioned in git
- expanded between runs, never during a run
- initially seeded from the current repo eval set and then matured aggressively

### 3. Canary Dataset

A recent, smaller real-call comparison set used after a candidate clears the binding gold checks.

Rules:

- refreshed between runs
- chosen from recent calls
- used to catch live-shape regressions that the gold set may miss

Phase 1 canary mode:

- use a fixed/manual canary snapshot
- do not automate canary refresh yet
- begin automated canary dataset management in Phase 2

### 4. Eval Result

The canonical output of a truth run. It must include:

- outcome: `pass`, `block`, or `escalate`
- failed binding metrics
- advisory metric summary
- baseline reference
- candidate reference
- evidence links

In Phase 1, truth results should persist into the existing `agent_reports` surface using a dedicated locked-eval report type, with `artifact_refs` pointing to any richer eval artifacts.

### 5. Gate Decision

The shipping-path decision emitted by the Truth Plane runner itself in v1.

For the first locked voice loop, Truth and gate verdict are the same object:

- Truth decides what is real
- that truth verdict is the final shipping-path gate result for voice in v1

Governance still owns surrounding approval boundaries and overrides, but it does not remap a truth verdict into a separate voice gate verdict in v1.

## Locked Scope in v1

Because the rollout is hybrid, the v1 truth contract is split into three groups.

### Binding Metrics Now

These can veto shipping immediately:

- `safety_emergency_exact`
- `urgency_tier_no_regression`
- `route_no_regression`
- `seam_survivability`
- `empty_structured_output_rate`

These are the operationally dangerous failure modes that should become non-negotiable immediately.

### Advisory Metrics Now

These must be computed and surfaced, but they do not veto on their own in early v1:

- `required_field_recall`
- `segment-specific recall`
- `warning_rate_delta`
- `classification exactness outside the critical subset`
- `booking_or_callback_quality`
- `quality_score movement`

### Future Binding Metrics

These should move into the binding set once the gold dataset is mature enough:

- `customer_phone_exact`
- broader field recall floors
- segment minimums
- booking or callback outcome exactness
- stronger canary business-quality thresholds

## Binding Metric Definitions

### `safety_emergency_exact`

Emergency classification must not regress on safety-sensitive calls.

Why binding now:
This is a trust and safety boundary, not just a product-quality preference.

### `urgency_tier_no_regression`

The candidate must not perform worse than the baseline on urgency classification over the locked evaluation set.

Why no-regression rather than hard global floor initially:
The seed dataset is not yet mature enough for a wide constitutional floor, but it is sufficient to stop clear backwards movement.

Baseline rule in v1:
The baseline reference for all `no_regression` metrics is the current production voice configuration that the business is actively relying on.

### `route_no_regression`

The candidate must not perform worse than the baseline on routing decisions across the locked evaluation set.

### `seam_survivability`

Every required downstream field in scope must continue to survive through storage and app mapping.

This must be tied directly to the seam contract, not inferred loosely.

### `empty_structured_output_rate`

The candidate must not exceed the configured threshold for outputs that technically run but produce unusable structured data.

## Advisory Metrics

Advisory metrics exist to make the Truth Plane useful before the full gold set is mature enough to constitutionalize every quality dimension.

These metrics should be:

- computed on every run
- included in the eval result
- shown to founder and truth operators
- candidates for future binding promotion

They should not be silently ignored, but they should not automatically veto shipping until the labeled dataset can support that authority.

## Truth Plane Flow

The recommended flow for a voice candidate change is:

### 1. Candidate proposed

A builder proposes a prompt, extraction, taxonomy, routing, or configuration change.

### 2. Locked eval run starts

The Truth Plane loads:

- current eval spec
- current gold dataset
- baseline reference
- candidate reference

### 3. Replay and scoring

The candidate is replayed through the extraction pipeline on the gold dataset. The runner computes:

- binding metrics
- advisory metrics
- seam validation results

### 4. First decision

- if any binding metric fails: `block`
- if binding metrics pass but results are weak, contradictory, or underpowered: `escalate`
- if binding metrics pass cleanly: continue to canary

### 5. Canary step

Run the recent-call canary sample.

- if canary shows a clear regression: `block` or `escalate` depending on severity
- if canary is clean: `pass`

### 6. Output

The Truth Plane emits a canonical eval result artifact for governance and founder inspection.

## Output Contract

The eval result should have this logical shape:

- `run_id`
- `suite`
- `baseline_reference`
- `candidate_reference`
- `outcome`
- `failed_binding_metrics`
- `binding_metric_results`
- `advisory_metric_results`
- `segment_summaries`
- `canary_summary`
- `recommendation`
- `artifact_refs`

Where:

- `outcome` is one of `pass`, `block`, `escalate`
- `recommendation` is for governance consumption, not a builder-owned conclusion

## Pass / Block / Escalate Semantics

### `pass`

Conditions:

- all binding metrics pass
- canary does not show material regression
- no unresolved seam break exists

Meaning:

- candidate is eligible to continue toward shipping

### `block`

Conditions:

- any binding metric fails
- safety-critical regression appears
- hard seam break occurs
- empty structured output threshold is exceeded

Meaning:

- candidate does not ship
- rework required

### `escalate`

Conditions:

- binding metrics pass, but advisory metrics materially contradict the apparent pass
- canary is borderline or unclear
- dataset coverage is insufficient for a confident pass

Meaning:

- candidate does not auto-ship
- additional review or investigation is required

### Initial Escalate Policy

The initial v1 `escalate` triggers are:

- `borderline_canary`: the canary does not clearly fail, but shows enough movement that the result should not auto-pass
- `insufficient_dataset_coverage`: the relevant evaluation slice is too thin to treat the apparent pass as trustworthy
- `advisory_material_contradiction`: binding metrics pass, but advisory metrics indicate meaningful quality degradation that should be reviewed before shipping

These triggers should be represented explicitly in the eval result rather than hidden behind a generic `escalate` label.

## Data Strategy

### Seed-to-constitution path

The repo already has a small seed set in [`golden-set.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/voice-pipeline/eval/golden-set.yaml). That should not be treated as a mature constitutional dataset.

Instead, the path should be:

1. use the seed set to bootstrap the locked runner
2. bind only a narrow critical metric set initially
3. expand and relabel the gold set quickly
4. ratchet more metrics from advisory to binding as evidence quality improves

### Dataset policy

- the gold set is human-labeled
- the candidate change cannot modify the eval set being used to judge it
- canary refresh happens between runs
- any dataset correction that would materially change a previous judgment should be treated as a real governance event, not a casual cleanup

## Relationship to Existing Health Checks

The current health checks remain useful, but they are not the constitutional truth loop.

Health checks are for:

- ongoing monitoring
- trend detection
- drift visibility
- diagnostics

The Truth Plane is for:

- locked evaluation
- shipping eligibility
- binding pass/block/escalate outputs

The two systems should share logic where useful, but they should not be confused with each other.

## Relationship to Detection Plane

The Detection Plane and the Truth Plane are intentionally separate.

Detection may say:

- this issue deserves investigation
- this signal is probably noise
- this issue is already known

Truth may say:

- this candidate passes
- this candidate blocks
- this candidate escalates

Detection can trigger investigation or candidate generation, but it does not become a truth verdict by itself.

## Relationship to Generic Eval Runner

The current generic runner in [`runner.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/evals/runner.py) is too shallow to serve as the main constitutional truth runner for voice.

It is still acceptable for:

- simple worker evals
- non-constitutional evaluation tasks
- early generic coverage

But the voice truth loop needs its own dedicated runner with richer outputs and explicit binding/advisory semantics.

## What Not To Do

The Truth Plane should explicitly avoid:

- using the generic boolean-pass eval model as the constitutional voice gate
- allowing builders to grade their own changes
- making the entire truth loop LLM-judge-driven
- binding broad thresholds before the dataset can support them
- changing the eval spec inside the same change being judged
- treating drift/health reports as equivalent to constitutional truth

## Phased Delivery

### Phase 1

- define the locked voice eval spec
- formalize binding vs advisory metrics
- bootstrap the dedicated truth runner against the seed set
- emit canonical `pass / block / escalate` outputs
- wire the truth output into the voice shipping path

### Phase 2

- expand the gold dataset substantially
- add automated canary dataset management
- ratchet more advisory metrics into binding metrics
- improve founder-facing truth summaries

### Phase 3

- stabilize voice truth as a mature constitutional loop
- use the same pattern to design app truth
- later apply the pattern to outbound truth

## Risks

### Risk: false constitution

If too many weakly supported metrics become binding too early, the Truth Plane will look rigorous while actually being fragile.

### Risk: advisory purgatory

If the binding set stays too small for too long, truth will not gain real authority and the company will keep hand-waving broader quality failures.

### Risk: health-check confusion

If operators treat health reports as equivalent to locked eval results, the system will blur monitoring and constitutional judgment.

## Open Questions for Planning

- What exact file path and format should the locked eval spec use in the repo?
- Should the seed dataset stay in its current YAML form initially or be normalized immediately into a stronger fixture format?
- Which existing extraction replay path should the dedicated truth runner call directly?

## Acceptance Criteria

This design is successful if:

- a candidate voice change can be judged by a dedicated truth runner
- the runner emits `pass`, `block`, or `escalate`
- at least the critical binding metrics can stop a bad change from shipping
- advisory metrics remain visible without pretending to be constitutionally mature
- the truth result can be consumed cleanly by governance and the founder surface

## Implementation Boundary

This spec defines the Truth Plane for the first locked voice loop: datasets, locked contract, scoring categories, decision semantics, and output shape. It does not define the full founder UI, the full worker-org redesign, or later app/outbound truth loops. Those should be planned separately and integrated via the truth outputs defined here.

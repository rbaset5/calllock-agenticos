# Improvement Lab Design

**Date:** 2026-03-23
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [Truth Plane Design](2026-03-23-truth-plane-design.md), [Governance Plane Design](2026-03-23-governance-plane-design.md), [Execution Org Design](2026-03-23-execution-org-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Design the Improvement Lab as CallLock’s controlled optimization environment for voice prompt iteration. The lab exists to generate, test, rank, and discard candidate prompt/config variants offline before any candidate is sent to the constitutional truth loop.

The Improvement Lab is not the Truth Plane. It is an optimization environment, not a source of constitutional judgment. It may decide which candidates are worth carrying forward, but it may not decide which candidates are allowed to ship.

## Goals

- create a tight loop for voice prompt improvement
- reduce the number of weak candidates that reach the constitutional truth gate
- automate candidate generation, replay, scoring, and ranking inside a bounded lab
- preserve clean separation between optimization and truth
- keep v1 narrow and interpretable

## Non-Goals

- replacing the Truth Plane
- becoming a general experimentation platform across the whole company
- mutating production directly
- becoming a full autonomous shipping loop
- expanding immediately into app, outbound, or broad extraction-code experimentation
- turning live detection events into direct lab verdicts

## Recommendation

Use a `controlled optimization loop`.

That means:

- automate candidate generation and comparison
- keep/revert inside the lab
- explicitly hand promoted candidates into the Truth Plane
- keep human control over targets and promotion boundaries

This is preferable to a manual workbench because it compounds faster, and preferable to a fully autonomous optimizer because it preserves separation of powers.

## Purpose

The Improvement Lab exists to answer:

`What candidate change is worth sending to the real truth gate next?`

It is not:

- the constitutional judge
- the shipping authority
- the founder operating surface
- the production runtime

Its job is:

- generate candidates
- compare candidates
- discard weak ideas cheaply
- surface strong candidates for real truth evaluation

## Scope of v1

V1 is explicitly prompt-optimization-first.

### In Scope

- prompt text variants
- prompt structure variants
- instruction-ordering changes
- wording changes around known failure clusters
- limited prompt-adjacent voice config variants

In v1, `prompt-adjacent voice config variants` means configuration that directly changes prompt behavior without changing the broader runtime contract, such as:

- system prompt body text
- instruction ordering
- few-shot/example wording
- tool description wording that affects model behavior

It explicitly excludes:

- model selection
- temperature and sampling settings
- tool schema changes
- state-machine rewrites
- deployment identifiers or runtime wiring

### Out of Scope

- broad extraction-pipeline code mutation
- routing-policy rewrites as a general lab capability
- app-side experimentation
- broad multi-surface experimentation
- autonomous production rollout

## Current Context

This design should be understood in the context of prior conclusions:

- Retell remains the production voice runtime for now
- the constitutional voice truth loop is separate and binding
- the lab should resemble the `autovoiceevals` pattern in spirit, but not replace CallLock’s truth layer

The lab is best treated as a `train/improvement loop`, while the Truth Plane remains the `prepare/judging loop`.

Detection context may later help choose experiment targets, but Detection does not replace the lab’s comparison logic or Truth’s constitutional judgment.

## Lab Loop

The recommended loop is:

### 1. Choose experiment target

Examples:

- improve follow-up handling
- reduce callback-gap warnings
- improve emergency instruction behavior
- improve extraction stability on noisy calls

### 2. Generate candidate variants

Candidates are usually prompt/config-focused in v1.

### 3. Run offline experiment suite

The candidate is evaluated against:

- simulated scenarios
- adversarial scenarios
- replay slices from known failure cohorts
- selected seed/gold examples appropriate for lab use

### 4. Compare against baseline

The lab compares candidate performance against the current experiment baseline.

### 5. Keep / revert inside the lab

Weak candidates are discarded.
Only promising candidates survive the lab loop.

### 6. Promote candidate for truth evaluation

A lab winner becomes a promotion candidate for the Truth Plane.

This handoff must be explicit.

## Core Lab Objects

The Improvement Lab should be built around five core objects.

### 1. Experiment Target

Defines what the lab is trying to improve.

Fields should include:

- target_id
- target_type
- hypothesis
- owner
- success signals

### 2. Candidate Variant

A prompt/config variation being tested.

Fields should include:

- candidate_id
- baseline_reference
- variant_type
- mutation_summary
- prompt_or_config_ref

### 3. Scenario Suite

The offline cases used in the lab.

This may include:

- adversarial conversations
- targeted failure clusters
- replay slices
- scenario subsets focused on one behavior

### 4. Experiment Result

The offline result of running one candidate against one scenario suite.

Fields should include:

- candidate_id
- suite_id
- baseline_comparison
- score_summary
- regressions
- keep_recommendation

### 5. Promotion Candidate

A lab winner that is worth sending into the Truth Plane.

This object matters because it preserves a visible boundary between:

- winning in the lab
- passing constitutional truth

## Keep / Revert Semantics

Inside the Improvement Lab, the canonical actions are:

- `keep`
- `revert`

### `keep`

Meaning:

- candidate outperforms the baseline inside the lab
- no obvious regression appears in the offline suite
- candidate is worth carrying forward

### `revert`

Meaning:

- candidate underperforms the baseline
- candidate introduces obvious offline regressions
- candidate is not worth sending to truth

Important distinction:

`keep / revert` is not the same as `pass / block / escalate`.

Those are Truth Plane outcomes, not lab outcomes.

## Relation to Truth Plane

The relationship to Truth must stay explicit and clean.

- the lab generates and filters candidates
- the Truth Plane decides whether a candidate is constitutionally acceptable
- Governance controls whether acceptable candidates are allowed to proceed

The Improvement Lab may say:

`candidate 7 is the best offline option`

Only the Truth Plane may say:

`candidate 7 passes the locked voice gate`

## Human Role

For v1, human control remains at three points:

### 1. Choosing experiment targets

Humans decide what the lab is trying to improve.

### 2. Reviewing promoted candidates when needed

Humans may inspect promoted candidates before they enter the Truth Plane, especially early in the lab’s life.

### 3. Adjusting scenario suites and experiment priorities

Humans control the shape of the optimization problem and the areas of focus.

The lab may automate:

- candidate generation
- replay
- scoring
- ranking
- keep/revert decisions inside the lab

It should not autonomously decide what the company is optimizing for.

## Scenario Strategy

V1 should use a focused mix of offline scenario types:

### Adversarial scenarios

Designed to stress known weak spots:

- noisy callers
- ambiguous urgency
- callbacks vs booking confusion
- safety wording edge cases

### Failure-cluster scenarios

Built from recurring real-world mistakes or warning patterns.

### Replay slices

Small subsets of real examples chosen to compare prompt behavior offline.

The scenario strategy should prefer targeted signal over broad volume in v1.

## Baseline Policy

The lab baseline should be the current experiment baseline for the target under investigation, which usually begins as the current production prompt/config for that surface.

This is separate from the Truth Plane’s constitutional production baseline comparison.

The lab baseline is used for ranking and filtering.
The Truth Plane baseline is used for constitutional gating.

## Promotion Policy

A candidate should be promoted out of the lab only when:

- it survives the keep/revert loop
- it shows clear offline improvement on the target
- it does not show obvious offline regressions on the bounded scenario suite

Promotion does not mean approval to ship.
It means:

`this candidate is worth constitutional evaluation`

## Relationship to Existing Repo

The lab should reuse existing assets where possible:

- current voice contracts
- existing seed eval cases
- health-check logic where useful for comparison helpers
- scorecard logic where useful for offline warning signals

But it should not reuse the generic eval runner as the lab’s only comparison engine if that would flatten meaningful experiment results into weak boolean outputs.

## What Not To Do

The Improvement Lab should explicitly avoid:

- becoming the shipping authority
- collapsing into the Truth Plane
- becoming a broad company experimentation platform too early
- mutating production as part of the lab loop
- turning every candidate into a truth run without cheap offline filtering first
- letting the lab silently redefine success metrics

## Phased Delivery

### Phase 1

- prompt optimization only
- bounded scenario suites
- candidate generation + replay + ranking
- keep/revert loop inside the lab
- explicit promotion candidate handoff to Truth

### Phase 2

- richer scenario generation
- stronger experiment history
- better ranking and comparison artifacts
- tighter integration with founder-facing truth and review surfaces
- use repeated detection patterns to seed better experiment targets

### Phase 3

- possible expansion into adjacent voice experiment classes once the prompt loop is stable
- possible monitor-tuning and triage-policy experiments once the Detection Plane is real and stable

## Risks

### Risk: self-grading creep

If the lab’s keep/revert decisions start to substitute for the Truth Plane, the system collapses back into self-certification.

### Risk: lab sprawl

If the lab becomes a general experimentation platform too early, it will become harder to understand and slower to operationalize.

### Risk: optimization without target discipline

If experiment targets are vague, the lab will generate activity without yielding useful promotion candidates.

### Risk: detection-lab confusion

If live detection signals are mistaken for lab outcomes, the system will blur investigation, optimization, and truth.

## Open Questions for Planning

- What exact file/config boundary defines a prompt candidate in v1?
- Which current replay path should the lab runner call for offline experiments?
- Where should experiment results and promotion candidates be stored in the repo/runtime model?
- What is the simplest useful ranking function for early keep/revert decisions?

## Acceptance Criteria

This design is successful if:

- the lab can generate and compare prompt candidates offline
- weak candidates are discarded before reaching the Truth Plane
- strong candidates are promoted explicitly rather than implicitly shipped
- the lab remains separate from constitutional truth
- humans retain control over experiment targets and strategic direction

## Implementation Boundary

This spec defines the Improvement Lab: prompt iteration loop, offline experiments, keep/revert behavior, and promotion handoff into Truth. It does not define the constitutional truth gate, the founder UI, or a broad experimentation platform for every future surface.

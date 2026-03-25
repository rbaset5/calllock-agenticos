# Missed-Call Inbox Triage Design

Date: 2026-03-25
Owner: Codex
Status: Draft for review

## Summary

The unresolved-call inbox should add a far-left triage block that helps a busy shop owner decide which record to open first and who to call now. The triage block uses two lines:

1. A command that tells the owner when to act.
2. A compact evidence line that earns the click by explaining why.

This is a judgment layer, not a replacement for owner judgment. It should sort unresolved calls into an operational order while staying easy to sanity-check.

## Problem

The current inbox already exposes lightweight judgment cues such as urgency chips and a binary follow-up label, but it still makes the owner read across each row to decide what matters first. That is too much work for a busy operator who needs a fast answer to:

- Which unresolved call should I open first?
- Which one deserves a call right now?

The product gap is not missing metadata. It is missing a stronger, glanceable triage system.

## Goals

- Give every unresolved call a fast, comparable action recommendation.
- Optimize for customer urgency before business value when those conflict.
- Help the owner review details and decide to call now, not blindly obey the UI.
- Make the system's judgment legible enough that owners can usually say, "yes, that sounds right."

## Non-Goals

- Replacing the detailed call row or detail pane.
- Showing a numeric triage score in the UI.
- Turning the inbox into a revenue leaderboard.
- Hiding uncertainty behind precise-sounding model language.

## Design Principles

- Command vs evidence: the UI must recommend action timing and justify it with a compact reason.
- Urgency first: customer pain, service outage risk, and time sensitivity outrank revenue potential.
- Plain language: use operational words, not model words.
- Fail soft: when evidence is weak, stay factual and avoid overclaiming certainty.

## Proposed Inbox Model

Every unresolved call receives a left-edge triage block with two lines:

### Command

One of four action-timing labels:

- `Call now`
- `Next up`
- `Today`
- `Can wait`

These labels should become the operating language of the inbox. They are for ordering work, not describing call types.

### Evidence

A short reason that explains why the call belongs in that bucket. The evidence line should be compact, factual, and fast to scan.

Preferred pattern:

`problem or situation` + optional `context that changes urgency`

Examples:

- `no cooling`
- `requested callback`
- `estimate request`
- `urgent escalation`
- `booking failed`
- `incomplete details, needs review`

Avoid:

- Full-sentence summaries
- Hidden-model phrasing such as "AI believes"
- Revenue-first wording
- Overly specific evidence when extraction quality is weak

## Priority Ladder

The command should come from a simple ladder, not a blended visible score.

### `Call now`

Use when delay is likely to cause immediate customer pain, safety risk, service outage, or high churn risk.

Typical triggers:

- `isSafetyEmergency = true`
- `urgency = LifeSafety`
- Severe outage language in `problemDescription` or `hvacIssueType`
- `isUrgentEscalation = true`
- `urgency = Urgent` with a concrete service issue

### `Next up`

Use when a human should respond soon, but the situation is not an immediate emergency.

Typical triggers:

- Callback requested
- `endCallReason = callback_later`
- `callbackType` present
- `endCallReason = booking_failed`
- `urgency = Urgent` without enough detail to justify `Call now`

### `Today`

Use when the call matters and deserves same-day follow-up, but waiting a few hours is acceptable.

Typical triggers:

- Estimate requests
- `urgency = Estimate`
- `urgency = Routine` with a concrete service issue
- Concrete unresolved issue that does not match a stronger bucket

### `Can wait`

Use when the unresolved call is real but low-cost to defer.

Typical triggers:

- Low-information unresolved call
- Ambiguous issue with no urgency cue
- Incomplete call with no clear urgency cue

## Ordering Logic

The inbox should order unresolved calls by:

1. Command bucket
2. Deterministic signal rank within the bucket
3. Recency

If a call matches multiple possible outcomes, the highest matching command bucket wins before any within-bucket ranking is applied.

For v1, business value is out of scope as a ranking signal. If two calls land in the same command bucket and share the same signal rank, recency decides the order.

Recommended within-bucket signal rank for v1:

1. Safety emergency
2. Urgent escalation
3. Follow-up signal (`callback requested`, `endCallReason = callback_later`, `callbackType`, or `endCallReason = booking_failed`)
4. Concrete service issue extracted (`problemDescription` or `hvacIssueType`)
5. Generic unresolved record

This keeps the sort logic deterministic and grounded in currently available fields.

## Trust And Uncertainty Guardrails

The triage layer should fail soft.

If evidence is weak, still assign a command, but keep the evidence line plainly factual:

- `Today` / `incomplete details, needs review`
- `Next up` / `callback requested, details unclear`

Guardrails:

- No numeric score in the UI
- No fabricated certainty language
- No urgency overrides based on projected revenue in v1
- No highly specific evidence unless supporting fields are reliable

Fallback mapping for sparse data:

- If the call has a concrete issue but no urgency cue, default to `Today`.
- If the call mainly indicates a callback or follow-up need, default to `Next up`.
- If the call is unresolved but the extracted fields are too thin to justify stronger action, default to `Can wait` with evidence such as `incomplete details, needs review`.

## Data Dependencies

The current call model already exposes several useful inputs for first-pass triage:

- `urgency`
- `isSafetyEmergency`
- `isUrgentEscalation`
- `endCallReason`
- `callbackType`
- `problemDescription`
- `hvacIssueType`
- `createdAt`

The first version should prefer deterministic rules over a fully learned ranking system. The spec intentionally does not require new extraction work for concepts such as customer lifetime value, customer history, lead value, partner/vendor identification, or after-hours classification. Those can be future enhancements after the command + evidence pattern proves useful.

If a later version introduces a hidden ranking score for tie-breaking, the visible UI should still remain command + evidence.

## UX Notes

- Place the triage block on the far left of each unresolved row so it becomes the first scan target.
- Keep caller name, time, and snippet as supporting detail, not the primary decision surface.
- Keep the existing urgency chips and follow-up metadata as secondary row details in v1; the new triage block becomes the primary ordering cue.
- Preserve the detail pane as the place where the owner validates context before calling.
- Treat this as an inbox-wide system for all unresolved calls, not only AI failures or handoff exceptions.

## Validation Criteria

The design is successful if owners can usually scan the inbox and know the right opening order without reading each row in full.

Validation scenarios should include:

- Emergency outage
- Urgent callback request
- Routine estimate
- Low-information unresolved inquiry
- Incomplete transcript or ambiguous issue
- `endCallReason = booking_failed`

Success criteria:

- Ordering feels operationally sane
- Evidence earns the click
- Urgency-first behavior holds under conflict
- Labels do not feel arbitrary or opaque

## Planning Readiness

This scope is narrow enough for a single implementation plan. It is a focused inbox triage feature, not a broader redesign of the call detail view, CRM, or dispatch workflow.

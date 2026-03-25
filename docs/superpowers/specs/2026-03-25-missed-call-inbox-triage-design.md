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

- `no cooling, existing customer`
- `requested callback, missed booking`
- `system quote, new lead`
- `parts question, can wait`
- `after-hours outage`
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

- Safety emergency
- No heat or no cooling outage
- Explicit urgency from the caller
- Existing customer with a stranded or acute problem
- Repeat failed resolution that now needs human intervention

### `Next up`

Use when a human should respond soon, but the situation is not an immediate emergency.

Typical triggers:

- Callback requested
- Owner decision needed
- Scheduling friction blocked the call
- Likely urgent issue with enough uncertainty that a human should review soon

### `Today`

Use when the call matters and deserves same-day follow-up, but waiting a few hours is acceptable.

Typical triggers:

- Estimate requests
- Replacement leads
- Routine service calls that the AI did not capture
- Non-urgent sales opportunities

### `Can wait`

Use when the unresolved call is real but low-cost to defer.

Typical triggers:

- Vendor or partner inquiry
- Low-priority admin request
- Weak-intent lead
- Incomplete call with no clear urgency cue

## Ordering Logic

The inbox should order unresolved calls by:

1. Command bucket
2. Strongest urgency cue within the bucket
3. Recency

Business value can break ties inside a bucket, but it must not promote a lower-urgency call above a higher-urgency call in another bucket.

Example:

- `Call now` + `no cooling, existing customer`
- `Today` + `high-ticket system quote`

The quote can still rank highly within `Today`, but it does not outrank the urgent outage.

## Trust And Uncertainty Guardrails

The triage layer should fail soft.

If evidence is weak, still assign a command, but keep the evidence line plainly factual:

- `Today` / `incomplete details, needs review`
- `Next up` / `callback requested, details unclear`

Guardrails:

- No numeric score in the UI
- No fabricated certainty language
- No urgency overrides based only on projected revenue
- No highly specific evidence unless supporting fields are reliable

## Data Dependencies

The current call model already exposes several useful inputs for first-pass triage:

- `urgency`
- `isSafetyEmergency`
- `isUrgentEscalation`
- `endCallReason`
- `callbackType`
- `appointmentBooked`
- `problemDescription`
- `hvacIssueType`
- `customerName`
- `createdAt`

The first version should prefer deterministic rules over a fully learned ranking system. If a later version introduces a hidden ranking score for tie-breaking, the visible UI should still remain command + evidence.

## UX Notes

- Place the triage block on the far left of each unresolved row so it becomes the first scan target.
- Keep caller name, time, and snippet as supporting detail, not the primary decision surface.
- Preserve the detail pane as the place where the owner validates context before calling.
- Treat this as an inbox-wide system for all unresolved calls, not only AI failures or handoff exceptions.

## Validation Criteria

The design is successful if owners can usually scan the inbox and know the right opening order without reading each row in full.

Validation scenarios should include:

- Emergency outage
- Urgent callback request
- Routine estimate
- Vendor or low-priority inquiry
- Incomplete transcript or ambiguous issue
- High-value but non-urgent lead

Success criteria:

- Ordering feels operationally sane
- Evidence earns the click
- Urgency-first behavior holds under conflict
- Labels do not feel arbitrary or opaque

## Planning Readiness

This scope is narrow enough for a single implementation plan. It is a focused inbox triage feature, not a broader redesign of the call detail view, CRM, or dispatch workflow.

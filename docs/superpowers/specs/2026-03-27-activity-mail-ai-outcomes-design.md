# Activity/Mail AI Outcomes Design

Date: 2026-03-27
Owner: Codex
Status: Draft for review

## Summary

The Activity/mail view should stop treating AI-booked appointments and AI-escalated urgent calls as generic handled records. For CallLock's owner-operator ICP, those are two distinct product moments:

- `Booked by AI` is the core win: the system turned a missed call into a booked job.
- `Escalated by AI` is the trust moment: the system recognized an urgent situation and pushed it upward.

The mail view should therefore split the current handled bucket into three visible outcome groups:

1. `Escalated by AI`
2. `Booked by AI`
3. `Other AI Handled`

These should sit alongside the existing owner work queues:

1. `Escalated by AI`
2. `New Leads`
3. `Follow-ups`
4. `Booked by AI`
5. `Other AI Handled`

Only the Activity/mail view changes in this spec. The dashboard/home view stays out of scope.

## Problem

The current Activity/mail IA collapses multiple very different outcomes under `AI Handled`. That causes three UX failures for the target user:

1. The product's main success event, an appointment booked by AI, is visually grouped with spam, wrong numbers, and routine resolved items.
2. AI escalations are not given enough prominence for a busy owner who needs confidence that urgent situations were recognized and routed correctly.
3. When the owner has no open callbacks, the view can land with no selected detail item even if AI already booked work or escalated something important.

This creates a mismatch with CallLock's positioning. The system is sold as the product that turns missed calls into booked jobs for small home-service operators. The UI should reflect that operating story directly.

## Goals

- Give `Booked by AI` first-class visibility as a top-level success section.
- Give `Escalated by AI` first-class visibility as a top-level trust/risk section.
- Preserve the existing callback workflow for `New Leads` and `Follow-ups`.
- Keep lower-value handled outcomes visible but visually quieter under `Other AI Handled`.
- Make selection behavior deterministic so the detail pane always surfaces the most important available item.

## Non-Goals

- Redesigning the dashboard/home view.
- Changing underlying extraction or call classification fields.
- Introducing new backend persistence or database schema.
- Changing how callback outcomes are saved.
- Building a new KPI or analytics system around these sections in this pass.

## ICP Framing

The target user is a small home-service operator, often owner-led, who already pays for demand but lacks reliable after-hours phone coverage and admin support. For that operator:

- `Booked by AI` means saved revenue while they were unavailable.
- `Escalated by AI` means the system can be trusted in urgent or safety-sensitive moments.
- `Other AI Handled` is operationally useful, but not the main story.

The section order and copy should reflect that mental model rather than a system-centric taxonomy.

## Information Architecture

The Activity/mail view should render five sections in this order:

### 1. `Escalated by AI`

Contains AI-handled calls whose handled reason is escalation, including safety emergencies, life-safety urgency, and urgent escalations that the system routed upward.

Why first:

- It represents the highest trust-sensitive AI outcome.
- The owner needs immediate confidence that the right urgent situations were recognized.

### 2. `New Leads`

Contains actionable, unresolved calls that need initial owner attention.

This remains the main callback work queue.

### 3. `Follow-ups`

Contains actionable calls where a prior touch or explicit follow-up signal exists.

This remains a work queue, but below fresh leads.

### 4. `Booked by AI`

Contains AI-handled calls where an appointment was successfully booked.

Why separate:

- This is the product's hero outcome.
- It should feel like a secured win, not archived system residue.

### 5. `Other AI Handled`

Contains lower-priority handled records such as:

- spam/vendor
- wrong number/out of area
- generic resolved terminal outcomes

This section should remain collapsible and visually quieter than the other four.

## Bucketing Model

The existing handled/action-queue split should be expanded into explicit display groups.

Recommended display groups:

- `ESCALATED_BY_AI`
- `NEW_LEADS`
- `FOLLOW_UPS`
- `BOOKED_BY_AI`
- `OTHER_AI_HANDLED`

### Mapping Rules

- The new display groups should be derived from the existing handled-reason and action-queue logic, not from a new independent classification system.
- Calls currently classified as handled reason `escalated` should map to `ESCALATED_BY_AI`.
- Calls with `appointmentBooked = true` should map to `BOOKED_BY_AI`, unless a higher-priority escalation rule applies.
- Actionable unresolved calls should continue to map to `NEW_LEADS` or `FOLLOW_UPS`.
- Spam, vendor, wrong number, out of area, and terminal generic resolved outcomes should map to `OTHER_AI_HANDLED`.

### Priority Rule

Escalation wins over booking if a call qualifies for both. The operating assumption is that a trust-sensitive escalation should not be visually downgraded into a success bucket.

## Section Behavior

### `Escalated by AI`

- Always visible.
- Not collapsible.
- Full opacity.
- Use danger styling at the section and card level.
- Cards should not look archived.
- Hide the section entirely when empty.

### `New Leads`

- Same operational behavior as today.
- Preserve actionable callback controls and triage surface.
- Hide the section entirely when empty.

### `Follow-ups`

- Same operational behavior as today.
- Preserve touch history and outcome controls.
- Hide the section entirely when empty.

### `Booked by AI`

- Always visible when non-empty.
- Not collapsible.
- Full opacity.
- Use success-forward styling, not muted handled styling.
- Cards should feel complete and trustworthy, not dormant.
- Hide the section entirely when empty.

### `Other AI Handled`

- Lower visual priority.
- Collapsible.
- Can retain quieter styling and compact summary counts.
- Hide the section entirely when empty.

## Selection Behavior

The detail pane should always default to the highest-priority available item.

Selection priority:

1. Newest item in `Escalated by AI`
2. First item in `New Leads`, using that section's existing sort order
3. First item in `Follow-ups`, using that section's existing sort order
4. Newest item in `Booked by AI`
5. Newest item in `Other AI Handled`
6. `null` only if all sections are empty

This rule prevents the empty-detail-state problem when the action queue is empty but important AI outcomes exist.

## Card Copy

Section labels should use operator language, not internal system language.

### `Escalated by AI`

Preferred card/status language:

- `Safety emergency escalated`
- `Urgent situation escalated`

Avoid:

- generic `handled`
- low-information labels like `escalated` with no context

### `Booked by AI`

Preferred card/status language:

- `Appointment secured`
- `Booked by AI`

If appointment time is known, show it inline or as secondary supporting text.

Avoid:

- generic `handled`
- muted archive language
- wording that makes the booking sound tentative if the underlying data says it succeeded

### `Other AI Handled`

Continue using compact reason labels, for example:

- `spam/vendor`
- `wrong number`
- `resolved`

## Detail Pane Behavior

### `Escalated by AI`

The detail pane should make the escalation action explicit.

Required emphasis:

- what was escalated
- why it was escalated
- when it happened

Preferred summary language:

- `Safety emergency escalated to dispatch`
- `Urgent issue escalated for immediate handling`

If future state data exists for downstream handling, it may be added later, but this spec does not require new backend fields.

### `Booked by AI`

The detail pane should make the booking outcome explicit and confidence-building.

Required emphasis:

- appointment was secured
- appointment time, if available
- key customer/job context

Preferred summary language:

- `Appointment secured by AI`
- `Booked for Today @ 4:30 PM`

### `Other AI Handled`

May continue to use the existing handled summary pattern because those records are not the hero outcome.

## Visual Treatment

The visual system should reinforce operational meaning:

- `Escalated by AI`: strongest alert treatment in this view
- `Booked by AI`: positive/success treatment
- `Other AI Handled`: quiet/muted treatment

Specific colors can follow the existing design system, but the contrast between these three groups must be obvious at a glance.

Do not apply reduced opacity to `Escalated by AI` or `Booked by AI` cards.

## Data Dependencies

This design should use existing fields only:

- `appointmentBooked`
- `appointmentDateTime`
- `isSafetyEmergency`
- `isUrgentEscalation`
- `urgency`
- `endCallReason`
- existing handled reason / bucket assignment logic

No new extraction or schema work is required.

## Testing Requirements

Implementation planning should include regression coverage for:

1. Booked calls map to `BOOKED_BY_AI`.
2. Escalated calls map to `ESCALATED_BY_AI`.
3. Spam, wrong-number, and generic resolved calls map to `OTHER_AI_HANDLED`.
4. Section ordering is preserved.
5. Selection priority chooses escalated first, then `New Leads`, then `Follow-ups`, then booked, then other handled.
6. `Booked by AI` cards and detail views use success-forward copy.
7. `Escalated by AI` cards and detail views use escalation-forward copy.
8. `Other AI Handled` remains collapsible and quieter.

## Risks And Guardrails

- Do not let `Booked by AI` compete visually with `Escalated by AI` for urgency. Success should be prominent, but escalation remains the highest-priority trust signal.
- Do not move booked records back into a generic archive pattern through muted styling, reduced opacity, or hidden default collapse.
- Do not break the current callback workflow while changing the section model.
- Do not infer new business meaning from `appointmentBooked`, such as whether the caller is a returning customer.

## Open Questions

None for v1. The user-approved decisions are:

- Scope is Activity/mail view only.
- The booking section label is `Booked by AI`.
- Escalated AI outcomes should also be handled specially.

## Implementation Readiness

This spec is intentionally narrow. It should be sufficient to produce a single implementation plan covering:

- bucket assignment updates
- Activity/mail section rendering updates
- detail copy updates
- selection behavior updates
- regression tests

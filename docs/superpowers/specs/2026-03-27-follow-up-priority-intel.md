# Follow-up Priority & Lead Intel Cards

**Date:** 2026-03-27
**Status:** Approved

## Problem

The Follow-ups section in the activity feed treats all follow-up calls identically. A booking failure (highest conversion intent) looks the same as a voicemail retry (lowest urgency). The operator can't scan the list and instantly know which call to make next or what context they need before dialing.

## Solution: Two-Tier Follow-ups

Split follow-up cards into **hot** and **routine** tiers based on conversion likelihood. Hot cards get a priority panel and inline lead intel. Routine cards keep the current compact pill treatment.

## Follow-up Reordering (Conversion Likelihood)

Replace the current `followUpSort` with a conversion-likelihood ranking:

1. **Booking failed** — highest intent, customer literally tried to book
2. **Complaint / active job issue** — existing customer at risk of churning
3. **AI promised callback** — (`callback_later`, `callbackType` set) — expectation set, not yet at decision point
4. **Retry** — (`left_voicemail`, `no_answer`) — already attempted, least urgent

Within each tier, sort by recency (newest first).

## Hot vs Routine Classification

### Hot follow-ups (priority panel + intel row)
- `endCallReason === "booking_failed"`
- `primaryIntent` is `"complaint"` or `"active_job_issue"`

### Routine follow-ups (current compact pill treatment)
- `callbackOutcome` is `"left_voicemail"` or `"no_answer"` (retries)
- `endCallReason === "callback_later"` or `callbackType` set (AI promised)
- `primaryIntent === "followup"` (generic follow-up)

Hot cards appear first in the Follow-ups section, then routine below. No sub-headers — the visual treatment itself creates the separation.

## Hot Follow-up Card Treatment

### Priority panel (left edge, 56px)
Same pattern as New Leads cards. Color-coded by follow-up type:
- **Booking failed** → danger-adjacent tone (similar to "CALL NOW"), calendar icon, stacked "BOOK" / "FAIL" label
- **Complaint** → amber/warning tone, alert icon, stacked "AT" / "RISK" label
- **Active job issue** → amber/warning tone, alert icon, stacked "ACTIVE" / "JOB" label

### Intel line (below snippet)
Single line of key facts from existing `Call` fields, separated by middots:
- `serviceAddress` (truncated to city/area if long)
- `equipmentType` + `equipmentBrand` (e.g., "Carrier · 2-ton split")
- `equipmentAge` if present
- For booking failed: "Booking failed" context
- For complaints: `problemDescription` snippet if different from main snippet

Example:
```
┌──────────┬──────────────────────────────────────────┐
│  BOOK    │ Jane Smith · booking failed       2h ago │
│  FAIL    │ AC not cooling, wants estimate           │
│  📅      │ Plano, TX · Carrier 2-ton · 15 yrs      │
│          │ [CALL BACK]                              │
└──────────┴──────────────────────────────────────────┘
```

### Graceful degradation
If equipment info is missing, show location only. If location is also missing, skip the intel line entirely — the hot card falls back to just having the priority panel.

## Routine Follow-up Card Treatment

No changes. Keeps the current compact card with category pill ("Left voicemail · 3h ago · try again").

## Scope

### In scope
1. `web/src/lib/triage.ts` — update `followUpSort` to use conversion-likelihood ordering
2. `web/src/components/mail/mail-list.tsx` — add hot/routine classification, priority panel for hot cards, intel line rendering

### Out of scope
- New Leads section (already has priority panels)
- Escalated / Booked sections (have their own treatments)
- Scripts/templates in list view (stay in detail view)
- Customer history lookups ("2nd call this week" — requires new query, separate feature)
- Detail view changes
- Schema changes (all fields already exist on `Call` interface)

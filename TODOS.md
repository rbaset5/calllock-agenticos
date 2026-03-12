# TODOS

Items identified during the CEO-level architecture review (2026-03-12).

## P1 — Must Do

### Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

## P2 — Should Do

### Define compliance graph conflict resolution rule
**What:** Define what happens when the compliance graph returns contradictory rules (e.g., one rule requires a disclosure, another forbids it for the same context).
**Why:** Without a conflict resolution strategy, the policy gate could silently apply the wrong rule or block everything.
**Effort:** S
**Depends on:** Policy Gate detail (Section 5) being finalized.
**Source:** CEO review, Section 2 (Error & Rescue Map).

### Define external service resilience patterns
**What:** Define fallback behavior when Retell AI, Supabase, Cal.com, or Twilio are unavailable.
**Why:** All four are production SPOFs with no fallback story in the spec.
**Effort:** M
**Depends on:** Section 0 (Current State) establishing which services are critical.
**Source:** CEO review, Section 1F (Single Points of Failure).

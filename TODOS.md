# TODOS

Items identified during architecture reviews (2026-03-12).
Updated 2026-03-13: closed resolved items, narrowed remaining scope.

## Active

### P1 — Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

### P2 — Define external service resilience patterns (narrowed)
**What:** Define fallback behavior when Retell AI, Cal.com, or Twilio are unavailable.
**Why:** All three are production SPOFs with no fallback story. Supabase resilience is covered by the harness write-failure handling already implemented.
**Scope:** Deferred until Retell/Cal.com/Twilio integration clients exist in this repo. Define resilience patterns alongside the integration code, not speculatively.
**Effort:** M
**Source:** CEO review, Section 1F (Single Points of Failure).

### P3 — Tune Cockpit alerting thresholds from production baselines
**What:** Define specific threshold values for the four alert types (policy gate block rate, worker metric degradation, job failure spikes, external service errors) using observed baselines from the metrics API.
**Why:** Thresholds need baseline data from actual deployment, not guesses.
**Prerequisite:** Metrics API deployed and collecting data from production traffic.
**Effort:** S
**Source:** Eng review, Section 3 (Alerting).

## Closed

### ~~P3 — Define Express V2 horizontal scaling story~~
**Resolved by:** `docs/decisions/002-express-v2-scaling.md` (ADR 002)

### ~~P1 — Define compliance graph conflict resolution rule~~
**Resolved by:** `supabase/migrations/006_compliance_conflict_resolution.sql`

### ~~P2 — Define Inngest event validation schema~~
**Resolved by:** Inngest event schema implementation in `inngest/src/events/schemas.ts`

### ~~P2 — Define harness → Supabase write failure handling~~
**Resolved by:** Harness persistence node and repository error handling in `harness/src/harness/nodes/persist.py` and `harness/src/db/supabase_repository.py`

### ~~P2 — Define PII redaction implementation approach~~
**Resolved by:** Pattern-matching PII redactor in `harness/src/observability/pii_redactor.py` and verification node checks in `harness/src/harness/nodes/verification.py`

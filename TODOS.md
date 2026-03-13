# TODOS

Items identified during architecture reviews (2026-03-12).

## P1 — Must Do

### Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

### Define compliance graph conflict resolution rule
**Status:** Resolved in code and ADR 009. Compliance rules now resolve by explicit conflict grouping (`metadata.conflict_key` / `metadata.disclosure_key` / `target`), mixed-effect matches always escalate, pure restrictions follow `deny > escalate > allow`, and tool execution remains deny-by-default when no explicit allow matches.
**What:** Define what happens when the compliance graph returns contradictory rules (e.g., one rule requires a disclosure, another forbids it for the same context). Resolution principle (most-restrictive-wins) is now in Section 5; this TODO covers the full rule set.
**Why:** Without a conflict resolution strategy, the policy gate could silently apply the wrong rule or block everything. Promoted from P2: the policy gate depends on this to function correctly.
**Implementation consideration:** Cross-graph queries ("which compliance rules contradict each other?") require scanning all compliance graph nodes. With markdown/YAML files this is a full-text scan — consider whether the compliance graph specifically should be database-backed (Supabase table with typed relationships) rather than file-based, to enable indexed conflict detection. The rest of the Knowledge Substrate can remain file-based; compliance rules are the highest-stakes query surface.
**Effort:** S
**Depends on:** Policy Gate detail (Section 5) being finalized.
**Source:** CEO review, Section 2 (Error & Rescue Map). Promoted by eng review.

## P2 — Should Do

### Define external service resilience patterns
**Status:** Partially resolved in code and ADR 002 for Supabase, Inngest, and LangSmith. Remaining work is Retell AI, Cal.com, and Twilio once those integrations exist in this repo.
**What:** Define fallback behavior when Retell AI, Supabase, Cal.com, or Twilio are unavailable.
**Why:** All four are production SPOFs with no fallback story in the spec.
**Effort:** M
**Depends on:** Section 0 (Current State) establishing which services are critical.
**Source:** CEO review, Section 1F (Single Points of Failure).

### Define Inngest event validation schema
**Status:** Resolved in code and ADR 004 for `harness/process-call` and `harness/job-complete`.
**What:** Define the event schema for harness trigger events emitted by Express V2 after processing Retell webhooks. Include required fields (call_id, tenant_id, call metadata), validation rules, and rejection behavior for malformed events.
**Why:** Without event validation, malformed or unauthorized events could trigger unintended worker execution. This is also a security vector (unauthorized event injection into the Inngest event bus).
**Effort:** S
**Depends on:** Harness trigger mechanism (Section 5) being implemented, Express V2 webhook handler structure.
**Source:** CEO review #2, Section 3 (Security & Threat Model).

### Define harness → Supabase write failure handling
**Status:** Resolved in code and ADR 002 with retry + local recovery journal fallback.
**What:** Define the specific mechanism for handling Supabase write failures during harness operations: transaction boundaries, retry policy, cleanup on partial failure.
**Why:** Error Philosophy rule #4 says "partial state is the enemy" but there's no specific mechanism for the harness → Supabase integration. A failed write mid-job could leave orphaned artifacts or incomplete tenant state.
**Effort:** S
**Depends on:** Return path definition (Section 5), Implementation Phasing (Section 24).
**Source:** Eng review, Failure Modes analysis.

### Define PII redaction implementation approach
**Status:** Resolved in code and ADR 003 with recursive regex redaction + identifier hashing.
**What:** Specify the PII redaction mechanism for LangSmith traces (regex-based, NER model, allowlist/denylist, or library like presidio).
**Why:** Section 5 says "redact or hash direct identifiers" but doesn't specify the approach. PII redaction is notoriously error-prone — regex misses edge cases, NER models add latency.
**Effort:** S
**Depends on:** Harness deployment decisions, LangSmith integration, data volume and latency budget.
**Source:** Eng review, Section 5 (Trace data classification).

## P3 — Nice to Have

### Define Express V2 horizontal scaling story
**What:** Document whether Express V2 on Render runs as single instance, auto-scaled, or behind a load balancer. Define the scaling trigger and expected behavior at 10x tenant count.
**Why:** At 10 tenants × 3 trades, Express V2 handles all webhooks and API requests. Current single-contractor load doesn't require scaling, but the spec positions Express V2 as the product core backend.
**Effort:** S
**Depends on:** Tenant count growth, Render deployment configuration.
**Source:** CEO review #2, Section 7 (Performance Review).

### Define Cockpit alerting thresholds and channels
**Status:** Partially resolved in code. Alert types now include scheduler stale claims and backlog age, thresholds can be overridden per tenant config, delivery supports dashboard, optional webhooks, email, SMS, and pager out of the box, stale alerts can auto-escalate by policy, duplicate sustained conditions are suppressed into a single active alert, recovered conditions can auto-resolve after cooldown, and grouped incidents are now queryable with episode history plus operator workflow, normalized classification, bound runbooks with structured step semantics (`required`, `depends_on`, `parallel_group`), completion and approval policy, per-step runbook progress, derived execution-plan guidance, step ownership/claiming with lease expiry, heartbeat, step-granular compare-and-set, DB-side atomic Supabase step mutation, DB-side atomic incident workflow mutation, DB-side atomic incident reminder/reassignment mutation, DB-side atomic alert-to-incident sync mutation, DB-side atomic alert-update-plus-incident-sync mutation, and DB-side atomic alert-create-plus-incident-sync mutation, weighted/capacity-aware assignment routing, availability-aware fallback, skill-aware routing, and reminders. Production threshold tuning still needs baseline traffic data.
**What:** Define specific threshold values for the four alert types (policy gate block rate, worker metric degradation, job failure spikes, external service errors) and tune the delivery mix for production operations.
**Why:** Sections 3 and 5 say the harness emits alerts to the Cockpit, but without thresholds, alerts are either too noisy or never fire. Thresholds need baseline data from initial deployment.
**Effort:** S
**Depends on:** Harness implementation, baseline metrics from initial deployment.
**Source:** Eng review, Section 3 (Alerting).

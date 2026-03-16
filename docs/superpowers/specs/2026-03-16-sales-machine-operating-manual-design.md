# Sales Machine Operating Manual

**Date:** March 16, 2026
**Status:** Draft - v2 (post CEO mega-review)
**Owner:** Founder / GTM
**Companion to:** `knowledge/growth-system/design-doc.md`
**Runtime alignment:** ADR 010 (Growth System Runtime Placement)
**Event naming:** ADR 015 (Inngest Event Naming Convention)

## Summary

This document is the operational companion to the CallLock Agentic Growth Loop design doc. It defines the concrete sales machine that turns the growth system's architecture into a running cold email outbound engine targeting HVAC single-owner shops.

The growth system design doc owns system architecture: Growth Memory, event bus, experiment allocation, segmentation, signal quality, doctrine, proof coverage, and wedge fitness. This document owns the operational layer: pricing model, unit economics, agent orchestration, sequence design, handoff protocol, the LTV:CAC scorecard, and the swarm-specific infrastructure (Growth Memory tables, proof asset registry, event schemas, observability, and deployment).

If this document conflicts with the growth system design doc on system architecture or object semantics, the growth system design doc wins. If the growth system design doc is silent on operational execution detail, this document is authoritative.

## 1. Pricing Model and Unit Economics

### 1.1 Pricing experiment

Pricing is validated through the swarm's first A/B experiment, founder-gated per growth doc Section 10.8.

Three arms:

| Arm | MRR | Gross Margin | Assumed Churn | LTV | Max CAC at 3:1 | Payback at CAC $500 |
|-----|-----|-------------|---------------|-----|----------------|---------------------|
| A | $149 | 85% | 3.5% | $3,619 | $1,206 | 3.9 months |
| B | $199 | 85% | 3% | $5,638 | $1,879 | 3.0 months |
| C | $249 | 85% | 2.5% | $8,466 | $2,822 | 2.4 months |

Winner declaration criteria:

- Minimum 50 closed prospects per arm
- Statistical significance at 95% confidence
- Measured by: pilot conversion rate, 30-day churn rate, payback period
- Founder-gated: founder must approve winner declaration before system applies it

Pricing arm assignment rules:

- Arms are assigned per-prospect at sequence creation time and are sticky for the lifetime of that prospect's journey, including re-engagement sequences
- If the experiment has declared a winner before a dormant prospect returns for re-engagement, that prospect keeps their original arm assignment
- New prospects entering the pipeline after winner declaration receive the winning arm
- This prevents bait-and-switch perception for returning prospects

### 1.2 CAC budget breakdown

Monthly cost structure for the agentic email swarm:

| Cost Component | Monthly Estimate | Notes |
|----------------|-----------------|-------|
| Lead data (Apollo or similar) | $200-400 | ~2,000-5,000 enriched prospects per month |
| Email infrastructure (Instantly/Smartlead + warmup) | $100-200 | Multiple sending domains |
| LLM costs (personalization, classification) | $50-150 | Claude Haiku or GPT-4o-mini tier |
| Founder time (review, approvals, calls with warm leads) | $0 | Valued at $0 for bootstrapped model |
| **Total monthly swarm cost** | **$350-750** | |

At 20 new customers per month (target): CAC = $18-38. At 5 customers per month (realistic early): CAC = $70-150. Both are well within the 3:1 band across all pricing arms.

### 1.3 Cost tracking

Every agent tracks its per-invocation cost and emits it in the output event:

| Agent | Cost Source | Field |
|-------|-----------|-------|
| Prospector | Apollo API credits per query | `prospecting_cost_cents` |
| Enrichment | LLM tokens + scrape infra | `enrichment_cost_cents` |
| Segmentation | Negligible (rule-based) | `segmentation_cost_cents` (always 0) |
| Sequence | Negligible (template lookup) | `sequence_cost_cents` (always 0) |
| Sender | Email infra per-send fee | `send_cost_cents` |
| Reply Classifier | LLM tokens | `classification_cost_cents` |
| Handoff | Negligible | `handoff_cost_cents` (always 0) |

A daily cost aggregation job sums per-agent costs into `cost_per_acquisition` in Growth Memory. The Founder Dashboard v0 displays rolling 7-day and 30-day CAC from this table.

### 1.4 Key insight

Automated cold email is the highest-leverage channel for this ICP and price point. The constraint is not cost. The constraint is deliverability and conversion rate.

## 2. Agentic Email Swarm Architecture

### 2.1 Design principles

The swarm is not one monolithic agent. It is a pipeline of specialized agents, each with a single job, chained through the Inngest event bus. This matches the growth doc's single-writer ownership model (Section 9.2) and makes each agent independently testable, replaceable, and observable.

### 2.2 Runtime alignment

Per ADR 010, all agent logic is Python in `harness/src/growth/agents/`. Inngest functions in `inngest/src/functions/growth/` are thin TypeScript handlers that validate events and POST to harness HTTP endpoints. The harness provides LiteLLM access, Supabase connections, and tenant isolation.

```
Inngest event arrives
  -> inngest/src/functions/growth/handle-prospect-sourced.ts
  -> validates event payload (TypeScript schema)
  -> HTTP POST to harness /growth/swarm/enrich
  -> harness/src/growth/agents/enrichment_agent.py
  -> tenant context set, LLM call, Supabase write
  -> returns result
  -> Inngest handler emits next event
```

### 2.3 Tenant isolation

All agents operate in a multi-tenant context from day 1:

- Every event payload carries `tenant_id` as a required field
- Every harness HTTP endpoint sets Supabase RLS context via `set_config('app.current_tenant', tenant_id, true)` before executing agent logic
- A tenant context guard middleware on all `/growth/swarm/*` endpoints rejects requests with missing or invalid `tenant_id` with HTTP 403 and logs `calllock/swarm.tenant.scope.failed`
- All 8 Growth Memory tables have `tenant_id` column with RLS policies

### 2.4 Pipeline overview

```
Trigger (cron / manual batch)
    |
    v
Prospector Agent        -- finds and filters raw leads
    | calllock/prospect.sourced
    v
Enrichment Agent        -- enriches with trade, pain, wedge fit, revenue estimate
    | calllock/prospect.enriched
    v
Segmentation Agent      -- assigns segment + lifecycle state
    | calllock/prospect.segmented
    v
Sequence Agent          -- builds multi-touch sequence (uses step.sleepUntil for scheduling)
    | calllock/sequence.created -> scheduled touches via step.sleepUntil
    v
Sender Agent            -- checks sequence status, runs health gate, sends
    | calllock/email.sent
    v
Reply Classifier Agent  -- classifies responses, maps belief signals
    | calllock/reply.classified
    v
Handoff / Escalation Agent -- routes to founder pipeline or re-sequence
```

Additionally:
- Sequence Health Monitor (daily cron) catches stalled sequences
- Cost Aggregation Job (daily cron) computes rolling CAC

### 2.5 Agent specifications

#### 2.5.1 Prospector Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospecting.batch.requested` (daily cron, 6am local) |
| Input | Target wedge (HVAC), geographic filters, batch size cap, tenant_id |
| Data sources | Apollo API (primary), Google Maps enrichment (secondary) |
| Credential health check | Before batch query, verify Apollo API key is valid. On auth failure, emit `calllock/swarm.credential.failed` (P0 founder alert). Fail closed: do not attempt partial batch with bad credentials. |
| Job | Query for HVAC businesses matching ICP filters. Dedupe against prospects table in Supabase (idempotency key: business email domain). Write prospect record to prospects table BEFORE emitting event (write-then-emit pattern). Output raw prospect records. |
| ICP filters | Trade: HVAC. Employees: 1-15. Revenue: inferred $300K-$3M. Has phone number. Has website or Google listing. No existing CallLock customer. Not in suppress list. |
| Output event | `calllock/prospect.sourced` -- one per prospect, batch_id for traceability |
| Output schema | `{ prospect_id, tenant_id, business_name, phone, email, website, google_listing_url, employee_count_est, revenue_est, source, batch_id, prospecting_cost_cents }` |
| Write ownership | Writes to `prospects` table (dedupe record), appends to `touchpoint_log` |
| Failure mode | API rate limit: back off and resume. API auth failure: P0 alert, halt batch. Zero results: alert if 3 consecutive empty batches. Partial batch: emit what you have, log gap. |
| Daily cap | 200 prospects per batch (tunable). During warmup phase: 50 per batch. |

#### 2.5.2 Enrichment Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.sourced` |
| Input | Raw prospect record with tenant_id |
| Input sanitization | Before LLM processing: strip all HTML tags, limit scraped text to 5,000 characters, remove non-printable characters, strip known prompt injection patterns. All LLM outputs validated against enum fields that reject any value not in the allowed set. |
| Job | Scrape website and Google listing. LLM-analyze for: services offered, review sentiment, response patterns (do they mention "leave a message"?), after-hours behavior, team size signals, urgency indicators. Estimate monthly lost revenue using HVAC revenue-estimation.yaml tiers and call-volume signals. Output enriched profile with per-field confidence scores. |
| Revenue estimation | Map prospect signals to HVAC revenue tiers (diagnostic $99, minor $75-250, standard $200-800, major $800-3K, replacement $5K-15K+). Estimate monthly call volume from Google review frequency and business size signals. Calculate estimated_monthly_lost_revenue as: estimated missed calls per month times average service tier value. If no matching signals: null field, skip dollar personalization in T1. |
| LLM | Claude Haiku or GPT-4o-mini (cost-optimized). Structured output with enum validation. |
| Output event | `calllock/prospect.enriched` |
| Output schema | `{ prospect_id, tenant_id, trade, buyer_type, pain_profile, urgency_likelihood, call_volume_likelihood, wedge_fit_score, estimated_monthly_lost_revenue, field_confidences, enrichment_quality, enrichment_cost_cents }` |
| Write ownership | Writes to `enrichment_cache` (company-domain keyed) |
| Failure mode | Website unreachable: degrade to Google listing only. Scrape blocked (403/captcha): degrade to listing. Scrape too large (>5MB): skip website. LLM parse failure: retry once with stricter prompt, then emit with `enrichment_quality: partial`. LLM refusal: log, emit with `enrichment_quality: partial`, do not drop prospect. Revenue estimation unavailable: null field, proceed. |
| Cost cap | $0.02 per prospect target |

#### 2.5.3 Segmentation Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.enriched` |
| Input | Enriched prospect profile with tenant_id |
| Job | Assign primary segment based on enrichment signals. Set initial lifecycle state to REACHED (ready for outbound). Score prospect for sequence priority. |
| Segments (HVAC Phase 1) | `owner-operator-solo`, `owner-with-small-crew`, `growing-dispatcher`, `unclassified` |
| Output event | `calllock/prospect.segmented` |
| Output schema | `{ prospect_id, tenant_id, primary_segment, secondary_segment, lifecycle_state, prospect_score, segment_confidence }` |
| Write ownership | Segmentation Engine writes to `segment_assignments` |
| Failure mode | Low confidence: assign `unclassified`, flag for manual review batch. |

#### 2.5.4 Sequence Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.segmented` |
| Input | Segmented prospect with enrichment data and tenant_id |
| Job | Build a multi-touch email sequence using the message router and template system. Select angle, template family, proof assets, and CTA for each touch. Respect experiment assignments from the Experiment Allocator, including pricing arm (sticky per prospect). Query proof_assets table for available assets matching segment and angle. |
| Touch scheduling | Uses Inngest step.sleepUntil() to schedule each touch within a single long-running function. Each touch is a scheduled step. Function is cancellable via Inngest function cancellation. |
| Output event | `calllock/sequence.created` (after building sequence and scheduling all touches) |
| Output schema | `{ prospect_id, tenant_id, sequence_id, experiment_arm_id, pricing_arm, touches: [{ touch_number, send_at, template_id, angle, proof_asset_id, cta, subject_line, body_slots }], sequence_cost_cents }` |
| Write ownership | Writes to `journey_assignments` |
| Failure mode | No matching template: use default angle for segment. No proof asset available: use no-proof variant of touch. Experiment allocator unavailable: use current best performer. |

#### 2.5.5 Sender Agent

| Field | Value |
|-------|-------|
| Trigger | Inngest step within Sequence Agent function (after step.sleepUntil resolves) |
| Input | Assembled email from Sequence Agent output, tenant_id |
| Pre-send check | Query sequence status from Supabase. If status is `paused` or `cancelled`, skip touch and log. This prevents the race condition where a reply pauses the sequence after a touch was already scheduled. |
| CAN-SPAM compliance | Every outbound email must include: physical mailing address in footer, functioning unsubscribe link, clear sender identification, non-deceptive subject line. These are enforced as required template slots that the template system validates before rendering. |
| Job | Run through Outbound Health Gate checks. If cleared, send via email infrastructure. Log to `touchpoint_log`. All communications within a sequence use the assigned sender persona (mailbox). Auto-replies also use the sequence's assigned mailbox, not a system address. |
| Health gate checks | Suppress list, bounce and complaint thresholds, volume cap, duplicate-send window, domain reputation, lifecycle eligibility |
| Output event | `calllock/email.sent` or `calllock/email.blocked` |
| Write ownership | Appends to `touchpoint_log` |
| Failure mode | Health gate block: skip touch, log reason, alert if pattern. Send failure: retry once via Inngest step retry, then dead-letter. Sequence paused/cancelled: skip touch, log. |
| Sending infrastructure | Smartlead or Instantly API (multiple warmed domains, rotation) |

#### 2.5.6 Reply Classifier Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/email.reply.received` (webhook from email infrastructure, HMAC signature verified) |
| Webhook security | Verify HMAC signature from email infrastructure provider before processing. Reject unsigned or invalid requests with HTTP 401. Log rejections as `calllock/swarm.webhook.rejected`. |
| Input | Reply text (sanitized: strip HTML, limit 2,000 chars, remove non-printable), prospect context, sequence context, tenant_id |
| Job | Classify reply into actionable category. Extract structured data (objections, questions, intent signals). Map classification to conviction and readiness signals using the belief signal mapping table. |
| Classification categories | `positive_interest`, `question`, `objection`, `not_now_future`, `unsubscribe`, `wrong_person`, `out_of_office`, `bounce`, `irrelevant` |
| Belief signal mapping | See Section 2.6 |
| LLM | Claude Haiku. Structured output with confidence score. |
| Idempotency | Dedupe on reply message ID. Duplicate webhook deliveries are no-op. |
| Output event | `calllock/reply.classified` |
| Output schema | `{ prospect_id, tenant_id, sequence_id, reply_category, confidence, extracted_objections[], extracted_questions[], conviction_signal, readiness_signal, raw_reply_hash, classification_cost_cents }` |
| Write ownership | Appends to `touchpoint_log`. Objections feed Sales Insight Layer. Conviction and readiness signals feed dual-axis belief model. |
| Failure mode | Low confidence classification (<0.5): route to `needs_human_review` bucket. LLM hallucinated category (not in enum): route to `needs_human_review`. LLM parse failure: retry once, then `needs_human_review`. |

#### 2.5.7 Handoff and Escalation Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/reply.classified` |
| Input | Classified reply with prospect context and tenant_id |
| Doctrine check | Before any auto-reply, check doctrine registry. If doctrine is unavailable (DoctrineUnavailableError), fail closed: route ALL replies to founder review queue. Never auto-reply when doctrine status is unknown. Log `calllock/swarm.doctrine.unavailable`. |
| Job | Route based on classification |
| Routing rules | `positive_interest`: move to EVALUATING, create founder notification with handoff packet including sequence replay (see Section 2.8). `question`: if doctrine approves auto-reply AND matching proof asset exists: send proof via sequence's assigned mailbox, resume sequence. Else: founder review. `objection`: insert counter-proof touch if proof coverage is `covered` for that objection. Else: log to objection registry, founder review. `not_now_future`: move to DORMANT, schedule re-engagement in 60 or 90 days. `unsubscribe`: add to suppress list immediately, send unsubscribe confirmation, remove from all active sequences, initiate PII deletion (Section 8.3). `wrong_person`: flag, attempt to find correct contact. |
| Lifecycle transitions | Uses compare-and-set against current lifecycle state. On CAS conflict: retry once, then log and skip transition. Invalid transitions are logged and rejected. |
| Output events | `calllock/prospect.escalated`, `calllock/sequence.modified`, `calllock/prospect.suppressed` |
| Write ownership | Updates lifecycle state in `prospects` table, updates `journey_assignments` |
| Failure mode | Uncertain routing: founder review queue. Doctrine unavailable: fail closed, all to founder review. Invalid lifecycle transition: log, don't transition. CAS conflict: retry once, then log. |

### 2.6 Reply-to-belief signal mapping

Concrete mapping from reply classification to the growth doc's dual-axis conviction and readiness signals (Section 13.1):

| Reply Category | Conviction Signal | Readiness Signal | Rationale |
|---------------|------------------|-----------------|-----------|
| `positive_interest` | up | up | Prospect believes AND is ready to act |
| `question` | flat | flat | Seeking information, not committed either way |
| `objection` | down | flat | Actively doubts value, not refusing to engage |
| `not_now_future` | flat | down | May believe it works, but not ready now |
| `unsubscribe` | down | down | Rejected both value and timing |
| `wrong_person` | null | null | No signal (wrong recipient) |
| `out_of_office` | null | null | No signal (automated response) |
| `bounce` | null | null | No signal (delivery failure) |
| `irrelevant` | null | null | No signal (noise) |

Null signals are not written to Growth Memory. They do not influence conviction or readiness scoring.

### 2.7 Sequence health monitor

A daily cron job (`calllock/swarm.health.check.requested`, runs 8am local) that catches stalled sequences:

- Queries all active sequences where the next touch is overdue by more than 24 hours
- For each stalled sequence: re-triggers the Sender Agent step (re-emits the touch event)
- Logs `calllock/swarm.sequence.stalled` with sequence_id and overdue duration
- Alerts if more than 10 sequences are stalled simultaneously

This is a belt-and-suspenders mechanism for Inngest step.sleepUntil durability.

### 2.8 Sequence replay (delight)

When a prospect is escalated to the founder pipeline, the handoff packet includes a visual sequence replay showing the full journey:

```yaml
sequence_replay:
  touches:
    - touch: T1
      sent_at: "2026-03-16T07:00:00Z"
      angle: "missed-calls"
      subject: "Mike's HVAC: ~$4,200/mo in missed calls?"
      engagement: ["opened day 0"]
    - touch: T2
      sent_at: "2026-03-18T07:00:00Z"
      angle: "missed-calls"
      proof: "revenue-calculator (pre-filled $4,200)"
      engagement: ["opened day 2", "clicked calculator day 2"]
    - touch: T3
      sent_at: "2026-03-21T07:00:00Z"
      angle: "social-proof"
      engagement: ["replied day 6: 'This looks interesting...'"]
  conversion_path: "T1 opened -> T2 calculator clicked -> T3 reply (positive_interest)"
```

Data sourced from `touchpoint_log` and `journey_assignments`. Assembled by the Handoff Agent at escalation time.

## 3. Sequence Design

### 3.1 Core sequence structure

5-touch, 14-day sequence following a pain, proof, social, urgency, break-up arc. Maps to the Journey Orchestrator's narrative structure (growth doc Section 11.2).

| Touch | Day | Purpose | Angle Strategy | Content Strategy |
|-------|-----|---------|---------------|-----------------|
| T1 | 0 | Pain recognition | Lead with prospect's specific pain signal from enrichment. If enrichment found "leave a message" language or no after-hours coverage: missed-call angle. If high review volume plus slow response signals: interruption angle. Default: missed-calls. If estimated_monthly_lost_revenue is available, use in subject line (e.g., "Mike's HVAC: ~$4,200/mo in missed calls?"). | Short, specific, one question. No pitch. Subject line references their business by name. |
| T2 | 2 | Proof | Same angle, add evidence. | Link to proof asset. If revenue estimate exists, link to pre-filled calculator (/tools/missed-call-revenue-calculator?estimate=4200&business=mikes-hvac). Else: demo call snippet or stat. CTA: "worth a look?" |
| T3 | 5 | Social proof and comparison | Shift to "others like you" framing. | Reference a similar-sized HVAC shop's outcome. Or link comparison page. CTA: "see how it compares" |
| T4 | 9 | Urgency and seasonal | Add time dimension. | Tie to seasonal demand or cost-of-waiting framing. CTA: direct booking link for intro call with pricing arm's rate. |
| T5 | 14 | Break-up | Permission-based close. | "Seems like timing isn't right. Want me to check back in 60-90 days, or should I stop reaching out?" Binary choice. |

### 3.2 Timing rules

- Send windows: Tuesday through Thursday, 7:00-9:00 AM prospect local time. HVAC owners check email before crews dispatch.
- Never send: weekends, Mondays (catch-up day), Fridays (wind-down).
- Holiday suppression: skip federal holidays plus day before and after.
- Timezone: derived from prospect's business address at enrichment time.

### 3.3 Escalation logic

Escalation is triggered by prospect behavior between touches, not just at sequence end.

| Signal | Detected Via | Action | Lifecycle Transition |
|--------|-------------|--------|---------------------|
| Reply: positive interest | Reply Classifier: `positive_interest` | Pause sequence. Founder notification with full context and sequence replay. | REACHED to EVALUATING |
| Reply: question | Reply Classifier: `question` | If doctrine approves auto-reply AND matching proof asset exists: send proof via sequence mailbox, resume sequence. Else: founder review queue. | Stay REACHED, flag engaged |
| Reply: objection | Reply Classifier: `objection` | Insert counter-proof touch if proof coverage is `covered` for that objection. Else: log to objection registry, founder review. | Stay REACHED |
| Reply: not now | Reply Classifier: `not_now_future` | End sequence. Schedule re-engagement in 60 or 90 days. | REACHED to DORMANT |
| Reply: unsubscribe | Reply Classifier: `unsubscribe` | Immediate suppress. Confirmation email via sequence mailbox. Remove from all active sequences. Initiate PII deletion per Section 8.3. | REACHED to LOST (reason: opt-out) |
| Link click | Touchpoint log via tracking | Do not accelerate sequence. Boost prospect score and log conviction signal up. | Stay current state |
| Email bounce | Sender Agent webhook | Hard bounce: suppress. Soft bounce: retry next touch, suppress after 2 soft bounces. | Remove from sequence |
| No engagement after T5 | Sequence completion | Move to cold pool. Eligible for re-engagement in 6 months with a different angle. | REACHED to DORMANT |

### 3.4 Re-engagement sequences

Prospects who completed a sequence without converting or who went DORMANT via "not now" get a 2-touch re-engagement after their dormancy period.

| Touch | Day | Strategy |
|-------|-----|----------|
| R1 | 0 | New angle or new proof asset that did not exist when they were last contacted. Pricing arm remains sticky (original assignment). |
| R2 | 4 | Break-up. If no response, move to long-term cold pool (12-month cycle). |

Hard rule: a prospect receives a maximum of 2 full sequences (initial plus one re-engagement) per 12-month period.

### 3.5 Experiment allocator controls

The sequence structure (Section 3.1) is fixed. What the Experiment Allocator varies within the structure:

| Element | Varied By | Example |
|---------|-----------|---------|
| Angle per touch | Experiment arm | T1 uses missed-calls vs. after-hours vs. interruption |
| Template per touch | Experiment arm | Same angle, different copy treatment |
| Proof asset | Experiment arm plus proof coverage | Calculator vs. demo call vs. stat |
| CTA | Experiment arm | Question CTA vs. direct booking link |
| Subject line | Experiment arm | Personalized ($-amount) vs. pain-statement vs. curiosity |
| Pricing tier | Pricing experiment arm (founder-gated) | $149 vs. $199 vs. $249 in T4 CTA |

The Experiment Allocator assigns arms at sequence creation time (per growth doc Section 10.8). The entire sequence runs as one cohesive arm. No mid-sequence variant switching.

### 3.6 Deliverability architecture

| Component | Specification |
|-----------|--------------|
| Sending domains | 3-5 secondary domains (e.g., calllockteam.com, getcalllock.com). Never send cold email from primary domain. |
| Mailboxes per domain | 2-3 warmed mailboxes each. Total: 6-15 sending accounts. |
| Warmup protocol | 14-day warmup per new mailbox before production sends. Use warmup service built into email infrastructure provider. |
| Daily send cap | 30-50 emails per mailbox per day. Scale by adding mailboxes, not volume per mailbox. |
| Total daily capacity | 180-750 emails per day at steady state (6-15 mailboxes times 30-50). |
| Rotation | Round-robin across mailboxes. Same prospect always gets the same sender persona for sequence continuity. All auto-replies within a sequence use the same persona. |
| Bounce threshold | Pause mailbox if bounce rate exceeds 3%. Investigate before resuming. |
| Complaint threshold | Pause mailbox if spam complaint rate exceeds 0.1%. |
| SPF/DKIM/DMARC | Configured on all sending domains before first send. Non-negotiable. |

### 3.7 CAN-SPAM compliance

Every outbound cold email must include:

- Physical mailing address in email footer (required template slot, validated before render)
- Functioning unsubscribe link (required template slot, links to immediate suppress endpoint)
- Clear sender identification (From name and address identify the sender)
- Non-deceptive subject lines (template validation rejects misleading claims)
- Unsubscribe requests honored within 24 hours (automated via Handoff Agent suppress flow)

These are enforced as required slots in the template system. A template that is missing any CAN-SPAM slot fails validation and cannot be sent.

## 4. Handoff Protocol

### 4.1 Handoff triggers

A prospect enters the handoff pipeline when any of these fire:

| Trigger | Source | Priority | SLA |
|---------|--------|----------|-----|
| Reply classified `positive_interest` | Reply Classifier Agent | P1 Hot | Founder contact within 4 hours |
| Reply classified `question` plus high readiness signal | Reply Classifier Agent | P2 Warm | Founder contact within 24 hours |
| Prospect books intro call via CTA link | Cal.com webhook (HMAC verified) via `calllock/meeting.booked` | P1 Hot | Auto-confirmed, founder prepares |
| Calculator completed plus high engagement dwell | Touchpoint log | P3 Interested | Add to next founder call block |

### 4.2 Handoff packet

When the Handoff Agent escalates a prospect, it assembles a founder context packet including the sequence replay (Section 2.8):

```yaml
handoff_packet:
  prospect:
    business_name: string
    owner_name: string
    phone: string
    email: string
    website: string
    trade: string
    employee_count_est: number
    revenue_est: number
    estimated_monthly_lost_revenue: number | null
    segment: string
    prospect_score: number
  enrichment:
    pain_profile: string
    urgency_likelihood: string
    key_signals: string[]
  sequence_replay:
    # Full sequence journey visualization (see Section 2.8)
  reply_context:
    reply_text: string
    classification: string
    extracted_questions: string[]
    extracted_objections: string[]
    conviction_signal: enum(up, flat, down)
    readiness_signal: enum(up, flat, down)
  recommended_talking_points: string[]
  pricing_arm: string  # Which price this prospect has seen
```

### 4.3 Founder pipeline

Simple Kanban that the founder works daily:

| Stage | Meaning | Action | Lifecycle State |
|-------|---------|--------|----------------|
| New | Handoff packet received | Review packet, decide to pursue | EVALUATING |
| Contacted | Founder has reached out | Awaiting response | EVALUATING |
| Meeting Set | Intro call scheduled | Prepare using packet | IN_PIPELINE |
| Pilot Proposed | Prospect has seen pricing and offer | Follow up | IN_PIPELINE |
| Pilot Started | Prospect is live on CallLock | Onboard, check in at day 3, 7, 14 | PILOT_STARTED |
| Won | Converted to paying customer | Record outcome | CUSTOMER |
| Lost | Declined or went dark | Log structured reason | LOST |

### 4.4 Feedback loop

Outcomes flow back into the swarm through Growth Memory:

| Outcome | Feeds Into | Effect |
|---------|-----------|--------|
| Won | `segment_performance`, `angle_effectiveness`, `proof_effectiveness` | Reinforces the sequence that worked |
| Lost (reason: price) | `loss_records`, `objection_registry` | Triggers pricing objection proof gap analysis |
| Lost (reason: not ready) | `loss_records` | Prospect moves to DORMANT with re-engagement at 90 days |
| Lost (reason: competitor) | `competitor_mentions`, `loss_records` | Feeds battlecard creation |
| Pilot churned | `churn_records` | Feeds conviction and readiness model — was readiness inflated? |

## 5. The Scorecard

### 5.1 Primary metrics (weekly review)

| Metric | Formula | Target | Red Flag |
|--------|---------|--------|----------|
| LTV:CAC Ratio | LTV divided by (all-in monthly swarm cost divided by new customers) | 3:1 or higher | Below 2:1 for 3 consecutive weeks |
| CAC | Total swarm cost divided by new customers acquired (from cost tracking, Section 1.3) | Below $800 | Above $1,200 |
| Payback Period | CAC divided by (MRR times gross margin) | Below 6 months | Above 9 months |
| Monthly New Customers | Count of PILOT_STARTED or CUSTOMER | Growth month-over-month | Flat or declining for 4+ weeks |

### 5.2 Leading indicators (daily glance)

| Indicator | What It Tells You | Healthy Range | Action If Off |
|-----------|------------------|---------------|---------------|
| Deliverability rate | Are emails landing in inboxes? | Above 95% | Pause affected mailboxes, investigate domain or content |
| Open rate | Are subject lines and sender reputation working? | 40-60% (cold email SMB) | Test new subject lines, check warmup health |
| Reply rate | Is the angle resonating? | 3-8% | Experiment with angles, check enrichment quality |
| Positive reply rate | Are replies converting to pipeline? | 30-50% of all replies | Review reply classifier accuracy, check ICP fit |
| Escalation-to-meeting rate | Are hot leads converting to calls? | Above 50% of P1 handoffs | Check founder response SLA, improve handoff packet |
| Bounce rate per mailbox | Is lead data quality holding? | Below 3% | Tighten prospecting filters, verify email addresses pre-send |
| Complaint rate per mailbox | Are you annoying people? | Below 0.1% | Reduce volume, improve targeting, check content |

### 5.3 Hiring trigger points

| Trigger | Evidence Required | Action |
|---------|------------------|--------|
| Swarm is CAC-efficient but capacity-constrained | LTV:CAC at 3:1 or higher for 8+ weeks AND daily send capacity above 80% utilized AND pipeline is converting | Add mailboxes and sending domains to increase volume |
| Founder is the bottleneck | Handoff queue above 10 prospects AND founder SLA is slipping (above 24hr on P1s) AND conversion from handoff-to-pilot above 30% | Hire first AE or closer. Hand them the pipeline plus handoff packet format. |
| Swarm needs supervision | Reply classifier accuracy below 85% OR enrichment quality degrading OR experiment velocity is bottlenecked on review | Hire growth ops or part-time SDR to manage swarm health and founder review queue |
| LTV:CAC at 5:1 or higher sustained | 12+ weeks of 5:1+ with stable churn | Double sending infrastructure. Expand to Plumbing wedge. |

### 5.4 Founder weekly ritual (15 minutes)

Maps to the growth doc's Founder Dashboard (Section 10.16) levels:

| Step | Time | Dashboard Level | What You Check |
|------|------|----------------|----------------|
| 1. Is it working? | 3 min | Level 1 | Deliverability, send volume, bounce and complaint rates. Any mailbox paused? Check activity feed for anomalies. |
| 2. What is converting? | 5 min | Level 2 | Reply rate by angle, positive reply rate by segment, escalation-to-meeting rate. Check experiment winner celebrations. |
| 3. What should I do? | 5 min | Level 3 | Review handoff queue (P1s first). Approve or reject pending experiment proposals or asset approvals. Review pricing experiment progress. |
| 4. What happened? | 2 min | Level 4 | Losses this week and why. New objections logged. Any churn. |

## 6. Swarm Infrastructure

### 6.1 Growth Memory tables (swarm-specific)

These 8 tables are the swarm's storage layer. They follow the growth doc's RLS and tenant isolation patterns. All tables have `tenant_id` column with row-level security policies.

| Table | Purpose | Write Owner | Key Fields |
|-------|---------|------------|------------|
| `prospects` | Dedupe registry and prospect master record | Prospector Agent | prospect_id, tenant_id, business_domain (unique per tenant), email, lifecycle_state, created_at |
| `enrichment_cache` | Cached enrichment results, keyed by domain | Enrichment Agent | prospect_id, tenant_id, business_domain, enrichment_data (JSONB), enrichment_quality, estimated_monthly_lost_revenue, enriched_at |
| `segment_assignments` | Current segment per prospect | Segmentation Agent | prospect_id, tenant_id, primary_segment, secondary_segment, confidence, assigned_at |
| `journey_assignments` | Active sequences and touch schedules | Sequence Agent | sequence_id, prospect_id, tenant_id, experiment_arm_id, pricing_arm, status (active/paused/cancelled/completed), touches (JSONB), created_at |
| `touchpoint_log` | Immutable append-only event log | All agents (append-only) | touchpoint_id, tenant_id, prospect_id, sequence_id, touchpoint_type, channel, experiment_id, arm_id, conviction_signal, readiness_signal, cost_cents, created_at |
| `suppress_list` | Prospects who must not be contacted | Handoff Agent | tenant_id, email, business_domain, reason, suppressed_at |
| `proof_assets` | Proof asset registry | Founder (manual or asset pipeline) | asset_id, tenant_id, asset_type, target_trade, pain_angle, lifecycle_stage, url, status (active/draft/retired), version, created_at |
| `pipeline` | Founder sales pipeline (Kanban) | Handoff Agent + Founder | prospect_id, tenant_id, stage, handoff_packet (JSONB), sequence_replay (JSONB), pricing_arm, created_at, updated_at |
| `cost_per_acquisition` | Rolling cost aggregation | Cost Aggregation Job | tenant_id, period_start, period_end, total_cost_cents, customers_acquired, cac_cents, computed_at |

### 6.2 Proof asset seed data (HVAC Phase 1)

5 seed assets loaded at deployment:

| Asset ID | Type | Pain Angle | URL | Status |
|----------|------|-----------|-----|--------|
| hvac-demo-call | demo_call | missed-calls | /demo/hvac-booking-call | active |
| hvac-revenue-calc | calculator | missed-calls | /tools/missed-call-revenue-calculator | active |
| hvac-comparison | comparison | better-than-voicemail | /compare/hvac-answering-service-vs-ai-receptionist | active |
| hvac-workflow | walkthrough | interruption | /hvac/ai-receptionist | active |
| hvac-faq | faq_pack | general | /hvac/faq | active |

The calculator supports pre-filling via query parameters: `/tools/missed-call-revenue-calculator?estimate=4200&business=mikes-hvac`. When the Enrichment Agent provides `estimated_monthly_lost_revenue`, T2 links to the pre-filled calculator. The prospect sees their estimated impact immediately.

### 6.3 API key management

All external API keys are stored as Render environment variables. Keys are referenced by name in agent configuration, never hardcoded.

| Service | Env Var | Rotation Protocol |
|---------|---------|------------------|
| Apollo | `APOLLO_API_KEY` | Rotate quarterly. Old and new keys valid concurrently during rotation window. |
| Google Maps | `GOOGLE_MAPS_API_KEY` | Rotate quarterly. |
| Email infrastructure | `EMAIL_INFRA_API_KEY` | Rotate quarterly. |
| Email infrastructure webhook secret | `EMAIL_INFRA_WEBHOOK_SECRET` | Rotate when compromised. Used for HMAC verification. |
| Cal.com webhook secret | `CALCOM_WEBHOOK_SECRET` | Rotate when compromised. Used for HMAC verification. |
| LLM provider | `LITELLM_API_KEY` (existing) | Existing harness rotation protocol. |

The Prospector Agent's credential health check (Section 2.5.1) verifies Apollo key validity before each batch. A `calllock/swarm.credential.expiring` alert fires 7 days before known expiry for services that expose expiry dates.

## 7. Observability

### 7.1 Agent-level metrics

Sourced from Inngest dashboard and structured logs:

- Per agent: invocations per day, success rate, p50 and p95 latency, error count by exception type
- Per event: emission count, consumption count, processing lag
- Structured logs at entry, exit, and each significant branch for all agent codepaths

### 7.2 Pipeline funnel metrics (Founder Dashboard v0)

Displayed on `/dashboard/growth`:

```
Prospects sourced -> Enriched -> Segmented -> Sequenced -> Sent -> Opened -> Replied -> Escalated -> Meeting -> Pilot -> Won
```

Each stage shows:
- Count (today, 7-day, 30-day)
- Conversion rate to next stage
- Daily trend (up/down/flat indicator)
- Color coding: green (healthy range), yellow (watch), red (action needed) per Section 5.2 thresholds

### 7.3 Activity feed (delight)

Real-time reverse-chronological feed on the Founder Dashboard showing agent activity:

- "Prospector found 47 HVAC shops in Austin (batch #1234)"
- "Enrichment analyzed mikeshvac.com — wedge fit: 0.87, est. lost revenue: $4,200/mo"
- "Sequence built for Mike's HVAC — angle: missed-calls, arm: $199, 5 touches scheduled"
- "Email sent to mike@mikeshvac.com — T1: 'Mike's HVAC: ~$4,200/mo in missed calls?'"
- "Reply received from mike@mikeshvac.com — classified: positive_interest (confidence: 0.94)"
- "Hot lead escalated: Mike's HVAC — handoff packet ready"

Sourced from Inngest event stream. Each entry links to the relevant prospect record.

### 7.4 Experiment winner celebration (delight)

When the Experiment Allocator declares a winner, surface it prominently on the Founder Dashboard:

- Banner notification: "Winner declared: missed-calls angle converts 2.3x better than after-hours for owner-operator-solo segment"
- Details: sample size, confidence level, effect size, date range
- Action: "Applied to all new sequences" (or "Awaiting your approval" if founder-gated)
- Historical list of all winner declarations on the dashboard

### 7.5 P0 alerts

4 alerts that fire immediately and notify the founder:

| Alert | Trigger | Channel |
|-------|---------|---------|
| Credential failure | `calllock/swarm.credential.failed` event | Email + SMS |
| Deliverability crisis | Deliverability rate drops below 90% for any mailbox | Email |
| Pipeline halt | Zero prospects sourced for 2 consecutive days | Email |
| Mass stall | Sequence health monitor finds more than 10 stalled sequences | Email |

## 8. Security and Data

### 8.1 Input sanitization

All agents that process untrusted external text (Enrichment Agent, Reply Classifier) apply sanitization before LLM processing:

- Strip all HTML tags
- Limit input to maximum character count (5,000 for web scrapes, 2,000 for replies)
- Remove non-printable characters
- Strip known prompt injection patterns
- All LLM structured outputs validated against enum fields; invalid values rejected

### 8.2 Webhook security

All inbound webhooks (email reply, Cal.com meeting booked) require HMAC signature verification:

- Webhook secret stored in Render env var
- HMAC computed over request body using SHA-256
- Invalid or missing signature: reject with HTTP 401
- Log `calllock/swarm.webhook.rejected` with source IP and timestamp

### 8.3 Data classification and retention

Prospect data is Tier 3 (identifiable) per growth doc Section 9.7.

| Data | Classification | Retention | Deletion Trigger |
|------|---------------|-----------|-----------------|
| Prospect PII (name, email, phone) | Tier 3 | 18 months from last activity | Unsubscribe or retention expiry |
| Enrichment data | Tier 2 (pseudonymous after PII removal) | 18 months | Linked to prospect deletion |
| Reply text | Tier 3 | 18 months | Linked to prospect deletion |
| Touchpoint log (aggregate) | Tier 1 (aggregate-safe) | Indefinite | Never (anonymized) |
| Logs | Tier 2 | 90 days | Automatic |

PII in logs: agents log `prospect_id` only. Never log email, phone, name, or reply text in structured logs. The existing PII redactor (ADR 003) is applied to all agent log output.

On unsubscribe: PII is deleted from `prospects`, `enrichment_cache`, `pipeline`, and `suppress_list.email` within 30 days. The `suppress_list` retains a hashed business_domain entry permanently to prevent re-contact. Aggregate touchpoint data is retained (anonymized).

## 9. Test Strategy

### 9.1 Unit tests (per agent)

Each agent has a test suite that mocks its inputs (Inngest events) and external dependencies (APIs, LLM). Tests cover:

- Happy path
- Each error path from the error and rescue map
- Edge cases: nil input, empty response, malformed LLM output, duplicate events
- Tenant isolation: verify agent only reads/writes data for the specified tenant_id

### 9.2 Integration tests

Full pipeline test using Inngest's test mode (local event bus, no real delivery):

- Seed data: 5 fake HVAC prospects with varied enrichment profiles
- Verify: prospect flows from sourced through enriched, segmented, sequenced, and sent (to mock)
- Verify: reply triggers correct classification and handoff
- Verify: pricing experiment arms are assigned and sticky
- Verify: unsubscribe triggers full suppress and PII deletion flow
- Verify: sequence status check prevents sends to paused sequences
- Verify: dedupe prevents duplicate sequences for same prospect

### 9.3 Shadow mode

Before going live, run the full pipeline against real Apollo data with email sending disabled:

- Sender Agent logs "would send" with full email content instead of calling email API
- All other agents run normally: real prospecting, real enrichment, real segmentation, real sequencing
- Founder reviews shadow output: are prospects right? Are sequences reasonable? Are enrichments accurate?
- Shadow mode runs during the 14-day mailbox warmup period

### 9.4 Shadow mode graduation criteria

Shadow mode ends when ALL of the following are met:

- Enrichment accuracy above 80% (founder spot-checks 50 prospects)
- Segmentation distribution matches expected ICP mix (no single segment exceeds 70%)
- Sequence templates render correctly for all segment and angle combinations
- No PII detected in structured logs (automated scan)
- Health Gate correctly blocks test-suppressed prospects
- Founder explicitly approves go-live

## 10. Deployment

### 10.1 Deployment sequence

```
PHASE 0: INFRASTRUCTURE (week 1)
  1. Supabase migrations: 8 swarm tables + proof_assets + pipeline + cost_per_acquisition
  2. RLS policies on all new tables
  3. Inngest event schemas: 14 new types in schemas.ts
  4. Secondary email domains: purchase 3-5, configure SPF/DKIM/DMARC
  5. Email infrastructure account setup
  6. Apollo API key provisioned
  7. Google Maps API key provisioned
  8. Render env vars updated with all new keys
  9. Mailbox warmup begins (14 days)
  10. Seed 5 HVAC proof assets

PHASE 1: AGENTS (week 1-2, parallel with warmup)
  11. Harness endpoints: /growth/swarm/* routes with tenant context guard
  12. Prospector Agent + credential health check + unit tests
  13. Enrichment Agent + input sanitization + revenue estimation + unit tests
  14. Segmentation Agent + unit tests
  15. Sequence Agent + experiment allocator + pricing arm + step.sleepUntil + unit tests
  16. Sender Agent + health gate + sequence status check + CAN-SPAM slots + unit tests
  17. Reply Classifier Agent + belief signal mapping + HMAC verification + unit tests
  18. Handoff Agent + doctrine fail-closed + sequence replay + unit tests
  19. Sequence health monitor cron
  20. Cost aggregation job
  21. Inngest function handlers (14 thin TS wrappers)

PHASE 2: INTEGRATION + SHADOW (week 2-3)
  22. Integration tests via Inngest test mode
  23. Shadow mode: real prospecting at 50/day, no sending
  24. Founder reviews shadow output against graduation criteria

PHASE 3: GO LIVE (week 3-4, after warmup + graduation)
  25. Enable Sender Agent (real sends)
  26. Ramp: 25% of capacity week 1, 50% week 2, 75% week 3, 100% week 4
  27. Founder Dashboard v0 deployed (scorecard + funnel + activity feed)
  28. Pipeline Kanban operational
  29. P0 alerts configured
  30. Daily monitoring begins
```

### 10.2 Phased startup

During the 14-day warmup period:

- Prospector runs at 50 prospects per day (not 200)
- Enrichment, Segmentation, and Sequence run in shadow mode (create sequences but do not schedule real touches)
- On go-live day, start scheduling real touches for NEW prospects only
- Shadow-mode prospects do NOT get retroactive sequences. They enter the live pipeline fresh if still eligible.
- Ramp sends 25% per week to protect freshly warmed mailboxes

### 10.3 Kill switch

Three-level emergency stop, each executable as a single command with no code deploy:

| Level | Action | Command | Effect |
|-------|--------|---------|--------|
| PAUSE | Disable daily prospecting cron | Inngest function pause | No new prospects enter pipeline. In-flight sequences continue on schedule. Replies still classified. |
| FREEZE | Pause cron AND set all active sequences to `paused` | Inngest pause + Supabase bulk update: `UPDATE journey_assignments SET status = 'paused' WHERE status = 'active'` | No new prospects AND no further sends. Sender Agent's status check prevents sends. Replies still classified and routed to founder. |
| SHUTDOWN | Freeze AND disable webhook endpoints AND remove Inngest function registrations | Inngest pause + Supabase update + Render env toggle (`SWARM_ENABLED=false`) | Full stop. No processing of any kind. |

## 11. Growth System Integration Points

This section maps swarm outputs to their downstream consumers in the growth doc, ensuring schema compatibility for Phase 2-3.

| Swarm Output | Growth Memory Table | Downstream Consumer | Required Fields for Compatibility |
|-------------|--------------------|--------------------|----------------------------------|
| Touchpoint events | `touchpoint_log` | Experiment Allocator (Section 10.8) | `experiment_id`, `arm_id` — required for winner declaration |
| Touchpoint events | `touchpoint_log` | Attribution views (Section 10.17) | `attribution_token`, `channel` — required for path attribution |
| Reply classifications | `touchpoint_log` | Sales Insight Layer (Section 10.9) | `extracted_objections[]` — feeds objection taxonomy |
| Conviction/readiness signals | `touchpoint_log` | Conviction and Readiness Layer (Section 13.1) | `conviction_signal`, `readiness_signal` — must use dual-axis format, not legacy single-axis `belief` |
| Loss records | Via feedback loop | Loss Analysis Engine (Section 12.10) | Structured reason codes: `price`, `not_ready`, `competitor`, `no_response`, `bad_fit` — must be enumerated, not free text |
| Segment performance | `segment_performance` | Growth Advisor (Section 10.14) | `experiment_id`, `arm_id`, `conversion_count`, `cost_cents` — required for cost-weighted Thompson sampling |
| Prospect lifecycle transitions | `prospects.lifecycle_state` | Journey Orchestrator (Section 11.2) | Must use canonical lifecycle states from growth doc Section 11.1. No custom states. |
| Cost data | `cost_per_acquisition` | Cost Layer (Section 10.19) | `period_start`, `period_end`, `total_cost_cents`, `customers_acquired` — required for value-per-dollar optimization |

## Appendix A: Inngest Event Catalog

All events follow the `calllock/` namespace convention per ADR 015. All payloads include `tenant_id` as a required field.

| Event | Producer | Consumer | Payload Key Fields |
|-------|----------|----------|--------------------|
| `calllock/prospecting.batch.requested` | Cron (daily 6am) | Prospector Agent | tenant_id, wedge, geo_filters, batch_size |
| `calllock/prospect.sourced` | Prospector Agent | Enrichment Agent | tenant_id, prospect_id, business_name, email, source, batch_id, prospecting_cost_cents |
| `calllock/prospect.enriched` | Enrichment Agent | Segmentation Agent | tenant_id, prospect_id, trade, pain_profile, wedge_fit_score, estimated_monthly_lost_revenue, field_confidences, enrichment_cost_cents |
| `calllock/prospect.segmented` | Segmentation Agent | Sequence Agent | tenant_id, prospect_id, primary_segment, lifecycle_state, prospect_score |
| `calllock/sequence.created` | Sequence Agent | (internal: schedules touches) | tenant_id, prospect_id, sequence_id, experiment_arm_id, pricing_arm, touches[] |
| `calllock/email.sent` | Sender Agent | Touchpoint log | tenant_id, prospect_id, sequence_id, touch_number, mailbox_id, send_cost_cents |
| `calllock/email.blocked` | Sender Agent | Alerting | tenant_id, prospect_id, block_reason |
| `calllock/email.reply.received` | Email infra webhook | Reply Classifier Agent | tenant_id, prospect_id, sequence_id, reply_text |
| `calllock/reply.classified` | Reply Classifier Agent | Handoff Agent | tenant_id, prospect_id, reply_category, confidence, conviction_signal, readiness_signal, classification_cost_cents |
| `calllock/prospect.escalated` | Handoff Agent | Founder pipeline | tenant_id, prospect_id, priority, handoff_packet |
| `calllock/sequence.modified` | Handoff Agent | Sender Agent | tenant_id, sequence_id, modification_type, inserted_touch |
| `calllock/prospect.suppressed` | Handoff Agent | Suppress list | tenant_id, prospect_id, reason |
| `calllock/meeting.booked` | Cal.com webhook | Founder pipeline | tenant_id, prospect_id, meeting_time |
| `calllock/swarm.credential.failed` | Prospector Agent | P0 Alert | tenant_id, service, error_message |
| `calllock/swarm.webhook.rejected` | Webhook middleware | Logging | source_ip, reason |
| `calllock/swarm.sequence.stalled` | Sequence Health Monitor | Alerting | tenant_id, sequence_id, overdue_hours |
| `calllock/swarm.health.check.requested` | Cron (daily 8am) | Sequence Health Monitor | tenant_id |
| `calllock/swarm.doctrine.unavailable` | Handoff Agent | Logging | tenant_id, error_message |
| `calllock/swarm.tenant.scope.failed` | Tenant context guard | Logging | attempted_tenant_id, error_message |

## Appendix B: Authority and Deference Map

| Topic | Authority | This Spec's Role |
|-------|-----------|-----------------|
| Growth Memory tables and write ownership | Growth system design doc Section 9 | Defers for architecture. Defines 8 swarm-specific tables within that framework. |
| Experiment allocation and winner declaration | Growth system design doc Section 10.8 | Defers. Adds pricing experiment as first founder-gated experiment. |
| Segmentation engine behavior | Growth system design doc Section 10.2 | Defers. Segmentation Agent implements the engine. |
| Signal quality and learning integrity | Growth system design doc Sections 10.11, 10.12 | Defers. All events scored before influencing Growth Memory. |
| Doctrine and proof coverage | Growth system design doc Sections 13.2, 13.3 | Defers. Handoff Agent fails closed on doctrine unavailability. |
| Outbound health gate | Growth system design doc Section 10.13 | Defers. Sender Agent runs through the gate. |
| Conviction and readiness semantics | Growth system design doc Section 13.1 | Defers. Reply Classifier uses concrete belief signal mapping (Section 2.6). |
| Runtime placement | ADR 010 | Aligns. Python agents in harness, TS Inngest wrappers. |
| Event naming convention | ADR 015 | Aligns. All events use calllock/ prefix. |
| Tenant isolation | Architecture spec | Aligns. RLS on all tables, tenant context guard on all endpoints. |
| Pricing model and experiment | This document Sections 1.1, 1.2 | Authoritative. |
| Agent orchestration pipeline | This document Section 2 | Authoritative. |
| Sequence structure and timing | This document Section 3 | Authoritative. |
| Handoff protocol and founder pipeline | This document Section 4 | Authoritative. |
| LTV:CAC scorecard and hiring triggers | This document Section 5 | Authoritative. |
| Swarm infrastructure (tables, assets, keys) | This document Section 6 | Authoritative. |
| Observability and alerting | This document Section 7 | Authoritative. |
| Security and data retention | This document Section 8 | Authoritative. |
| Test strategy and shadow mode | This document Section 9 | Authoritative. |
| Deployment and kill switch | This document Section 10 | Authoritative. |
| Growth system integration points | This document Section 11 | Authoritative. |
| Inngest event catalog for the swarm | This document Appendix A | Authoritative, following ADR 015 convention. |

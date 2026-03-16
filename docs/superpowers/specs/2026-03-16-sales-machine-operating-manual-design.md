# Sales Machine Operating Manual

**Date:** March 16, 2026
**Status:** Draft - v1
**Owner:** Founder / GTM
**Companion to:** `knowledge/growth-system/design-doc.md`

## Summary

This document is the operational companion to the CallLock Agentic Growth Loop design doc. It defines the concrete sales machine that turns the growth system's architecture into a running cold email outbound engine targeting HVAC single-owner shops.

The growth system design doc owns system architecture: Growth Memory, event bus, experiment allocation, segmentation, signal quality, doctrine, proof coverage, and wedge fitness. This document owns the operational layer: pricing model, unit economics, agent orchestration, sequence design, handoff protocol, and the LTV:CAC scorecard.

If this document conflicts with the growth system design doc on system architecture or object semantics, the growth system design doc wins. If the growth system design doc is silent on operational execution detail, this document is authoritative.

## 1. Pricing Model and Unit Economics

### 1.1 Pricing scenarios

Three scenarios for CallLock's HVAC SMB plan, modeled against a 3:1 LTV:CAC floor.

LTV formula: `ARPU x Gross Margin / Monthly Churn`

| Scenario | MRR | Gross Margin | Monthly Churn | LTV | Max CAC at 3:1 | Sweet Spot CAC | Payback Period |
|----------|-----|-------------|---------------|-----|----------------|----------------|----------------|
| Starter | $99 | 85% | 4% | $2,104 | $701 | $350-500 | 4-5 months |
| Core | $199 | 85% | 3% | $5,638 | $1,879 | $500-800 | 3-4 months |
| Pro | $299 | 85% | 2.5% | $10,166 | $3,389 | $800-1,200 | 3-4 months |

### 1.2 Recommended launch tier

Launch at **Core ($199/mo)**.

Rationale:

- $199 is defensible for a tool that recovers $500-5,000+ in missed revenue per month for HVAC shops.
- 3:1 LTV:CAC gives a CAC budget up to ~$1,879, which is generous for automated cold email where typical SMB acquisition cost is $200-600.
- Leaves room for a $99 downmarket wedge later if needed.
- The 3% monthly churn assumption is conservative for a product with hard-dollar ROI. If actual churn is 2%, LTV jumps to $8,458.

### 1.3 CAC budget breakdown

Monthly cost structure for the agentic email swarm at Core tier:

| Cost Component | Monthly Estimate | Notes |
|----------------|-----------------|-------|
| Lead data (Apollo or similar) | $200-400 | ~2,000-5,000 enriched prospects per month |
| Email infrastructure (Instantly/Smartlead + warmup) | $100-200 | Multiple sending domains |
| LLM costs (personalization, classification) | $50-150 | GPT-4o-mini or Claude Haiku tier |
| Founder time (review, approvals, calls with warm leads) | $0 | Valued at $0 for bootstrapped model |
| **Total monthly swarm cost** | **$350-750** | |

At 20 new customers per month (target): CAC = $18-38. At 5 customers per month (realistic early): CAC = $70-150. Both are well within the 3:1 band.

### 1.4 Key insight

Automated cold email is the highest-leverage channel for this ICP and price point. The constraint is not cost. The constraint is deliverability and conversion rate.

## 2. Agentic Email Swarm Architecture

### 2.1 Design principles

The swarm is not one monolithic agent. It is a pipeline of specialized agents, each with a single job, chained through the Inngest event bus. This matches the growth doc's single-writer ownership model (Section 9.2) and makes each agent independently testable, replaceable, and observable.

### 2.2 Pipeline overview

```
Trigger (cron / manual batch)
    |
    v
Prospector Agent        -- finds and filters raw leads
    | calllock/prospect.sourced
    v
Enrichment Agent        -- enriches with trade, pain profile, wedge fit (growth doc 10.1)
    | calllock/prospect.enriched
    v
Segmentation Agent      -- assigns segment + lifecycle state (growth doc 10.2, 11.1)
    | calllock/prospect.segmented
    v
Sequence Agent          -- builds multi-touch email sequence (growth doc 10.3, 10.4, 11.2)
    | calllock/sequence.created
    v
Sender Agent            -- executes sends through outbound health gate (growth doc 10.13)
    | calllock/email.sent
    v
Reply Classifier Agent  -- classifies responses and routes next action
    | calllock/reply.classified
    v
Handoff / Escalation Agent -- warm leads to founder, objections to re-sequence, unsubscribe to suppress
```

### 2.3 Agent specifications

#### 2.3.1 Prospector Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospecting.batch.requested` (daily cron, 6am local) |
| Input | Target wedge (HVAC), geographic filters, batch size cap |
| Data sources | Apollo API (primary), Google Maps enrichment (secondary) |
| Job | Query for HVAC businesses matching ICP filters. Dedupe against existing prospects in Growth Memory. Output raw prospect records. |
| ICP filters | Trade: HVAC. Employees: 1-15. Revenue: inferred $300K-$3M. Has phone number. Has website or Google listing. No existing CallLock customer. Not in suppress list. |
| Output event | `calllock/prospect.sourced` -- one per prospect, batch_id for traceability |
| Output schema | `{ prospect_id, business_name, phone, email, website, google_listing_url, employee_count_est, revenue_est, source, batch_id }` |
| Write ownership | Appends to `touchpoint_log` (append-only, per growth doc Section 9.2) |
| Failure mode | API rate limit: back off and resume. Zero results: alert, do not retry. Partial batch: emit what you have, log gap. |
| Daily cap | 200 prospects per batch (tunable) |

#### 2.3.2 Enrichment Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.sourced` |
| Input | Raw prospect record |
| Job | Scrape website and Google listing. LLM-analyze for: services offered, review sentiment, response patterns (do they mention "leave a message"?), after-hours behavior, team size signals, urgency indicators. Output enriched profile with per-field confidence scores. |
| LLM | Claude Haiku or GPT-4o-mini (cost-optimized). Structured output with enum validation. |
| Output event | `calllock/prospect.enriched` |
| Output schema | Growth doc Section 10.1 enrichment output: `{ prospect_id, trade, buyer_type, pain_profile, urgency_likelihood, call_volume_likelihood, wedge_fit_score, field_confidences, enrichment_cost_cents }` |
| Write ownership | Writes to prospect enrichment cache (company-domain keyed, per Section 10.1) |
| Failure mode | Website unreachable: degrade to Google listing only. LLM parse failure: retry once, then emit with `enrichment_quality: partial`. |
| Cost cap | $0.02 per prospect target |

#### 2.3.3 Segmentation Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.enriched` |
| Input | Enriched prospect profile |
| Job | Assign primary segment based on enrichment signals. Set initial lifecycle state to REACHED (ready for outbound). Score prospect for sequence priority. |
| Segments (HVAC Phase 1) | `owner-operator-solo`, `owner-with-small-crew`, `growing-dispatcher`, `unclassified` |
| Output event | `calllock/prospect.segmented` |
| Output schema | `{ prospect_id, primary_segment, secondary_segment, lifecycle_state, prospect_score, segment_confidence }` |
| Write ownership | Segmentation Engine (per Section 9.2) |
| Failure mode | Low confidence: assign `unclassified`, flag for manual review batch. |

#### 2.3.4 Sequence Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/prospect.segmented` |
| Input | Segmented prospect with enrichment data |
| Job | Build a multi-touch email sequence using the message router (Section 10.3) and template system (Section 10.4). Select angle, template family, proof assets, and CTA for each touch. Respect experiment assignments from the Experiment Allocator (Section 10.8). |
| Output event | `calllock/sequence.created` |
| Output schema | `{ prospect_id, sequence_id, touches: [{ touch_number, send_at, template_id, angle, proof_asset_id, cta, subject_line, body_slots }] }` |
| Write ownership | Writes to `journey_assignments` (Journey Orchestrator, per Section 9.2) |
| Sequence structure | See Section 3 (Sequence Design) |
| Failure mode | No matching template: use default angle for segment. Experiment allocator unavailable: use current best performer. |

#### 2.3.5 Sender Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/sequence.touch.due` (scheduled per touch timing) |
| Input | Assembled email from Sequence Agent output |
| Job | Run through Outbound Health Gate (Section 10.13) checks. If cleared, send via email infrastructure. Log to `touchpoint_log`. |
| Health gate checks | Suppress list, bounce and complaint thresholds, volume cap, duplicate-send window, domain reputation, lifecycle eligibility |
| Output event | `calllock/email.sent` or `calllock/email.blocked` |
| Write ownership | Appends to `touchpoint_log` |
| Failure mode | Health gate block: skip touch, log reason, alert if pattern. Send failure: retry once, then dead-letter. |
| Sending infrastructure | Smartlead or Instantly API (multiple warmed domains, rotation) |

#### 2.3.6 Reply Classifier Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/email.reply.received` (webhook from email infrastructure) |
| Input | Reply text, prospect context, sequence context |
| Job | Classify reply into actionable category. Extract structured data (objections, questions, intent signals). |
| Classification categories | `positive_interest`, `question`, `objection`, `not_now_future`, `unsubscribe`, `wrong_person`, `out_of_office`, `bounce`, `irrelevant` |
| LLM | Claude Haiku. Structured output with confidence score. |
| Output event | `calllock/reply.classified` |
| Output schema | `{ prospect_id, sequence_id, reply_category, confidence, extracted_objections[], extracted_questions[], conviction_signal, readiness_signal, raw_reply_hash }` |
| Write ownership | Appends to `touchpoint_log`. Objections feed Sales Insight Layer (Section 10.9). Conviction and readiness signals feed Section 13.1. |
| Failure mode | Low confidence classification: route to `needs_human_review` bucket. |

#### 2.3.7 Handoff and Escalation Agent

| Field | Value |
|-------|-------|
| Trigger | `calllock/reply.classified` |
| Input | Classified reply with prospect context |
| Job | Route based on classification |
| Routing rules | `positive_interest`: move to EVALUATING, create founder notification with context. `question`: auto-reply with relevant proof asset if doctrine allows, else founder review. `objection`: insert counter-proof touch into sequence if proof coverage is covered for that objection, else founder review. `not_now_future`: move to DORMANT, schedule re-engagement in 60 or 90 days. `unsubscribe`: add to suppress list immediately, confirm removal. `wrong_person`: flag, attempt to find correct contact. |
| Output events | `calllock/prospect.escalated`, `calllock/sequence.modified`, `calllock/prospect.suppressed` |
| Write ownership | Updates lifecycle state, journey assignments |
| Failure mode | Uncertain routing: founder review queue. Never auto-reply when uncertain. |

## 3. Sequence Design

### 3.1 Core sequence structure

5-touch, 14-day sequence following a pain, proof, social, urgency, break-up arc. Maps to the Journey Orchestrator's narrative structure (growth doc Section 11.2).

| Touch | Day | Purpose | Angle Strategy | Content Strategy |
|-------|-----|---------|---------------|-----------------|
| T1 | 0 | Pain recognition | Lead with prospect's specific pain signal from enrichment. If enrichment found "leave a message" language or no after-hours coverage: missed-call angle. If high review volume plus slow response signals: interruption angle. Default: missed-calls. | Short, specific, one question. No pitch. Subject line references their business by name. |
| T2 | 2 | Proof | Same angle, add evidence. | Attach or link one proof asset: calculator result, demo call snippet, or stat. CTA: "worth a look?" |
| T3 | 5 | Social proof and comparison | Shift to "others like you" framing. | Reference a similar-sized HVAC shop's outcome. Or link comparison page. CTA: "see how it compares" |
| T4 | 9 | Urgency and seasonal | Add time dimension. | Tie to seasonal demand or cost-of-waiting framing. CTA: direct booking link for intro call. |
| T5 | 14 | Break-up | Permission-based close. | "Seems like timing isn't right. Want me to check back in 60-90 days, or should I stop reaching out?" Binary choice. |

### 3.2 Timing rules

- Send windows: Tuesday through Thursday, 7:00-9:00 AM prospect local time. HVAC owners check email before crews dispatch.
- Never send: weekends, Mondays (catch-up day), Fridays (wind-down).
- Holiday suppression: skip federal holidays plus day before and after. Skip extreme weather events in prospect's region if detectable (busiest days -- they will not read email).
- Timezone: derived from prospect's business address at enrichment time.

### 3.3 Escalation logic

Escalation is triggered by prospect behavior between touches, not just at sequence end.

| Signal | Detected Via | Action | Lifecycle Transition |
|--------|-------------|--------|---------------------|
| Reply: positive interest | Reply Classifier: `positive_interest` | Pause sequence. Founder notification with full context. | REACHED to EVALUATING |
| Reply: question | Reply Classifier: `question` | If matching proof asset exists and auto-reply is doctrine-approved: send proof, resume sequence. Else: founder review queue. | Stay REACHED, flag engaged |
| Reply: objection | Reply Classifier: `objection` | Insert counter-proof touch if proof coverage is covered for that objection. Else: log to objection registry, founder review. | Stay REACHED |
| Reply: not now | Reply Classifier: `not_now_future` | End sequence. Schedule re-engagement in 60 or 90 days. | REACHED to DORMANT |
| Reply: unsubscribe | Reply Classifier: `unsubscribe` | Immediate suppress. Confirmation email. Remove from all active sequences. | REACHED to LOST (reason: opt-out) |
| Link click | Touchpoint log via tracking | Do not accelerate sequence. Boost prospect score and log conviction signal up. | Stay current state |
| Email bounce | Sender Agent webhook | Hard bounce: suppress. Soft bounce: retry next touch, suppress after 2 soft bounces. | Remove from sequence |
| No engagement after T5 | Sequence completion | Move to cold pool. Eligible for re-engagement in 6 months with a different angle. | REACHED to DORMANT |

### 3.4 Re-engagement sequences

Prospects who completed a sequence without converting or who went DORMANT via "not now" get a 2-touch re-engagement after their dormancy period.

| Touch | Day | Strategy |
|-------|-----|----------|
| R1 | 0 | New angle or new proof asset that did not exist when they were last contacted. "Things have changed since we last talked..." |
| R2 | 4 | Break-up. If no response, move to long-term cold pool (12-month cycle). |

Hard rule: a prospect receives a maximum of 2 full sequences (initial plus one re-engagement) per 12-month period. This protects sender reputation and respects the ICP.

### 3.5 Experiment allocator controls

The sequence structure (Section 3.1) is fixed. What the Experiment Allocator varies within the structure:

| Element | Varied By | Example |
|---------|-----------|---------|
| Angle per touch | Experiment arm | T1 uses missed-calls vs. after-hours vs. interruption |
| Template per touch | Experiment arm | Same angle, different copy treatment |
| Proof asset | Experiment arm plus proof coverage | Calculator vs. demo call vs. stat |
| CTA | Experiment arm | Question CTA vs. direct booking link |
| Subject line | Experiment arm | Personalized vs. pain-statement vs. curiosity |

The Experiment Allocator assigns arms at sequence creation time (per growth doc Section 10.8). The entire sequence runs as one cohesive arm. No mid-sequence variant switching.

### 3.6 Deliverability architecture

| Component | Specification |
|-----------|--------------|
| Sending domains | 3-5 secondary domains (e.g., calllockteam.com, getcalllock.com). Never send cold email from primary domain. |
| Mailboxes per domain | 2-3 warmed mailboxes each. Total: 6-15 sending accounts. |
| Warmup protocol | 14-day warmup per new mailbox before production sends. Use warmup service built into Instantly or Smartlead. |
| Daily send cap | 30-50 emails per mailbox per day. Scale by adding mailboxes, not volume per mailbox. |
| Total daily capacity | 180-750 emails per day at steady state (6-15 mailboxes times 30-50). |
| Rotation | Round-robin across mailboxes. Same prospect always gets the same sender persona for sequence continuity. |
| Bounce threshold | Pause mailbox if bounce rate exceeds 3%. Investigate before resuming. |
| Complaint threshold | Pause mailbox if spam complaint rate exceeds 0.1%. |
| SPF/DKIM/DMARC | Configured on all sending domains before first send. Non-negotiable. |

## 4. Handoff Protocol

### 4.1 Handoff triggers

A prospect enters the handoff pipeline when any of these fire:

| Trigger | Source | Priority | SLA |
|---------|--------|----------|-----|
| Reply classified `positive_interest` | Reply Classifier Agent | P1 Hot | Founder contact within 4 hours |
| Reply classified `question` plus high readiness signal | Reply Classifier Agent | P2 Warm | Founder contact within 24 hours |
| Prospect books intro call via CTA link | Cal.com webhook via `calllock/meeting.booked` | P1 Hot | Auto-confirmed, founder prepares |
| Calculator completed plus high engagement dwell | Touchpoint log | P3 Interested | Add to next founder call block |

### 4.2 Handoff packet

When the Handoff Agent escalates a prospect, it assembles a founder context packet with everything needed for a relevant first conversation:

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
    segment: string
    prospect_score: number
  enrichment:
    pain_profile: string
    urgency_likelihood: string
    key_signals: string[]  # e.g. ["no after-hours coverage", "4.2 stars with couldn't reach complaints"]
  sequence_history:
    touches_sent: number
    angle_used: string
    proof_shown: string
    engagement: string[]  # e.g. ["opened T1, T2", "clicked calculator T2", "replied T3"]
  reply_context:
    reply_text: string
    classification: string
    extracted_questions: string[]
    extracted_objections: string[]
    conviction_signal: enum(up, flat, down)
    readiness_signal: enum(up, flat, down)
  recommended_talking_points: string[]
```

### 4.3 Founder pipeline

Simple Kanban that the founder works daily:

| Stage | Meaning | Action |
|-------|---------|--------|
| New | Handoff packet received | Review packet, decide to pursue |
| Contacted | Founder has reached out | Awaiting response |
| Meeting Set | Intro call scheduled | Prepare using packet |
| Pilot Proposed | Prospect has seen pricing and offer | Follow up |
| Pilot Started | Prospect is live on CallLock | Onboard, check in at day 3, 7, 14 |
| Won | Converted to paying customer | Record outcome |
| Lost | Declined or went dark | Log reason, feeds Loss Analysis (growth doc Section 12.10) |

Lifecycle state mapping:

- New and Contacted map to EVALUATING
- Meeting Set and Pilot Proposed map to IN_PIPELINE
- Pilot Started maps to PILOT_STARTED
- Won maps to CUSTOMER
- Lost maps to LOST with structured reason

### 4.4 Feedback loop

Outcomes flow back into the swarm through Growth Memory:

| Outcome | Feeds Into | Effect |
|---------|-----------|--------|
| Won | `segment_performance`, `angle_effectiveness`, `proof_effectiveness` | Reinforces the sequence that worked |
| Lost (reason: price) | `loss_records`, `objection_registry` | Triggers pricing objection proof gap analysis |
| Lost (reason: not ready) | `loss_records` | Prospect moves to DORMANT with re-engagement at 90 days |
| Lost (reason: competitor) | `competitor_mentions`, `loss_records` | Feeds battlecard creation |
| Pilot churned | `churn_records` | Feeds conviction and readiness model. Was readiness inflated? |

## 5. The Scorecard

### 5.1 Primary metrics (weekly review)

| Metric | Formula | Target | Red Flag |
|--------|---------|--------|----------|
| LTV:CAC Ratio | LTV divided by (all-in monthly swarm cost divided by new customers) | 3:1 or higher | Below 2:1 for 3 consecutive weeks |
| CAC | Total swarm cost divided by new customers acquired | Below $800 (Core tier) | Above $1,200 |
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
| 1. Is it working? | 3 min | Level 1 | Deliverability, send volume, bounce and complaint rates. Any mailbox paused? |
| 2. What is converting? | 5 min | Level 2 | Reply rate by angle, positive reply rate by segment, escalation-to-meeting rate. Which experiment arms are winning? |
| 3. What should I do? | 5 min | Level 3 | Review handoff queue (P1s first). Check Growth Advisor recommendations. Approve or reject pending experiment proposals or asset approvals. |
| 4. What happened? | 2 min | Level 4 | Losses this week and why. New objections logged. Any churn. |

## Appendix A: Inngest Event Catalog

All events follow the calllock/ namespace convention per ADR 015.

| Event | Producer | Consumer | Payload Key Fields |
|-------|----------|----------|--------------------|
| `calllock/prospecting.batch.requested` | Cron (daily 6am) | Prospector Agent | wedge, geo_filters, batch_size |
| `calllock/prospect.sourced` | Prospector Agent | Enrichment Agent | prospect_id, business_name, email, source, batch_id |
| `calllock/prospect.enriched` | Enrichment Agent | Segmentation Agent | prospect_id, trade, pain_profile, wedge_fit_score, field_confidences |
| `calllock/prospect.segmented` | Segmentation Agent | Sequence Agent | prospect_id, primary_segment, lifecycle_state, prospect_score |
| `calllock/sequence.created` | Sequence Agent | Sender Agent (via scheduled touches) | prospect_id, sequence_id, touches[] |
| `calllock/sequence.touch.due` | Scheduler | Sender Agent | prospect_id, sequence_id, touch_number |
| `calllock/email.sent` | Sender Agent | Touchpoint log | prospect_id, sequence_id, touch_number, mailbox_id |
| `calllock/email.blocked` | Sender Agent | Alerting | prospect_id, block_reason |
| `calllock/email.reply.received` | Email infra webhook | Reply Classifier Agent | prospect_id, sequence_id, reply_text |
| `calllock/reply.classified` | Reply Classifier Agent | Handoff Agent | prospect_id, reply_category, confidence, conviction_signal, readiness_signal |
| `calllock/prospect.escalated` | Handoff Agent | Founder pipeline | prospect_id, priority, handoff_packet |
| `calllock/sequence.modified` | Handoff Agent | Sender Agent | sequence_id, modification_type, inserted_touch |
| `calllock/prospect.suppressed` | Handoff Agent | Suppress list | prospect_id, reason |
| `calllock/meeting.booked` | Cal.com webhook | Founder pipeline | prospect_id, meeting_time |

## Appendix B: Authority and Deference Map

| Topic | Authority | This Spec's Role |
|-------|-----------|-----------------|
| Growth Memory tables and write ownership | Growth system design doc Section 9 | Defers. Agents write to tables per ownership rules. |
| Experiment allocation and winner declaration | Growth system design doc Section 10.8 | Defers. Sequence Agent respects experiment assignments. |
| Segmentation engine behavior | Growth system design doc Section 10.2 | Defers. Segmentation Agent implements the engine. |
| Signal quality and learning integrity | Growth system design doc Sections 10.11, 10.12 | Defers. All events scored before influencing Growth Memory. |
| Doctrine and proof coverage | Growth system design doc Sections 13.2, 13.3 | Defers. Handoff Agent checks doctrine before auto-reply. |
| Outbound health gate | Growth system design doc Section 10.13 | Defers. Sender Agent runs through the gate. |
| Pricing model and scenarios | This document Section 1 | Authoritative. |
| Agent orchestration pipeline | This document Section 2 | Authoritative. |
| Sequence structure and timing | This document Section 3 | Authoritative. |
| Handoff protocol and founder pipeline | This document Section 4 | Authoritative. |
| LTV:CAC scorecard and hiring triggers | This document Section 5 | Authoritative. |
| Inngest event names for the swarm | This document Appendix A | Authoritative, following ADR 015 convention. |

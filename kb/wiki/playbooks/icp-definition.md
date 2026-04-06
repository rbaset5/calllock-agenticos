---
id: playbook-icp-definition
title: CallLock Ideal Customer Profile (ICP)
dossier: playbooks
tags: [icp, gtm, targeting, customer-profile]
source_refs:
  - wiki/competitors/servicetitan-ai.md
  - wiki/competitors/sameday-ai.md
  - wiki/competitors/answering-services.md
  - wiki/playbooks/positioning-dunford.md
  - wiki/playbooks/lsa-acquisition-channel.md
  - wiki/competitors/yc-trend-analysis.md
compiled_at: 2026-04-05T18:00:00Z
confidence: medium
---

# CallLock Ideal Customer Profile (ICP)

Synthesized from 13 articles of competitor research, positioning analysis, and channel mapping. Every attribute below is a hypothesis — zero contractors have validated any of it.

## The Buyer (unvalidated — discover in first 10 calls)

The buyer role is unclear and must be validated. Possibilities:

- **Owner-operator** — on job sites all day, feels the pain when checking voicemail at 9 PM
- **Office manager** — lives with the voicemail problem daily, may have more influence than assumed
- **Owner's spouse** — handles the phones in many small shops, different objections and decision criteria

In the first 10 validation calls, explicitly ask: "Who handles your phone situation — you, or someone in the office?" Use the answer to determine whether the pitch, triggers, and prospecting channel need to shift.

## The Business

| Attribute | Spec | Why this matters (sourced from KB) |
|-----------|------|-------------------------------------|
| Trade | HVAC, plumbing, or electrical | Highest-value calls ($80-$5,000+ per job). Emergency-driven = after-hours demand. Electrical has lower CPL ($30-70) but same after-hours urgency. |
| Size | 3-15 employees | Too small for a dedicated CSR. Too busy for the owner to answer every call. |
| Revenue | $500K-$3M/year | Big enough to spend $297/mo. Small enough that ServiceTitan ($245-$398/tech/mo) is too expensive or overbuilt. |
| FSM platform | NOT on ServiceTitan | ST customers get native AI voice agent — we can't compete there ([[competitors/servicetitan-ai]]). HCP/Jobber/paper are all fine. FSM platform is a NICE-TO-HAVE filter, not a gate — integration isn't shipped yet. |
| Lead source | Paid inbound ads ($1K+/mo) | LSA, Angi, Thumbtack, or other paid channels. Already spending to make the phone ring. Each missed call = wasted ad spend ([[playbooks/lsa-acquisition-channel]]). LSA is the primary discovery channel but not the only one. |
| Current call solution | Voicemail or nothing | Never paid for an answering service. The $297/mo is a new expense, not a switch. This is Segment A from [[competitors/answering-services]]. |
| After-hours volume | Gets calls evenings + weekends | This is where 100% of calls go to voicemail. Easiest entry point. |

## The Moment

The ideal time to reach this person is when they're experiencing one of these:

1. **Just checked their LSA dashboard and saw missed calls** — Google is literally telling them their responsiveness is low
2. **Lost a job to a competitor who answered first** — they know it happened, they're frustrated
3. **Seasonal surge starting** — summer (HVAC) or winter (plumbing) — call volume is about to spike and they know they can't handle it
4. **Hired (or fired) a receptionist** — either they just spent $2,500/mo on a human and want cheaper, or they just lost their phone coverage

## The Disqualifiers

Do NOT pursue contractors who:
- **Are on ServiceTitan** — ST's native AI voice agent is unbeatable on their platform ([[competitors/servicetitan-ai]])
- **Have a dedicated call center** (5+ CSRs) — too large, complex sales cycle, Sameday's territory ([[competitors/sameday-ai]])
- **Don't run any paid ads** — if they're not spending to generate calls, the "stop wasting ad spend" pitch doesn't land. Deprioritize, don't hard-exclude (they may still have organic call volume).
- **Are happy with Smith.ai at low volume** — at <50 calls/mo, Smith.ai at $95 is genuinely a better deal. Deprioritize, don't hard-exclude ([[competitors/answering-services]])

## Qualification Rubric (2-minute qualify/disqualify)

Replace the compound one-liner with a tiered scorecard a salesperson can use in real time:

| Tier | Criteria | How to observe | Time to check |
|------|----------|---------------|---------------|
| **MUST** | HVAC, plumbing, or electrical | LSA/ad listing, website | 10 sec |
| **MUST** | Goes to voicemail after hours | Call them after 6 PM | 30 sec |
| **MUST** | 2-20 employees (not solo, not a chain) | Review count, truck count, website | 30 sec |
| **STRONG** | Runs paid ads (LSA, Angi, Thumbtack) | Search results | 10 sec |
| **STRONG** | Not on ServiceTitan | Ask, or check Facebook groups / website | 1 min (on callback) |
| **NICE** | On Housecall Pro or Jobber | Only by asking | 1 min (on callback) |
| **NICE** | Buyer personally feels the missed-call pain | Only by asking | 1 min (on callback) |

**Step 1 (60 seconds, before contact):** Search LSA, check trade + size + ads = MUST gate.
**Step 2 (30 seconds):** Call after 6 PM. Voicemail = passes. Human = deprioritize.
**Step 3 (on callback, 2 questions):** "Are you on ServiceTitan?" + "Who handles your phone situation?" = STRONG + buyer identification.

**One-line summary (for internal use):** HVAC, plumbing, or electrical shop, 2-20 people, not on ServiceTitan, running paid ads, going to voicemail after hours.

## How to Find Them

1. **Google LSA results** — search "HVAC near me" in any city. Small shops with <50 reviews and 4.0-4.5 stars.
2. **Call them after 6 PM** — if voicemail answers, they're a prospect. The research IS the prospecting.
3. **Housecall Pro / Jobber Facebook groups** — they self-identify as non-ServiceTitan and discuss missed calls openly.
4. **Supply houses** (Ferguson, Winsupply, Johnstone Supply) — where contractors go weekly. A bulletin board or supply house rep referral reaches them in their natural habitat.
5. **Local PHCC / ACCA chapters** — trade association meetings where owners talk shop.

See [[playbooks/lsa-acquisition-channel]] for the full channel breakdown with cost-per-lead data.

## The Pitch (by segment)

**Segment A — voicemail (majority, best prospects):**
"You're paying Google $50-100 for every lead that calls your phone. How many go to voicemail after 5 PM? CallLock answers every one for $297/mo."

**Segment B — cheap answering service:**
"Your answering service takes a message. By the time you call back, the customer hired someone else. CallLock books the job on the first call."

**Segment C — Smith.ai / Ruby (harder to convert):**
Lead with the volume comparison table from [[competitors/answering-services]]. At 150+ calls/month, CallLock is cheaper than Smith.ai. Add vertical depth and unlimited concurrency.

## What's Still Unvalidated

Every line above is a hypothesis built from secondary research. Zero contractors have confirmed:

1. That they actually miss 20%+ of calls (our number, not theirs)
2. That $297/mo is in their "try it" budget
3. That they'd trust AI on the phone with their customers
4. That after-hours is the real pain point (vs. peak-hour overflow, vs. lunch breaks, vs. weekends)
5. That "works with Housecall Pro" matters to them
6. That the owner-operator is the buyer (vs. the office manager, vs. the owner's spouse who handles the phones)
7. That "independent" or "owner-led" is how they describe themselves
8. That Google LSA responsiveness metrics actually motivate behavior change

## Validation Plan (3 phases)

### Phase 1: Phone Audit (validates the problem exists)

**Call 50 LSA contractors between 5-8 PM in 2-3 starter markets.**

**Starter markets** (chosen for extreme seasonal demand + high LSA density):
- **Summer HVAC:** Phoenix, Houston, or Dallas
- **Winter plumbing:** Chicago or Minneapolis
- **Year-round:** Atlanta or Charlotte

**Record for each call:**
- Voicemail, human receptionist, owner, or answering service?
- How many rings before answer/voicemail?
- What does the voicemail say? (custom greeting = cares about calls; default = doesn't)

**Phase 1 success:** 30%+ go to voicemail after hours.

### Phase 2: Discovery Interviews (validates the buyer and willingness)

**For the 15-20 who answered or called back, ask:**
1. "Who handles your phone situation — you, or someone in the office?"
2. "When you miss a call, what happens?"
3. "Have you ever tried an answering service or AI phone system?"
4. "If something could answer your phone and book jobs when you're busy, what would that be worth to you?"
5. "Would you want a system that proactively finds you new customers, or is answering existing calls enough?"
6. "Are you on ServiceTitan, Housecall Pro, Jobber, or something else?"

**Phase 2 success:** Consistent buyer persona emerges (owner vs. office manager vs. spouse) AND the pain is real (not "my wife handles it, we're fine").

### Phase 3: Commitment Test (validates willingness to pay)

**Offer 5 of the most engaged prospects a free 2-week pilot.**

This is the only real validation. Stated preference on a cold call ("yeah I'd pay $300/mo") is nearly worthless. Observed behavior (they actually set up the trial, forward their after-hours calls, and use it) is proof.

**Phase 3 success:** 3+ of 5 activate the trial AND at least 1 converts to paid or explicitly asks "how do I keep this?"

**Overall ICP validation:** All three phases pass. If Phase 1 fails (contractors don't go to voicemail), the missed-call thesis is wrong. If Phase 2 fails (contractors don't care or already solved it), the pain isn't acute enough. If Phase 3 fails (they say yes but don't activate), the product or price is wrong.

## What Could Prove This ICP Wrong

1. The "not-ServiceTitan" market is smaller than we think — more small contractors have migrated to ST than assumed
2. Owner-operators don't answer sales calls from strangers — the outbound prospecting motion to reach them may be as hard as the outbound motion they'd buy
3. $297/mo is above the impulse-buy threshold for shops doing $500K — they'd try it at $99 but not $297
4. The after-hours wedge is too narrow — contractors want full 24/7 coverage or nothing, not "just evenings"
5. The real buyer is the office manager or owner's spouse, not the owner — and they have different objections and decision criteria
6. HVAC/plumbing is too narrow to start — should include electrical, roofing, landscaping to have enough volume

## See Also

- [[playbooks/positioning-dunford]] — Positioning framework this ICP is derived from
- [[playbooks/lsa-acquisition-channel]] — Where to find these customers and the unit economics of reaching them
- [[competitors/answering-services]] — Segment definitions (A/B/C) and Smith.ai competitive dynamics
- [[competitors/servicetitan-ai]] — Why ServiceTitan customers are disqualified
- [[competitors/sameday-ai]] — Why large contractors (5+ CSRs) are disqualified

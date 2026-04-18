---
id: playbook-missed-call-audit
title: 15-Minute Missed-Call Audit
dossier: playbooks
tags: [sales, audit, conversion, funnel, math-only]
source_refs:
  - wiki/positioning/positioning-dunford.md
  - wiki/product/smb-feature-set.md
derived_from: wiki/positioning/positioning-dunford.md
compiled_at: 2026-04-14T00:00:00Z
confidence: medium
status: living
version: 1
epistemic_status: |
  The formula is sound. The constants (hang-up rate, close rate) are founder estimates
  pending validation against first-party call recording corpus. See "Constants & Sourcing"
  below. Do not cite specific dollar figures from this playbook on public surfaces
  without marking them as estimates.
---

# 15-Minute Missed-Call Audit

The canonical conversion flow for CallLock prospects. A math-only, no-install, verbal audit that produces a personalized dollar figure in 15 minutes. This is the **single audit spec** the homepage CTA, cold-call close, SDR pitch, and ad landing pages all inherit from.

When we eventually graduate to an installation-based diagnostic (actual call tracking on the prospect's line before they buy), that becomes a premium/upsell audit. Don't confuse the two.

## Thesis (inherited from canon)

From [[../positioning/positioning-dunford]] §Where the Miss Problem Actually Lives:

> *Contractors measure missed calls by counting voicemails. That mental model is wrong. Voicemails only count the patient callers — the people who waited through 4–6 rings and then took another 15 seconds to leave a message. The callers who matter most — emergencies, I-need-someone-today, the high-ticket installs — don't wait. They hang up in 10–20 seconds and call the next shop on Google. The contractor never sees them. Voicemail is a patience filter, not a miss tracker.*

Every audit conversation has to deliver this insight before the math lands. The dollar figure at the end only matters if the contractor has already accepted that their current mental model undercounts misses.

## The 3 inputs

Ask for exactly three numbers. No more. If you ask for four, the contractor feels interrogated and you lose the close.

| Input | How to ask | Default if they don't know |
|---|---|---|
| **V — voicemails per day** | *"Rough guess — how many voicemails do you check in a typical morning?"* | Don't default. Ask until you get a number. |
| **T — average ticket** | *"On a typical service call, what's the job worth to you — ballpark?"* | $400 (HVAC/plumbing service call anchor) |
| **C — close rate on new customer calls** | *"When a brand-new customer calls you, how often do they book?"* | 20% floor, with a line: *"Most owners say higher — we use 20% because it's the conservative version. The real number is probably better."* |

## The formula

Let **R** = hang-up rate (fraction of callers who don't leave a voicemail when they reach one). **Default: 0.40** (founder estimate, see Constants below).

```
Total missed calls/day  = V / (1 − R)
Invisible misses/day    = Total − V
Daily lost revenue      = Total × T × C
Monthly lost revenue    = Daily × 20 working days
```

**At R = 0.40:** Total = V × 1.67. Every voicemail implies ~1.67 total missed calls and ~0.67 additional invisible misses the contractor never saw.

## Worked example — the 3-voicemail contractor

> *"Say you get 3 voicemails a day. Let's do the math out loud.*
>
> *Industry data says somewhere between 30% and 50% of people who reach voicemail don't leave a message at all — especially on urgent calls. Let's use 40% — the middle. That means your 3 voicemails represent about 5 actual missed calls a day — 3 you see, 2 you don't.*
>
> *At a $400 average ticket and a conservative 20% close rate on new customers — and I think yours is higher — that's $400 a day, every day. Over a 20-day working month, that's about $8,000 walking to voicemail.*
>
> *And that's using the floor number on close rate. At your real close rate, probably 30–40%, you're looking at $12K to $16K/month.*
>
> *Does $8K/month match your gut?"*

**Numbers for this example:**
- V = 3, T = $400, C = 0.20, R = 0.40
- Total misses/day = 3 / 0.60 = **5**
- Invisible misses/day = **2**
- Daily lost revenue = 5 × $400 × 0.20 = **$400**
- Monthly (20 days) = **$8,000**
- At C = 0.30: **$12,000**
- At C = 0.40: **$16,000**

## Sensitivity — how the range moves

At V = 3 voicemails/day, $400 ticket, 20-day month:

| Hang-up rate R | Close rate C | Monthly lost |
|---|---|---|
| 30% | 20% | ~$6.9K |
| 30% | 30% | ~$10.3K |
| 30% | 40% | ~$13.7K |
| 40% | 20% | ~$8.0K |
| 40% | 30% | ~$12.0K |
| 40% | 40% | ~$16.0K |
| 50% | 20% | ~$9.6K |
| 50% | 30% | ~$14.4K |
| 50% | 40% | ~$19.2K |

For cold audits, use **R = 0.40, C = 0.20** as the default ("the conservative version"). This gives you a floor number you can anchor against without overclaiming. The contractor will almost always push back with *"my close rate is higher than 20%"* — when they do, accept it and rerun the math on the call. That's the close.

## The verbal close

After you land the number, say exactly this:

> *"That's the math on the conservative side. If you want, I can set up a 15-minute call this week where we plug in your real close rate, look at what you're paying for leads right now, and I'll show you what CallLock would have caught from that same voicemail volume. No deck, no demo, just the math. Thursday at 10 or Friday at 2?"*

Two options on the close, never "when works for you." Same close rule as [[cold-call-hvac]] §5.

## Constants & Sourcing

**This is the epistemic-status section. Read it before citing any number from this playbook publicly.**

### R — hang-up rate (30–50%)

- **Status:** founder estimate, corroborated by anecdotal observation of call recordings
- **Why 30–50%:** emergency/urgent callers tend to hang up within 10–20 seconds rather than wait through voicemail greetings and leave a message. Informed by review of CallLock's own call corpus.
- **How to verify:** pull N inbound calls where the owner didn't answer. Count (a) calls where caller hung up before the voicemail tone, (b) calls where caller left a voicemail. `R = a / (a + b)`. An hour of work against the existing corpus produces a real number.
- **TODO (v2):** replace R with a measured value from the corpus. Tag source as "CallLock call recording corpus, N calls, as of [date]."
- **Never cite on public surfaces without** framing as *"industry call-tracking estimates"* or *"our internal observation of call recordings."* Do not name ServiceTitan, CallRail, or any third-party dataset in public copy.

### C — new-customer close rate (20% floor, contractor's own if they'll give it)

- **Status:** floor anchor, not an assertion about the ICP
- **Why 20%:** deliberately conservative. Most owner-operators will report 30–50% for new customer calls, so starting at 20% lets the conversation end with *"the real number is almost certainly higher."*
- **How to use:** always prefer the contractor's own number. Only use 20% as a fallback when they can't or won't give one. Never use 20% silently — name it as the floor so the upside is visible.

### T — average ticket ($400 default)

- **Status:** ICP anchor, from [[../positioning/icp]] hard filters (*"$300+ service OR $3K+ install"*)
- **Why $400:** midpoint of the service-call range for a typical HVAC/plumbing contractor. Safer than $300 (too low, contractor feels insulted) or $500 (too high, contractor argues).
- **How to use:** always prefer the contractor's own number. $400 is only for when they refuse to commit to a figure or say *"depends."*

### Working days per month (20)

- **Status:** convention, not estimate
- **Why 20:** 5-day work week × 4 weeks = 20. Contractors work 6 days/week in practice but the math is cleaner at 20 and it slightly underclaims, which is the right direction for a floor estimate.
- **If pressed:** *"That's only counting weekdays. Your real number is 15–20% higher because you work Saturdays."*

## Why math-only beats installation-based for launch

| Dimension | Math-only (this playbook) | Installation-based |
|---|---|---|
| Time to first number | 15 minutes | 1–2 weeks |
| Friction | One phone call | Carrier config + monitoring period |
| Commitment required | None | Prospect agrees to pre-install |
| Accuracy | Anchored on founder estimates | Exact |
| Converts cold prospects | Yes | Only warm prospects will agree |
| Sales leverage | Low-to-medium | Very high (shows real calls walking away) |
| When to use | Cold + mid-funnel (default) | Deal stuck on "is this really my number?" |

**For launch:** use math-only exclusively. Graduate specific high-value stalled deals to installation-based. Do not offer installation-based on the homepage CTA — it will crater conversion.

## What this unlocks downstream

- **Homepage Feature Block 1** can anchor on the voicemail count as the conversion input instead of generic call volume
- **Cold-call §2 Quantifier** (see [[cold-call-hvac]]) can be simplified to the same 3 inputs
- **Ad landing pages** can lead with the voicemail-filter insight and the 15-minute audit offer
- **Email sequences** for cold prospects can frame the opener around *"3 voicemails a day = 5 misses a day"* math
- **SDR script** (future) uses this as the conversion close verbatim

Every marketing and sales surface inherits from this one file. When any constant changes here, grep every downstream surface for the old number and update.

## Changelog

- **v1** (2026-04-14) — Initial playbook. Formula and verbal close locked. Constants R=0.40, C=0.20, T=$400 are founder estimates pending first-party corpus validation.

## Related

- [[../positioning/positioning-dunford]] — the voicemail-filter thesis this playbook operationalizes
- [[cold-call-hvac]] — sister playbook; the audit lands at the end of §2 Quantifier in the cold-call flow
- [[../product/smb-feature-set]] — the product delivering against the audit's promise
- [[../marketing/homepage-v3]] — the conversion surface this playbook feeds

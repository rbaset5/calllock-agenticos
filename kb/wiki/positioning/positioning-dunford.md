---
id: positioning-dunford
title: Positioning — Dunford Framework (SMB Home Services)
dossier: positioning
tags: [positioning, dunford, category, icp, messaging, smb]
source_refs:
  - raw/positioning-dunford-draft.md
compiled_at: 2026-04-14T00:00:00Z
confidence: high
status: living
---

# Positioning — Dunford Framework (SMB Home Services)

Positioning for CallLock built on April Dunford's five-component framework, targeted at the SMB home services ICP.

## 1. Competitive Alternatives

*What would they do if you didn't exist?*

Not other AI receptionists. The real alternatives in the SMB owner's head:

- **The owner's own cell phone** — current default; answer between jobs, miss the rest
- **Spouse / family member answering** — free but unreliable, causes household friction
- **Voicemail + callback** — the status quo; lose 50%+ of callers to the next Google result
- **Human answering service** — Ruby, AnswerConnect, PATLive at $200–$500/month; hated for script-reading and missed context
- **Missed-call text-back (MCTB)** — Podium, GoHighLevel, Thryv auto-reply "Sorry we missed you"; now default in most SMB marketing suites. Shares voicemail's patience-filter failure mode (see §3.5) — catches the tune-up caller, loses the emergency. Not a separate competitive front; same category as voicemail.
- **Hiring a part-time receptionist** — $2K–$3K/month, HR overhead, still not 24/7

**Why it matters:** positioning has to beat *voicemail* and *the owner's own thumb*, not Bravi or Sameday. Those are enterprise fights the SMB buyer has never heard of.

### The competitive wedge

The advantage isn't *"AI beats human."* It's:

> **live pickup when you can't + real calendar booking + HVAC-specific intelligence + price point — vs. an answering service that hands over a message pad.**

Each clause targets a specific failure mode of the real alternatives above:

- **Live pickup when you can't** beats voicemail — because we're only in the picture when voicemail would have been.
- **Real calendar booking** beats the human answering service's "we took a message" handoff — the booking *is* the conversion.
- **HVAC-specific intelligence** beats Ruby/PATLive script-readers who don't know a condenser from a compressor.
- **Price point** beats the $200–$500/mo answering service and the $2K–$3K/mo receptionist — and it's predictable, unlike per-minute bills.

Frame every competitive conversation through these four, not through "our AI is smarter than theirs."

## 2. Unique Attributes

*What do you have that alternatives don't?*

- Picks up the calls you can't — 24/7, right when your voicemail would have, including calls that land while the owner is under a sink
- Books directly to the owner's calendar, not a message pad
- Texts the owner a summary in 30 seconds — every call lands visibly on their phone
- Spam and sales-call filtering built in
- Live in 72 hours, done-for-you setup — owner configures nothing
- Published monthly subscription pricing — not a per-minute answering service bill that spikes in busy months
- Built specifically for home services trades — knows "R-22 recharge" or "main line snake" without training

## 3. Value

*What do those attributes enable for the customer?*

Attributes translate to outcomes the owner actually cares about:

- **Capture revenue currently walking to competitors** — including the calls the owner doesn't even know about (see §3.5 below)
- **Stop dropping the phone mid-job** — no more choosing between finishing the repair and answering the call
- **Get the family off the phones** — spouse stops being unpaid dispatch
- **Predictable monthly cost** — no answering service surprise bills in busy months
- **Sleep through the 2am emergency calls** — and still capture them

The three that do the most selling work: *capture missed call revenue*, *stop dropping the phone mid-job*, *get your spouse off dispatch*. The third is underrated — it's an emotional win the owner feels at dinner, not just on the P&L.

## 3.5. Where the Miss Problem Actually Lives

*The insight that carries the whole sales conversation.*

Contractors measure missed calls by counting voicemails. That mental model is broken.

The typical owner will tell you *"I get about 3 voicemails a day — that's what I'm missing."* They treat the voicemail count as their miss tracker. It isn't. **Voicemail is a patience filter, not a miss tracker.**

Only patient callers leave voicemails — the ones who wait through 4–6 rings and then take another 15 seconds to leave a message. The callers who matter most — emergencies, I-need-someone-today jobs, high-ticket installs — **don't wait**. They hang up in 10–20 seconds and call the next shop on Google. The contractor never sees them.

Which means:

1. **The voicemail count systematically understates total misses**, because impatient callers don't appear in it at all.
2. **The missing callers are disproportionately the highest-value ones.** Impatience correlates with urgency, and urgency correlates with ticket size (active leak vs. routine tune-up; no heat in January vs. maintenance check).
3. **The contractor has no way to surface these invisible misses without intervention.** There is no log, no inbox, no reminder. They exist only in the carrier's call record, which the owner has never looked at.

This is the insight the audit weaponizes. See [[../playbooks/missed-call-audit]] for the 15-minute conversion math built on this thesis.

### Constants used in the audit math

- **Hang-up rate (fraction who don't leave voicemail):** 30–50%. *Founder estimate + first-party observation of CallLock's own call recording corpus. Not yet verified against a formal sample — see `wiki/playbooks/missed-call-audit.md` §Constants & Sourcing. TODO: pull real R from corpus analysis.*
- **Business-hours miss rate:** 5–10% is a plausible floor for solo owner-operators in the ICP, informed by industry call-tracking data for trade businesses. Real number for the ICP (1–5 trucks, owner-answered, no front desk) is likely at the **upper end** of that range or higher — solo dispatch has the worst conditions for pickup. *Founder estimate.*
- **New-customer close rate floor:** 20%. *Deliberately conservative anchor — most owner-operators report 30–50%. Use as floor, not as assertion.*

### Do not use on public surfaces

- Do not name specific industry data vendors (ServiceTitan, CallRail, etc.) in marketing copy. Keep vendor-specific references to internal canon only.
- Do not assert miss-rate percentages as facts. Frame as *"industry call-tracking estimates"*, *"our internal observation of call recordings"*, or qualitative language (*"some percentage you can't see without an audit"*).
- The voicemail-filter insight itself is safe to use publicly — it's a structural claim about how people use voicemail, not a statistic that requires citation.

## 4. Best-Fit Customer

*Who cares most about the value?*

US home services contractors — HVAC, plumbing, electrical, drain, garage door, water treatment — with:

- **1–5 trucks** and **$300K–$2M revenue**
- **Owner or spouse currently answering the phone between jobs**
- **10+ inbound calls/week**
- **$300+ service tickets or $3K+ install tickets**
- **$500+/month on Google LSAs or paid search**
- **Not locked into ServiceTitan**

The two filters that carry the positioning: *owner is currently the receptionist* (pain) + *already buying leads* (they know what a lead costs).

## 5. Market Category

*What context makes the value obvious?*

The most important decision in the whole framework, and where most AI receptionist companies fumble. Three options:

- **"AI receptionist"** — accurate but crowded. Competing on a features checklist against Sameday, Drillbit, Bravi, Rosie, Goodcall, and 30 others. Loses on price.
- **"Virtual answering service"** — places you next to Ruby and PATLive. Buyers understand it immediately but you get benchmarked against $150/month human services. Loses on anchor pricing.
- **"Missed-call revenue recovery for contractors"** — frames the product as a revenue tool, not an operations tool. The owner isn't buying a receptionist; they're buying back the leads currently going to voicemail.

**Recommended category: "Missed-call revenue recovery for home services contractors."**

This frame does three things at once:
1. Sidesteps the crowded AI receptionist comparison
2. Anchors price against *lost revenue* (where any number under $1K/month is trivially justified) instead of against a $150/month human service
3. Signals vertical specialization — which matters to a contractor burned by generic SaaS that doesn't understand their trade

## The Dunford One-Liner

> *For home services contractors with 1–5 trucks whose owners are answering the phone between jobs, CallLock is a missed-call revenue recovery system that catches every call you can't — 24/7, booked straight to your calendar, texted to you in 30 seconds — so the calls currently going to voicemail (including the ones you never even see) stop walking to your competitors.*

## Cold-Call Compressed Version

> *"We help 1–5 truck HVAC shops capture the calls they're missing while on the job — every missed call answered live, booked to your calendar, and texted to you in 30 seconds. Most guys we work with were losing one to two jobs a week to voicemail before we turned it on."*

## Operational Implications

Once you commit to this positioning:

- Website hero copy leads with **"missed-call revenue,"** not "AI receptionist"
- Pricing page shows ROI math *as a range tied to call volume*, not a single number:
  - **Floor ICP shop** (10 calls/wk × 20% miss × $400 ticket × 4 wks) → **~$3K/month walking away**
  - **Median ICP shop** (25 calls/wk × 20% miss × $400 × 4) → **~$8K/month**
  - **Top-of-ICP shop** (75 calls/wk × 20% miss × $400 × 4) → **~$12K/month**
  - Headline phrasing: *"Most shops we audit are losing $3K–$12K/month to voicemail, depending on their call volume."*
  - The old single-number *"$12K/month"* line is top-of-ICP only and overclaims for the median — do not use it without the range context.
- Cold call opener asks about *missed calls* and *jobs lost to voicemail*, not about "AI" or "automation"
- Case studies lead with dollar amounts recovered, not call counts handled
- Stop competing with Sameday on features; start competing with *voicemail* on outcomes — a fight you win by default

## Key Insight

The positioning choice doing the most work: **category**. Pick "missed-call revenue recovery" and the rest of the messaging writes itself. Pick "AI receptionist" and you're in a knife fight against 30 better-funded competitors on feature parity.

## See Also

- [[playbooks/cold-call-hvac]] — Operationalizes this positioning into a dial-ready script
- [[competitors/answering-services]] — Anchor-pricing context for Ruby/Smith.ai/PATLive
- [[competitors/sameday-ai]] — The "AI receptionist" feature-parity fight this positioning avoids

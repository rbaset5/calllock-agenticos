# Product Marketing Context

*Last updated: 2026-04-14*
*Sources: `kb/wiki/positioning/icp.md`, `kb/wiki/positioning/positioning-dunford.md`, `kb/wiki/product/smb-feature-set.md`*

## Product Overview
**One-liner:** For home services contractors with 1–5 trucks whose owners are answering the phone between jobs, CallLock is a missed-call revenue recovery system that catches every call you can't — 24/7, booked straight to your calendar, texted to you in 30 seconds — so the 20–40% of leads currently going to voicemail stop walking to your competitors.

**What it does:** When the owner's cell would have rolled to voicemail, the call auto-forwards to CallLock — a voice AI trained on the contractor's trade that answers live, books the job straight to their calendar, and texts the owner a plain-English summary within 30 seconds. Filters spam/sales calls, triages emergency vs. routine, and goes live in under 72 hours with done-for-you setup. The owner keeps answering the calls they want; CallLock only touches the ones that would otherwise be missed.

**Product category:** Missed-call revenue recovery for home services contractors. (Explicitly *not* "AI receptionist" — that frame loses a feature knife-fight against 30 competitors. Explicitly *not* "virtual answering service" — that anchors price against $150/mo Ruby/PATLive.)

**Product type:** Vertical B2B SaaS (voice AI + booking) with white-glove onboarding.

**Business model:** Published monthly subscription. Predictable flat price — deliberately *not* per-minute, so busy months don't spike the bill the way answering services do. Positioned below "one missed install" in cost.

## Target Audience
**Target companies:** US-based home services contractors in HVAC, plumbing, electrical, garage door, drain, and water treatment. 1–5 trucks, $300K–$2M annual revenue, 10+ inbound calls/week, $300+ service ticket or $3K+ install ticket, currently missing 20%+ of calls (after-hours, on-job, lunch). Running on QuickBooks, Jobber, Housecall Pro, or no system at all. **Not** on ServiceTitan (locked into their native AI Voice).

**Decision-makers:** Owner-operator. Single buyer. Not a GM, not an office manager — if the owner isn't the buyer, it's a different sales motion and usually a disqualifier.

**Primary use case:** Stop losing jobs to voicemail while the owner is under a sink, on a ladder, or asleep. Every inbound lead gets answered, qualified, and booked without the owner touching the phone.

**Jobs to be done:**
- Capture the 20–40% of inbound calls currently going to voicemail and walking to the next Google result
- Get the owner (and the owner's spouse) off unpaid dispatch duty
- Turn after-hours and on-the-job calls into booked jobs, not callbacks

**Use cases:**
- Owner is mid-repair and the phone rings → AI answers, books, texts summary
- 2am emergency water leak → AI triages as emergency, phone-alerts owner immediately
- Lunch / drive time / family dinner → AI handles it, owner gets an SMS instead of a voicemail
- Spam/robocall/SEO pitch → AI filters it out, never touches owner's SMS feed

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---|---|---|---|
| **Owner-operator (user + champion + decision maker + financial buyer)** | Missed revenue, family/spouse relief, predictable bills, trust that the AI won't screw up a customer | Currently the receptionist between jobs; spouse is unpaid dispatch; bleeding leads to faster competitors; burned by generic SaaS | Every call answered and booked, spouse off the phones, flat monthly bill, live in 72 hours, audit every call yourself |
| **Owner's spouse (secondary user, emotional stakeholder)** | Not being dispatch anymore | Answering calls they don't want to, household friction | Hand the phones off without hiring anyone |

*B2B but effectively single-stakeholder — the owner is every role on the org chart.*

## Problems & Pain Points
**Core problem:** The owner is the receptionist. Calls come in while they're on a job, at lunch, asleep, or at dinner. 20–40% go to voicemail and the caller immediately dials the next contractor on Google. Every missed call is a missed install, and the owner can feel it but can't stop it without hiring someone.

**Why alternatives fall short:**
- **Voicemail + callback:** loses 50%+ of callers to the next Google result before the owner ever hears the message
- **Owner's own cell phone:** answers between jobs, misses the rest, drops the phone mid-repair
- **Spouse / family answering:** free but unreliable, causes household friction, not 24/7
- **Human answering service (Ruby, AnswerConnect, PATLive, $200–$500/mo):** reads from a script, doesn't know the trade, hands over a message pad instead of a booking, per-minute bills spike in busy months
- **Part-time receptionist ($2K–$3K/mo):** HR overhead, not 24/7, expensive, still drops after-hours calls

**What it costs them:** At a $400 average ticket and 20% miss rate, 15 missed calls/week = ~$12K/month of revenue walking to competitors. For contractors already spending $500+/month on Google LSAs, every missed inbound is a paid lead burning.

**Emotional tension:** Choosing between finishing the repair and answering the call. Spouse resentment at being unpaid dispatch. Knowing competitors are out-responding them on speed-to-lead. Waking up at 2am for emergency calls. The constant, grinding awareness that revenue is walking out the door and they can't do anything about it without hiring.

## Competitive Landscape
**Direct (same solution, same problem):** Other AI receptionists — Sameday, Drillbit, Bravi, Rosie, Goodcall. Falls short because most target contractors with front-office staff (wrong ICP), lead with "AI" instead of revenue, and compete on feature checklists the SMB owner doesn't read.

**Direct (incumbent lock-in):** ServiceTitan AI Voice — strong inside the ServiceTitan base, but our ICP explicitly excludes ServiceTitan shops. We win by only selling to the 1–5 truck shops on QuickBooks/Jobber/Housecall Pro who will never buy ServiceTitan.

**Secondary (different solution, same problem):** Human answering services — Ruby, Smith.ai, AnswerConnect, PATLive. Fall short on script-reading, trade ignorance ("don't know a condenser from a compressor"), message-pad handoff instead of real bookings, and per-minute bills that spike in busy months.

**Indirect (status quo):** Voicemail + the owner's own thumb. This is the real competitor. Positioning has to beat *voicemail*, not Bravi. Falls short because callers don't leave messages — they hang up and dial the next contractor.

**Indirect (hire a human):** Part-time receptionist at $2K–$3K/mo. Falls short on cost, coverage (not 24/7), and HR overhead.

## Differentiation
**Key differentiators:**
- Picks up the calls you can't — 24/7, right when your voicemail would have, including calls that land while the owner is under a sink
- Real calendar booking (Google Calendar + iCal), not a message pad handoff
- 30-second SMS to owner with caller name, problem, urgency, and booked slot
- Spam/sales/robocall filtering built in
- Live in 72 hours, done-for-you setup — owner never touches a config screen
- Flat monthly subscription, not per-minute billing
- Trade-specific intelligence — knows "R-22 recharge" and "main line snake" without training
- "Missed call rescue" auto-forward when owner's cell goes to voicemail mid-job — built for the exact SMB pain
- Emergency vs. routine triage with phone alerts for real emergencies
- Service-area enforcement so the AI never books a job 90 minutes out of coverage
- Live call transcripts + recordings so the owner can audit every interaction

**How we do it differently:** We don't sell "AI receptionist." We sell *missed-call revenue recovery*. Every feature either makes the one-sentence offer literally true, credible for a contractor, or trustworthy on first watch. We don't build deep CRM, outbound campaigns, workflow builders, or web chat — those distract from the promise.

**Why that's better:** The owner isn't buying a receptionist — they're buying back leads that are currently going to voicemail. At a $400 ticket and 20% miss rate, any price under $1K/month is trivially justified against recovered revenue. Answering services anchor at $150/mo and lose on value math; we anchor against *lost revenue* and win on it.

**Why customers choose us:**
- Live pickup when you can't beats voicemail — we only enter the picture when voicemail would have
- Real booking beats the answering service message pad — the booking *is* the conversion
- Trade-specific language beats generic script-readers
- Flat price + 72-hour setup beats hiring anyone

## Objections
| Objection | Response |
|---|---|
| "What if the AI screws up a customer?" | You can pull up any call, read the transcript, hear the audio — every call is auditable. Most owners stop listening after the first week. |
| "I already answer my own calls." | Between jobs you do. After-hours, at lunch, and during a repair you don't — that's where the 20–40% goes. We only have to catch *those* to pay for ourselves. |
| "I tried Ruby / an answering service and hated it." | Answering services hand you a message pad. We hand you a booked appointment on your calendar. Different product. Same price or less. |
| "How much is it?" | Less than one missed install. At your ticket size, one recovered job a month covers it. |
| "I'm not technical — I don't want to configure anything." | You don't. We build your AI in under 72 hours — your pricing, your service area, your hours, your trade. You never touch a config screen. |

**Anti-persona:** Shops with 6+ trucks, $2M+ revenue, in-house dispatch, ServiceTitan users, pure new-construction or commercial-only (no inbound residential), shops with an answering service they're already happy with, and non-owner buyers (GMs, office managers) — different sales motion entirely.

## Switching Dynamics
**Push (what drives them away from current):** Losing visible revenue to voicemail. Spouse complaining about being on the phones. Competitors out-responding them on speed-to-lead. Paying $500+/month for Google LSAs and watching the leads go to voicemail anyway. Realizing they've grown past the owner-as-receptionist stage.

**Pull (what attracts them to us):** "Missed-call revenue recovery" framing — they immediately do the math. Flat monthly price. 72-hour setup with no config work. Live transcripts they can audit. The "missed call rescue" feature that auto-forwards their cell.

**Habit (what keeps them stuck):** Answering the phone themselves is free and familiar. The spouse is already doing it. "I'll hire someone eventually." Fear that any change to the phone line will cost them a customer.

**Anxiety (what worries them about switching):** "What if the AI sounds robotic and customers hate it?" "What if it screws up a booking?" "What if it misses a real emergency?" "What if setup is a nightmare and I lose calls during the cutover?"

Counters baked into the product: audit every call via transcripts + recordings, emergency triage with phone alerts, done-for-you setup in 72 hours so the owner never touches configuration.

## Customer Language
**How they describe the problem:** (TODO — capture verbatim from sales calls)
- "I'm missing calls"
- "I'm losing jobs to voicemail"
- "My wife is answering the phones and she's sick of it"
- "I can't be on the roof and on the phone"

**How they describe us:** (TODO — capture verbatim once live customers exist)

**Words to use:**
- "missed-call revenue"
- "jobs lost to voicemail"
- "booked straight to your calendar"
- "texted to you in 30 seconds"
- "live in 72 hours"
- "flat monthly price"
- "get your spouse off the phones"
- "catches every call you can't"
- "picks up when you can't"
- "when your voicemail would have"
- "auto-forwards when your cell doesn't pick up"

**Words to avoid:**
- "AI receptionist" (crowded category, feature knife-fight)
- "virtual answering service" (anchors price against $150/mo Ruby)
- "automation" (contractor doesn't care)
- "platform" / "workflow" / "dashboard" (CallLock App naming: never "dashboard")
- "Squad" / "multi-agent architecture" (over-engineered for a 2-truck shop)
- Per-minute pricing language
- "answers every call" / "every inbound call" (implies replacement — CallLock only catches missed calls, it doesn't intercept the live ones)
- "instant response" / "under a few rings" (false on conditional forward — CallLock picks up *after* the owner's full ring cycle, not before)
- "auto-callback" (wrong mechanic — it's auto-forward, carrier-level conditional forwarding, not a callback)

**Glossary:**
| Term | Meaning |
|---|---|
| Missed-call revenue recovery | The category CallLock competes in — framing the product as a revenue tool, not an operations tool |
| The Core 5 | The must-have feature bundle: 24/7 answer, calendar booking, 30-sec SMS summary, spam filter, 72-hour setup |
| Missed call rescue | Auto-forward from owner's cell to the AI when owner's mobile goes to voicemail mid-job |
| Owner-operator | The single buyer persona — not a GM, not an office manager |
| Ticket | Service-call revenue ($300+) or install revenue ($3K+) |
| ICP two filters | (1) Owner is currently the receptionist (2) Already buying leads |

## Brand Voice
**Tone:** Direct, no-BS, contractor-to-contractor. Never corporate SaaS-speak. Talks in dollars and jobs, not features and workflows.

**Style:** Conversational, concrete, numeric. Leads with revenue math. Uses trade-specific vocabulary (condenser, snake, LSA) without explaining it — the reader is a contractor and already knows.

**Personality:** Blunt. Practical. Numerate. Respectful of the trade. Slightly impatient with fluff.

## Proof Points
**Metrics:** (TODO — fill once live)
- Default ROI math used in copy: *"At a $400 average ticket and 20% miss rate, 15 missed calls/week = $12K/month walking away."*
- Target outcome in cold-call opener: *"Most guys we work with were losing one to two jobs a week to voicemail before we turned it on."*

**Customers:** (TODO — logos, names, trades once cleared for use)

**Testimonials:** (TODO — capture verbatim from live customers)

**Value themes:**
| Theme | Proof |
|---|---|
| Capture missed-call revenue | ROI math on ticket size × miss rate |
| Get the spouse off the phones | Emotional win the owner feels at dinner, not just on the P&L |
| Stop dropping the phone mid-job | Missed-call rescue + 24/7 answer |
| Predictable monthly cost | Flat subscription vs. per-minute answering service |
| Sleep through the 2am emergency | Emergency triage + phone alerts |
| Trade-specific intelligence | Knows "R-22 recharge" or "main line snake" without training |
| Audit every call | Live transcripts + recordings |

## Goals
**Business goal:** (TODO — current MRR / logo target for SMB GTM model — see `decisions/product/DEC-2026-04-14-smb-gtm-model.md`)

**Conversion action:** Booked demo / discovery call with the owner-operator, framed as a missed-call revenue audit ("let me show you what you're losing"), not a product demo.

**Current metrics:** (TODO — fill from current pipeline data)

---

## Notes & Open Items

- **Confirmed from KB:** product overview, ICP, personas, competitive landscape, differentiation, objections, switching dynamics, brand voice, value themes — all three source files are in tight agreement.
- **TODO to fill in manually:** verbatim customer language (sections 9, 11), proof metrics and customer logos (section 11), current pipeline metrics and business goals (section 12).
- **Load-bearing positioning decision:** category = "missed-call revenue recovery," *not* "AI receptionist." If any downstream copy drifts back to "AI receptionist," it's wrong — flag and fix.
- **Related canon:** `kb/wiki/playbooks/cold-call-hvac.md`, `kb/wiki/competitors/bravi.md`, `decisions/product/DEC-2026-04-14-smb-gtm-model.md`.

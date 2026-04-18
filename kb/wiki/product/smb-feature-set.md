---
id: smb-feature-set
title: Product — SMB Feature Set & Offering
dossier: product
tags: [product, offering, features, smb, icp, pitch]
source_refs:
  - user-provided canon, 2026-04-14
compiled_at: 2026-04-14T00:00:00Z
confidence: high
status: living
---

# Product — SMB Feature Set & Offering

The feature set built specifically for the SMB ICP ([[../../../decisions/product/DEC-2026-04-14-smb-gtm-model]], [[positioning/positioning-dunford]]), ranked by what actually closes the deal vs. what's nice-to-have.

## The one-sentence offer

> **"We catch every call you miss — 24/7 — book the job straight to your calendar, text you the details in 30 seconds, filter out spam, and get you live in 72 hours, for less than what one missed install costs you."**

Every feature below either makes that sentence **true** or makes it **believable**. Anything that doesn't, cut.

---

## The Core 5 — must-have, no deal without them

1. **24/7 live pickup on missed calls.** Not "press 1 for service." When your cell would have rolled to voicemail — after-hours, lunch, on-the-job, overflow — CallLock picks up with real-time voice and books the job. This is the entire reason they're buying.
2. **Appointment booking directly to their calendar.** Google Calendar + iCal at minimum. The AI confirms address, problem type, and slot — not "we'll call you back." The booking is the conversion.
3. **Instant SMS to owner with call summary + caller info.** Caller name, number, problem, urgency, booked slot (or reason not booked), in plain English, within 30 seconds of call end. This is what turns "I trust the AI" into reality — the owner sees every call land on their phone.
4. **Spam / sales call filtering.** SMB owners get hammered by SEO spam, insurance pitches, and robocalls. The AI screens these out and doesn't waste their SMS feed with them.
5. **Done-for-you setup in <72 hours.** White-glove onboarding: we build the AI's knowledge of their business, their pricing logic, their service area, their hours. They don't touch a config screen. This is a feature, not a service — sell it as such.

## The Next 3 — strong differentiators that justify price

6. **Service area + dispatch logic.** AI checks zip code against their coverage area before booking. Won't book a job 90 minutes away unless owner allows it. Prevents the #1 "the AI booked me garbage" complaint.
7. **Emergency vs. routine triage.** "Water actively leaking" vs. "drain is slow" route differently — emergency calls trigger an immediate phone alert to owner, routine bookings just SMS. Maps to how contractors actually think about their day.
8. **Estimate ranges, not exact quotes.** "Service call starts at $89, repair typically $200–$600 depending on the part." Sets expectations without committing the contractor to a number. This is the SMB-safe version of [[competitors/bravi]]'s quoting feature — same outcome, far less risk.

## The 2 that win the demo

9. **Live call transcripts + recordings in a simple interface.** Owner can pull up any call, read what was said, hear the audio. Builds trust fast — the #1 SMB objection is "what if the AI screws up?" Letting them audit every call kills that objection.
10. **"Missed call rescue" — auto-forward on missed mobile calls.** When the owner's cell goes to voicemail mid-job, the call auto-forwards to the AI. This is the killer feature for the exact SMB pain — owner answering between jobs and dropping calls. [[competitors/bravi]] doesn't lead with this because their ICP has a front office; we should lead with it because our ICP doesn't.

---

## What to explicitly NOT include (yet)

- **Deep CRM.** They don't have one. Don't try to be HubSpot. SMS + calendar is the CRM at this scale.
- **Outbound campaigns.** Different muscle, different sale, distracts from the core promise.
- **Multi-agent "Squad" architectures.** Over-engineering for a 2-truck shop.
- **Workflow builders.** They will never use it. Configure it for them in setup.
- **Web chat widgets.** Their website gets 50 visits a month. Wrong channel.
- **Manufacturer / B2B2C features.** Not their world. (See [[competitors/bravi]] for the opposite bet.)

---

## Why this order

The pitch order compresses the ten features into one sentence. Everything above is in service of that sentence:

- Core 5 → makes the sentence **literally true** (we do answer, book, SMS, filter, and onboard fast).
- Next 3 → makes the sentence **credible for a contractor** (geography, urgency, money).
- Demo 2 → makes the sentence **trustworthy on first watch** (they can audit it; it catches the calls they were most afraid of losing).
- Non-goals → protects the sentence from feature creep that dilutes the promise.

## Related

- [[positioning/positioning-dunford]] — Dunford five-component positioning; the category frame this offer lives inside.
- [[playbooks/cold-call-hvac]] — how to walk through this offer on a cold call.
- [[competitors/bravi]] — closest feature-adjacent competitor; different ICP (installers w/ front office).
- [[competitors/sameday-ai]] — inbound-only incumbent in the trades.
- [[competitors/servicetitan-ai]] — incumbent threat; native to ServiceTitan CRM.

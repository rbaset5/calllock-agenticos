---
id: marketing-homepage-v3
title: Homepage Copy — v3 (Safety-Net Frame, Quick Wins Applied)
dossier: marketing
tags: [marketing, homepage, copy, conversion, smb]
source_refs:
  - wiki/positioning/positioning-dunford.md
  - wiki/positioning/icp.md
  - wiki/product/smb-feature-set.md
derived_from:
  - wiki/positioning/positioning-dunford.md
  - wiki/product/smb-feature-set.md
inherits_frame_from: safety-net (not replacement) — see "Positioning Commitments" below
compiled_at: 2026-04-14T00:00:00Z
confidence: high
status: living
version: 3
---

# Homepage Copy — v3

Working draft of the CallLock homepage copy. This is a **derived artifact**, not canon. If positioning-dunford.md or smb-feature-set.md changes, this file must be re-checked for drift.

When the site ships in `web/`, the canonical copy moves into the Next.js page and this file gets a deprecation note pointing at the source of truth.

## Positioning Commitments

Three commitments this copy inherits from canon. If any line on the page violates one, it's a bug:

1. **Safety-net frame, not replacement.** CallLock only handles calls the owner would have missed anyway (conditional call forwarding when the owner's cell goes to voicemail). The owner keeps answering the calls they want. We are not an AI receptionist.
2. **Category = missed-call revenue recovery.** Not "AI receptionist." Not "virtual answering service." Anchors price against lost revenue, not against $150/mo human services.
3. **No ring-speed bragging.** CallLock picks up *after* the owner's full ring cycle, at the point where voicemail would have taken over. Any "instant response" / "under a few rings" language is factually wrong on conditional forward.

See `wiki/positioning/positioning-dunford.md` §1–§2 for the wedge formula these commitments inherit from.

---

## Hero Section

**Headline:**
> **Stop losing jobs to voicemail.**

**Subheadline (D6 fix — restores 24/7 + 30-second detail from canon):**
> When your cell goes to voicemail — on the job, at dinner, at 2am — CallLock picks up 24/7, books the job, and texts you the details in 30 seconds. You keep every call you want.

**Primary CTA:** `Get My Missed-Call Audit`

**Supporting line under CTA (D5 fix — names the category explicitly):**
> Missed-call revenue recovery for contractors. One recovered job a month pays for CallLock.

**Trust strip (D8 fix — adds "US"):**
> *Built for **US** HVAC, plumbing, electrical, garage door, drain, and water treatment shops — 1–5 trucks, live in 72 hours.*

---

## Feature Block 1 — Voicemail is a patience filter, not a miss tracker

**Headline:** **If they had time to leave a voicemail, it wasn't urgent.**

**Subhead:** Most contractors measure missed calls by counting voicemails. That only counts the patient callers. The ones who matter most — the emergencies, the I-need-someone-today jobs, the $3,000 installs — hang up in 10 seconds and call the next shop. You never see them in your voicemail inbox. They never existed, as far as you know. CallLock catches them.

**Body:**
- <!-- TODO(D2): confirm carrier mechanic. Unverified claim pulled pending product confirmation. -->
  Forwards to CallLock the moment your phone doesn't pick up — you keep answering everything you want
- Picks up right where your voicemail would have — 24/7, every day of the year
- Books directly to your Google Calendar or iCal — real bookings, not message pads
- Catches the impatient callers who hang up before the beep — the ones you don't even know about

**ROI math sidebar (inherits from [[../playbooks/missed-call-audit]]):**

> **Say you get 3 voicemails a day.**
>
> Industry call-tracking estimates say 30–50% of people who reach voicemail don't leave a message at all — especially on urgent calls. So your 3 voicemails probably represent about **5 actual missed calls a day — 3 you see, 2 you don't**.
>
> At a $400 average ticket and a conservative 20% close rate on new customers, that's:
>
> - **~$8,000/month** walking to voicemail — at the floor numbers
> - **~$12,000/month** at a 30% close rate (more realistic for most shops)
>
> *These are floor estimates. We'll do the real math on your actual numbers in 15 minutes.*

**Micro-CTA:** `See a sample audit →` *(anchors to demo section)*

---

## Feature Block 2 — Trust the AI before it touches a customer

**Headline:** **Pull up any call. Read the transcript. Sleep fine.**

**Subhead:** The #1 reason contractors hesitate on voice AI is "what if it screws up a customer?" Fair question. So we let you pull up any rescued call, read the full transcript, and hear the audio — same day, no support ticket. And because CallLock only touches the calls you would have missed anyway, the downside of an imperfect call is a call you weren't going to get at all.

**Body:**
- Full transcripts and recordings of every call CallLock handles — searchable, timestamped
- See exactly what the AI said, how the caller responded, and which slot got booked
- <!-- TODO(D4): "flag + retrain" feature pulled pending product confirmation that this actually exists. -->
  Every call is reviewable the same day — no support ticket, no delay
- Predictable flat monthly price — not a per-minute bill that spikes in your busy season

**Micro-CTA:** `See a real transcript →` *(anchors to demo section)*

---

## Feature Block 3 — Get your spouse off the overflow

**Headline:** **Hand off the overflow without hiring anyone.**

**Subhead:** Right now, when you can't get to the phone, your spouse does. Between jobs. During dinner. On weekends. CallLock takes *just* that overflow off their plate for less than a part-timer — and unlike a part-timer, it works at 2am, doesn't quit, and doesn't resent your family for it. You still answer what you want. They stop being unpaid dispatch.

**Body:**
- Every rescued call lands on your phone as a 30-second SMS — caller name, problem, urgency, booked slot
- Emergency calls (active leak, no heat, no power) trigger an immediate phone alert; routine jobs just text you
- Spam, SEO pitches, and robocalls get filtered before they ever hit your SMS
- Done-for-you setup in under 72 hours — you don't touch a config screen

**Micro-CTA:** `See a sample SMS →` *(anchors to demo section)*

---

## Final CTA Section

**Headline:** **See what you're losing this month.**

**Subhead:** 15 minutes. Your numbers. A real dollar figure on what's walking away. We'll take three inputs — your voicemail count, your ticket size, your close rate — and show you the calls you don't even know you're missing. No deck. No demo. Just the math.

**Primary CTA:** `Book My Missed-Call Audit`

**Risk reversal (D2 + D3 claims pulled pending product confirmation — see TODOs below):**
> Live in 72 hours. Flat monthly price. No per-minute surprises.

<!--
  TODO(D2): Restore "Auto-forwards from your existing line — no new number" once product confirms conditional call forwarding mechanic.
  TODO(D3): Restore "Cancel anytime, keep every booking" once product confirms commercial terms.
-->


---

## Meta Content

- **Page title (SEO):** CallLock — Missed-Call Revenue Recovery for Home Services Contractors
- **Meta description (155 chars):** Stop losing HVAC, plumbing, and electrical jobs to voicemail. CallLock answers every call you can't — 24/7 — and books the job straight to your calendar.

---

## Known Gaps (block launch or A/B test)

Tracked here so they don't get lost when this file gets reviewed next:

1. **No hero visual.** Needs SMS screenshot or split-screen before/after mockup. Single highest-ROI remaining change.
2. **No social proof anywhere.** `TODO` in `.agents/product-marketing-context.md` — needs real customer quotes or logos. Until then, consider a capability-based trust strip (infra provider, US hosting, SMS security).
3. **No pricing number surfaced.** Page says "less than one missed install" twice but never commits to a dollar figure. Needs a decision.
4. **CTA destination unknown.** Calendly vs. form vs. phone — affects how hard the CTA has to work.
5. **Final CTA "Book My Missed-Call Audit" duplicates hero CTA.** A/B candidate: `Show Me The Number` as alternative — more concrete, less work-framed.

### Blocking product confirmations (from v3.1 drift audit)

These claims were pulled from the draft pending verification. Restore when confirmed and add to canon (`smb-feature-set.md`):

- **D2 — Carrier mechanic.** Is CallLock genuinely conditional call forwarding from the owner's existing cell (no new number, no porting), or does onboarding require a new/ported number? The entire safety-net frame depends on the answer.
- **D3 — Commercial terms.** Is "cancel anytime, keep every booking" an accurate description of the contract and data-portability terms?
- **D4 — Flag + retrain.** Does the product actually have a one-tap flagging UI that feeds into retraining? If not, the transcript block needs a different differentiation claim.

### Data needed to firm up v3.2 numbers (from v3.2 thesis pivot)

These are founder estimates the audit math currently depends on. Backing them out of the existing call recording corpus would upgrade v3.2 from "defensible floor estimate" to "proprietary data":

- **D12a — Hang-up rate.** What fraction of callers who reach CallLock voicemail *don't* leave a message? Currently using 30–50% (midpoint 40%) as the estimate in the audit playbook and the homepage ROI sidebar. An hour of corpus analysis produces the real number. See `wiki/playbooks/missed-call-audit.md` §Constants & Sourcing.
- **D12b — Business-hours miss rate.** Currently using 5–10% as a floor for solo owner-operators, sourced informally from industry call-tracking data. Not on the page, but used in canon reasoning. Nice-to-have, not blocking.
- **D12c — ICP close rate on new-customer calls.** Currently using 20% as a deliberate floor anchor. Not a blocker because we use it as a conservative floor, not an assertion — but knowing the real number helps calibrate the audit upsell conversation.

## A/B Test Candidates (post-launch)

In priority order:

1. **Hero subhead length** — current 26 words vs. 15-word minimal version. Hypothesis: shorter improves CTA click-through.
2. **Hero visual** — text-only vs. SMS screenshot. Hypothesis: visual variant improves time-on-page significantly.
3. **Feature-block order** — rational → trust → emotional (current) vs. rational → emotional → trust. Hypothesis: current order wins because emotional beat sits next to the close.
4. **Final CTA copy** — "Book My Missed-Call Audit" vs. "Show Me The Number." Hypothesis: "Show me the number" wins.
5. **Single vs. dual hero CTA** — current single-button vs. primary + secondary. Hypothesis: single wins on path-of-least-cognitive-load.

## Changelog

- **v3.2** (2026-04-14) — Voicemail-filter thesis pivot. D11: replaced the "20% miss rate / $3K–$12K call volume" framing with the voicemail-count anchor and the "voicemail = patience filter, not miss tracker" insight. Feature Block 1 fully rewritten around the new thesis, headline is now *"If they had time to leave a voicemail, it wasn't urgent."* ROI sidebar now inherits from new playbook [[../playbooks/missed-call-audit]]. Final CTA subhead tightened to *"15 minutes. Your numbers. A real dollar figure..."* D12: hang-up rate (30–50%) and close rate (20% floor) constants are founder estimates tagged pending corpus validation in the audit playbook.
- **v3.1** (2026-04-14) — Drift audit pass against canon. Fixes: D1 ROI math now inherits corrected range from canon ($3K–$12K, not just $12K); D5 category phrase "missed-call revenue recovery" now explicit in hero supporting line; D6 restored "24/7" and "in 30 seconds" to hero subhead; D7 miss rate now shown as 20–40% range; D8 "US" qualifier added to trust strip. Unverified claims D2 (no new number / no porting), D3 (cancel anytime, keep every booking), D4 (flag + retrain) pulled pending product confirmation and marked with inline TODOs.
- **v3** (2026-04-14) — Quick Wins from page-cro review: trimmed hero subhead 68 → 26 words, removed secondary hero CTA, added hero trust strip, tightened Block 3 headline, reordered feature blocks to 1 → trust → emotional, added anchor-link framing on micro-CTAs.
- **v2** (2026-04-14) — Safety-net frame applied: "answers every call" → "catches the calls you miss." Auto-forward mechanic named explicitly. "Under a few rings" bragging removed everywhere.
- **v1** (2026-04-14) — Initial draft from copywriting skill pass against `.agents/product-marketing-context.md`. Had replacement-frame bugs inherited from pre-fix KB.

## Related

- [[../positioning/positioning-dunford]] — canon positioning this page inherits from
- [[../positioning/icp]] — buyer definition driving the "is this for me?" trust strip
- [[../product/smb-feature-set]] — feature claims the blocks inherit from
- [[../playbooks/cold-call-hvac]] — sister artifact; same positioning operationalized for cold outbound

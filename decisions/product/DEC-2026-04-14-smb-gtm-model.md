---
id: DEC-2026-04-14-smb-gtm-model
domain: product
status: active
---

# SMB GTM model: published pricing, templated setup, compressed cycle

## Context
Bravi (YC F25) targets the same category but fishes one tier up: $1M–$50M revenue home-services manufacturers and installers, 10–100 employees, $2K+ AOV, custom enterprise pricing, multi-week onboarding with a dedicated CSM. Their model is optimized for low-volume / high-ACV (~20 customers ≈ $200K ARR at $10K+ ACV).

CallLock's ICP (see [[wiki/playbooks/icp-definition]]) is one tier down: 3–15 employee HVAC/plumbing/electrical shops, $500K–$3M revenue, owner-operator buyer. At the $297/mo anchor, the structural math is inverted — 40+ customers to reach the same ARR, which forces every part of the GTM motion to look different from Bravi's.

This decision records the commitments that flow from that inversion, so the sales motion stays coherent instead of drifting toward enterprise habits that don't pencil at this ACV.

## Decision
Adopt a high-volume / low-ACV GTM model with four commitments:

### 1. Published tiered pricing (not "book a demo for a quote")
Price tiers are visible on the landing page. Owner-operators self-qualify in under 60 seconds or bounce. Hiding pricing signals "not for you" at this tier and breaks the sales velocity the model depends on. Tier structure segments by call volume (the real cost driver), not by negotiation.

### 2. Done-for-you setup as a productized 72-hour deliverable
Setup is templated and fixed-scope, delivered within 72 hours. Owner-operators will not touch a workflow builder, and we cannot afford to hand-craft 40+ deployments per year. This copies Bravi's DFY *framing* (it's a feature, not a service) but rejects their open-ended multi-week engagement model.

### 3. Compressed sales cycle: dial → 15-min demo → same-week close
No multi-touch enterprise cycle, no CSM post-sale. Cold dial, 15-minute demo same day or next day, decision within the week. Post-sale support is async — the DFY setup call replaces a CSM relationship.

### 4. Target unit economics
- ACV: $3,500–$9,500 (from $297–$797/mo tiers)
- Marginal infra cost: $30–$80/mo per customer (Twilio + LLM + TTS)
- Gross margin target: 80%+
- CAC ceiling: $500/customer
- Primary channel: cold outbound (7–9 AM and 4–6 PM local, between-job windows)

## Options Considered
- **Option A — Mirror Bravi.** Custom enterprise pricing, dedicated CSM, multi-week onboarding, LinkedIn + conference channels. Rejected: math doesn't work at sub-$10K ACV; LinkedIn doesn't reach 2-truck owner-operators.
- **Option B — Pure self-serve.** No setup, no sales calls, signup-to-live in an hour. Rejected: owner-operators will not configure a voice AI themselves, and the trust bar for "AI answers my customers" is too high for a checkout flow.
- **Option C — Hybrid: published pricing + productized DFY + founder-led cold outbound.** Chosen. Keeps the trust-building human touch where it matters (setup + first demo) and strips it everywhere else.

## Consequences
- Landing page must show prices before asking for contact info. Any "contact us for pricing" CTA on the pricing page is out of grain with this decision.
- Onboarding must be templated enough that a new customer is live in ≤72 hours without custom engineering. If setup drifts past 72h repeatedly, either the template is wrong or the ICP is wrong — not a staffing problem.
- Sales cycle instrumentation (dial → demo → close) measured in days, not weeks. A deal sitting >14 days without a decision is a lost deal, not a slow one.
- CAC above $500 means either pricing is too low or the channel is wrong. Revisit tiers before revisiting the channel — LSA channel data in [[wiki/playbooks/lsa-acquisition-channel]] already suggests cold outbound is the cheapest route.
- This decision does NOT commit to a specific tier table yet. Tier count, price points, and volume breakpoints are set once Phase 3 of [[wiki/playbooks/icp-definition]] validation produces real willingness-to-pay data.

## See Also
- [[wiki/competitors/bravi]] — source competitor whose model this explicitly inverts
- [[wiki/playbooks/icp-definition]] — the ICP this GTM model serves
- [[wiki/positioning/after-hours-wedge]] — the wedge the first-touch message leads with

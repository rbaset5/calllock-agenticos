# CallLock Research Wiki

LLM-compiled research intelligence for CallLock. This wiki is maintained by the LLM — rarely edit directly.

**Checkpoint: April 19, 2026** — Has this KB influenced 3+ concrete product decisions?

## Canon vs. Derived

Not all wiki content is equal. Two categories:

- **Canon** (source of truth — edit carefully, everything inherits from these):
  - `positioning/` — ICP, category, wedge, Dunford framework
  - `product/` — what CallLock *is* (feature set, offering, pitch)

- **Derived / research / operational** (inherit from canon — safe to churn):
  - `competitors/` — market research, not authored positioning
  - `playbooks/` — operational scripts derived from positioning
  - `marketing/` — homepage, ads, emails, pages (outputs derived from canon)
  - `voice-ai/` — technical research

If you change canon, re-check every derived file for drift. If you change a derived file, canon is unaffected.

## Dossiers

### Competitors
Battlecards on competing voice AI products.

**Incumbents (highest threat):**
- [[competitors/servicetitan-ai]] — ServiceTitan's NATIVE AI Voice Agent. 70-90% booking rate, 20-min setup, full CRM data access. The real threat.

**Direct competitors (home services):**
- [[competitors/sameday-ai]] — AI workforce for the trades, YC W23. 2M+ calls, $1.25B rev facilitated. Inbound-only.
- [[competitors/bravi]] — AI OS for home services installers, YC F25. Quoting + B2B2C angle. Newest entrant.
- [[competitors/drillbit]] — Full lifecycle AI admin for contractors, YC S24. Calls + CRM + quoting + payments.

**Adjacent verticals (dental/healthcare):**
- [[competitors/patientdesk-ai]] — AI receptionist for dental, YC W26. Insurance verification + lead gen.
- [[competitors/arini]] — AI receptionist for dental, YC W24. 17-person team, Threads/Meta pedigree.
- [[competitors/somn]] — AI receptionists for healthcare clinics, YC W24. Does outbound (patient follow-ups).

**Synthesis:**
- [[competitors/yc-trend-analysis]] — Trend analysis across 8 YC voice AI companies (S23–F25). Six key trends.

**Answering service incumbents:**
- [[competitors/answering-services]] — Smith.ai ($95/mo AI hybrid), Ruby, Nexa. Smith.ai is the real competitor. Most contractors use nothing.

**Horizontal players:**
- [[competitors/opencall-ai]] — AI voice agents for service businesses, YC W24. HIPAA compliant, proprietary model.
- [[competitors/twine]] — SMS-only receptionist for SMBs, YC S23. Text-based, not voice.

### Voice AI
Technical papers, implementation patterns, API capabilities.
- _No articles yet_

### Product
What CallLock *is* for the SMB ICP — features, offering, pitch.
- [[product/smb-feature-set]] — SMB feature set ranked by deal-closing power: Core 5, Next 3 differentiators, 2 demo winners, explicit non-goals, and the one-sentence offer.

### Positioning
Product positioning, category framing, ICP, and messaging foundations.
- [[positioning/icp]] — SMB home services ICP. 1–5 trucks, $300K–$2M, owner-operator buyer, 10+ calls/wk, $300+ ticket, 20%+ missed. Source of truth for qualification.
- [[positioning/positioning-dunford]] — Dunford five-component positioning built on the ICP. Category: "missed-call revenue recovery for home services contractors." Anchors price against lost revenue, not $150/mo human services.

### Playbooks
Sales objection handling, qualification logic, GTM strategies for home services. *(Derived from positioning.)*
- [[playbooks/cold-call-hvac]] — Dial-ready cold call decision tree for HVAC/plumbing/electrical. Operationalizes [[positioning/positioning-dunford]].
- [[playbooks/missed-call-audit]] — 15-minute math-only audit. The canonical conversion flow: 3 inputs, voicemail-filter insight, personalized dollar figure. Every marketing surface and sales channel inherits from this spec.

### Marketing
Homepage, landing pages, ads, email copy. *(Derived outputs of positioning + product. Not canon.)*
- [[marketing/homepage-v3]] — Homepage copy v3.2. Voicemail-filter thesis, math-only audit CTA. Inherits from [[positioning/positioning-dunford]] §3.5, [[product/smb-feature-set]], and [[playbooks/missed-call-audit]].

## Stats
- Total articles: 17 (10 battlecards + 1 synthesis + 2 positioning + 2 playbooks + 1 product + 1 marketing)
- Raw sources: 9
- Last ingest: 2026-04-14

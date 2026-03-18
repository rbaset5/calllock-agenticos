# CallLock Corporate Hierarchy & Agent Roster

**Date:** 2026-03-17
**Status:** Design approved
**Author:** Rashid Baset + Claude

## Overview

This document defines the complete agent roster for CallLock's AI workforce. Every agent maps 1:1 to a role in the corporate hierarchy. The roster is the source of truth for the 3D Command Center (which rooms exist, who sits where), the worker spec system (which agents can execute), and the scheduling system (who runs when).

**North Star Metric:** LTV:CAC Ratio > 3:1
**Core Operating Principle:** Every department is actively driving down Customer Acquisition Cost (CAC) or aggressively protecting Lifetime Value (LTV).

## Department Priority

Departments come alive in this order, reflecting business needs:

1. **Product Management + Engineering** — build and improve the product
2. **Growth Marketing** — fill the pipeline
3. **Customer Success** — retain customers, protect LTV
4. **Sales** — prioritize outbound (founder is the closer)
5. **Finance/Legal** — manage and protect the business

## Agent Roster (30 agents)

### Executive Suite (4 agents)

The C-Suite owns the overarching business model, market positioning, and unit economics. CEO makes final strategic decisions. Each exec owns a clear domain and metric.

| Agent | ID | Owns | Key Metric | Reports To |
|---|---|---|---|---|
| CEO / Founder | `exec-ceo` | Strategy, vision, closing deals, final decisions | LTV:CAC ratio | — |
| CPO | `exec-cpo` | What to build and why, pricing, value proposition | Feature adoption, retention | CEO |
| CTO | `exec-cto` | How to build it, reliability, architecture | Uptime, latency, zero dropped calls | CEO |
| COO | `exec-coo` | Post-sale operations, compliance, churn prevention | Churn rate, onboarding time, NPS | CEO |

**3D Office:** Executive Suite room with 4 desks. CEO desk is central and larger. Colored light on glass wall reflects company-wide health.

### Product Management (7 agents)

Led by the Head of Product, this department translates the CPO's macro-strategy into shipped features. Their lens for every PRD: "Does this decrease CAC (friction) or increase LTV (retention)?"

| Agent | ID | Discipline | Reports To |
|---|---|---|---|
| Head of Product (Director) | `pm-product-strategy` | Vision, business models (Lean Canvas, BMC), monetization/pricing, macro-environment analysis (SWOT, PESTLE, Porter's Five Forces) | CPO |
| PM — Discovery & Innovation | `pm-product-discovery` | Early-stage ideation, Opportunity Solution Trees, customer interviews, risky assumptions, pretotypes/experiments | Head of Product |
| PO — Execution | `pm-execution` | PRDs, sprint planning, outcome-focused roadmaps, team OKRs, user/job stories, stakeholder communication | Head of Product |
| User/Market Researcher | `pm-market-research` | User personas, customer journeys, market segments, TAM/SAM/SOM, user feedback analysis | Head of Product |
| Product Data Analyst | `pm-data-analytics` | Product metrics tracking, database queries, A/B test analysis, cohort retention analysis | Head of Product |
| ProdOps Manager | `pm-toolkit` | Operational backbone — coordination, proofing communications, hiring/resume review, internal process docs | Head of Product |
| Lead UI/UX Designer | `pm-designer` | Prototypes, usability testing, mobile-first design for contractors on job sites | Head of Product |

**3D Office:** Product Management room. Head of Product has corner office with glass wall. Health light reflects product sprint status.

### Engineering (4 agents)

Turns PRDs into reality. Heavy focus on latency, reliability, and zero dropped calls to prevent churn.

| Agent | ID | Focus | Reports To |
|---|---|---|---|
| VP of Engineering (Director) | `eng-vp` | Sprint planning, capacity estimation, engineering delivery | CTO |
| AI/Voice Engineer | `eng-ai-voice` | LLMs, prompt engineering, extraction pipeline, voice agent config, latency optimization | VP Eng |
| Fullstack Engineer | `eng-fullstack` | Triage and fix issues from Product Guardian. Read issues, examine code, propose fixes. | VP Eng |
| Product QA Engineer | `eng-product-qa` | Test scenarios (happy path + edge cases), zero hallucinations, seam validation, E2E product testing | VP Eng |

**Product Guardian:** eng-ai-voice and eng-product-qa form the Product Guardian system (see `2026-03-17-product-guardian-design.md`). eng-ai-voice guards the voice pipeline; eng-product-qa guards the seam between voice pipeline and customer app.

**3D Office:** Engineering room. VP Eng has corner office. Room shows high activity during sprint execution. eng-ai-voice and eng-product-qa desks have health indicator lights tied to voice pipeline and seam contract status.

### Growth Marketing (6 agents)

A highly efficient outbound machine designed to prospect, enrich leads, and fill the founder's demo calendar. Combines marketing strategy with conversion optimization.

| Agent | ID | Focus | Reports To |
|---|---|---|---|
| Head of Growth (Director) | `growth-head` | Top-of-funnel engine, cold email infra, lead magnet tools, data enrichment pipeline, ICP definition, beachhead segments, competitive battlecards, growth loops, positioning, North Star metric | CEO |
| CRO Specialist | `growth-cro` | Funnel optimization — squeeze every possible booked meeting from existing traffic. Tools: page-cro, signup-cro, onboard, form-cro, popup-cro, paywall | Head of Growth |
| Content & Copy | `growth-content` | Copywriting, copy editing, cold email templates, email sequences, social media content. Tools: copywriting, copy-edit, cold-email, email-seq, social | Head of Growth |
| Growth Engineer | `growth-engineer` | Rapidly builds and tests landing pages, ROI calculators, sign-up flows — bypasses core engineering backlog | Head of Growth |
| Lifecycle/Retention Marketer | `growth-lifecycle` | Automated onboarding comms (email, SMS, in-app) to drive early activation and prevent early-stage churn | Head of Growth |
| Growth/Data Analyst | `growth-analyst` | Full-funnel dashboards, growth experiment tracking, proving which experiments print money | Head of Growth |

**Boundary with Product Data Analyst:** Product Data Analyst (`pm-data-analytics`) answers "is the product good?" (feature adoption, cohort retention, A/B tests on product changes). Growth Data Analyst (`growth-analyst`) answers "is the funnel working?" (outbound conversion, landing page performance, CAC by channel). Same toolset, different questions and stakeholders.

**Boundary with CS Onboarding:** Lifecycle/Retention Marketer owns automated comms (drip email, SMS nudges, in-app tooltips). CS Onboarding Specialist owns white-glove setup (voice agent config, first 50 calls). Channel boundary, not domain overlap.

**3D Office:** Growth Marketing room. Head of Growth has corner office. Room has a visible "pipeline counter" showing leads → demos → closes funnel. CRO and Content & Copy desks show conversion metrics on floating displays.

### Sales (1 agent)

The founder is the sole closer. The SDR's job is to ensure every minute of founder time is spent on prospects with the highest probability of closing.

| Agent | ID | Focus | Reports To |
|---|---|---|---|
| SDR / Lead Router | `sales-sdr` | Prioritize who the founder calls next. Manages outbound cold calling queue, inbound filtering, lead enrichment verification, and qualification gate | CEO |

**SDR Outbound Enrichment SOP:**
1. Marketing data engine scrapes target trades business for: truck count, services offered, business hours
2. SDR uses enriched data for hyper-specific outreach wedge
3. SDR confirms prospect meets ICP threshold before routing to founder
4. Full enrichment profile + pain point attached to calendar invite

**3D Office:** Sales room. One desk, one agent. The room has a "call priority queue" board on the wall showing ranked prospects. Visually sparse by design — this is lean.

### Customer Success (5 agents)

The LTV protection agency. Ensures the product delivers immediate ROI. Organized in pods assigned to customer cohorts.

| Agent | ID | Focus | Reports To |
|---|---|---|---|
| Head of CS (Director) | `cs-head` | LTV protection, pod management, churn intervention | COO |
| Onboarding Specialist | `cs-onboarding` | First 14-30 days. Sole metric: first "saved call = saved revenue" moment within 7 days. White-glove voice agent setup, first 50 live calls | Head of CS |
| Account Manager (Pod Lead) | `cs-account-manager` | Strategic partner for business owner. Regular check-ins, ROI proof with hard data, renewals/upsells | Head of CS |
| Pod Technical Support | `cs-tech-support` | Dedicated troubleshooter assigned to AM's pod | Head of CS |
| Pod Success Associate | `cs-associate` | Day-to-day assistant. Routine tasks: prompt tweaks when contractor changes service area, minor config changes | Head of CS |

**3D Office:** Customer Success room. Head of CS has corner office. Room has a "customer health board" showing per-customer status (green/yellow/red). Onboarding desk shows active onboarding countdown timers.

### Finance/Legal (3 agents)

Manages and protects the business. Reports to COO.

| Agent | ID | Focus | Reports To |
|---|---|---|---|
| Finance Lead (Director) | `fin-lead` | Budget, unit economics, cash flow, CAC payback period tracking | COO |
| Accounting | `fin-accounting` | Books, billing, subscription management | Finance Lead |
| Legal/Compliance | `fin-legal` | Contracts, GDPR, compliance, vendor agreements | Finance Lead |

**3D Office:** Finance/Legal room. Finance Lead has corner office. Room is quieter/calmer than others — fewer state transitions, steady work.

## Reporting Hierarchy

```
CEO (exec-ceo)
├── CPO (exec-cpo)
│   ├── Head of Product (pm-product-strategy)
│   │   ├── PM Discovery (pm-product-discovery)
│   │   ├── PO Execution (pm-execution)
│   │   ├── Market Researcher (pm-market-research)
│   │   ├── Product Data Analyst (pm-data-analytics)
│   │   ├── ProdOps Manager (pm-toolkit)
│   │   └── Lead UI/UX Designer (pm-designer)
│   └── (Growth Marketing reports to CEO, not CPO)
│
├── CTO (exec-cto)
│   └── VP of Engineering (eng-vp)
│       ├── AI/Voice Engineer (eng-ai-voice)
│       ├── Fullstack Engineer (eng-fullstack)
│       └── Product QA Engineer (eng-product-qa)
│
├── COO (exec-coo)
│   ├── Head of CS (cs-head)
│   │   ├── Onboarding Specialist (cs-onboarding)
│   │   ├── Account Manager (cs-account-manager)
│   │   ├── Pod Technical Support (cs-tech-support)
│   │   └── Pod Success Associate (cs-associate)
│   └── Finance Lead (fin-lead)
│       ├── Accounting (fin-accounting)
│       └── Legal/Compliance (fin-legal)
│
├── Head of Growth (growth-head)
│   ├── CRO Specialist (growth-cro)
│   ├── Content & Copy (growth-content)
│   ├── Growth Engineer (growth-engineer)
│   ├── Lifecycle/Retention Marketer (growth-lifecycle)
│   └── Growth/Data Analyst (growth-analyst)
│
└── SDR / Lead Router (sales-sdr)
```

## Totals

| Department | Agents | Directors | Workers |
|---|---|---|---|
| Executive Suite | 4 | — | — |
| Product Management | 7 | 1 | 6 |
| Engineering | 4 | 1 | 3 |
| Growth Marketing | 6 | 1 | 5 |
| Sales | 1 | 0 | 1 |
| Customer Success | 5 | 1 | 4 |
| Finance/Legal | 3 | 1 | 2 |
| **Total** | **30** | **5** | **21** |

(Plus 4 executives = 30 total agents)

## 3D Command Center Room Layout

```
                ┌──────────────┐
                │  Executive   │
                │    Suite     │
                │  CEO CPO     │
                │  CTO COO     │
                └──────┬───────┘
                       │
    ┌──────────┐  ┌────┴────────────────┐  ┌──────────┐
    │ Product  │  │   CENTRAL LOBBY     │  │ Finance  │
    │ Mgmt     │  │                     │  │ /Legal   │
    │ 7 agents │──│ Deal Breaker Board  │──│ 3 agents │
    │          │  │ Quest Kiosk         │  │          │
    └──────────┘  │ Meeting Table       │  └──────────┘
                  │ Daily Memo Board    │
    ┌──────────┐  │                     │  ┌──────────┐
    │ Engin-   │──│                     │──│ Customer │
    │ eering   │  │                     │  │ Success  │
    │ 4 agents │  └────┬────────────────┘  │ 5 agents │
    └──────────┘       │                   └──────────┘
                  ┌────┴──────┐  ┌──────────┐
                  │ Growth    │  │ Sales    │
                  │ Marketing │──│ 1 agent  │
                  │ 6 agents  │  │          │
                  └───────────┘  └──────────┘
```

## The Growth Loop (Deal Breaker Ledger)

Sales and Marketing log **problems** in the Deal Breaker Ledger: "We lost 20% of deals because of X." Product and Engineering own **solutions**, ensuring the roadmap is built for scale, not custom one-offs.

**3D Office visualization:** Physical board in the Central Lobby. Growth Marketing agents walk to the lobby and write entries. Product Management agents read entries and carry them back to their room. The board shows a running count of open deal breakers. Click to expand details.

**Data flow:**
- Growth Marketing writes: problem description, evidence (lost deal count, objection frequency)
- Product reads: prioritizes against roadmap, assigns to sprint or defers with rationale
- Board shows: open count, oldest unresolved, resolution rate

## Worker Spec Status

| Agent | Worker Spec | Status |
|---|---|---|
| `exec-ceo` | Needs creation | Planned |
| `exec-cpo` | Needs creation | Planned |
| `exec-cto` | Needs creation | Planned |
| `exec-coo` | Needs creation | Planned |
| `pm-product-strategy` | Needs creation (maps partially to existing `product-manager.yaml`) | Planned |
| `pm-product-discovery` | Needs creation | Planned |
| `pm-execution` | Needs creation (maps partially to existing `product-manager.yaml`) | Planned |
| `pm-market-research` | Needs creation (maps partially to existing `customer-analyst.yaml`) | Planned |
| `pm-data-analytics` | Needs creation (maps partially to existing `customer-analyst.yaml`) | Planned |
| `pm-toolkit` | Needs creation | Planned |
| `pm-designer` | Needs creation (maps to existing `designer.yaml`) | Planned |
| `eng-vp` | Needs creation | Planned |
| `eng-ai-voice` | Designed in Product Guardian spec | Ready to build |
| `eng-fullstack` | Needs creation (maps to existing `engineer.yaml`) | Planned |
| `eng-product-qa` | Designed in Product Guardian spec | Ready to build |
| `growth-head` | Needs creation | Planned |
| `growth-cro` | Needs creation | Planned |
| `growth-content` | Needs creation | Planned |
| `growth-engineer` | Needs creation | Planned |
| `growth-lifecycle` | Needs creation | Planned |
| `growth-analyst` | Needs creation | Planned |
| `sales-sdr` | Needs creation | Planned |
| `cs-head` | Needs creation | Planned |
| `cs-onboarding` | Needs creation | Planned |
| `cs-account-manager` | Needs creation | Planned |
| `cs-tech-support` | Needs creation | Planned |
| `cs-associate` | Needs creation | Planned |
| `fin-lead` | Needs creation | Planned |
| `fin-accounting` | Needs creation | Planned |
| `fin-legal` | Needs creation | Planned |

**Existing worker specs to retire/rename:**
- `product-manager.yaml` → split into `pm-product-strategy` + `pm-execution`
- `customer-analyst.yaml` → split into `pm-market-research` + `pm-data-analytics`
- `designer.yaml` → rename to `pm-designer`
- `engineer.yaml` → rename to `eng-fullstack`
- `product-marketer.yaml` → absorbed by `growth-head` (Head of Growth owns GTM + growth strategy)

## VP of Product Q1 OKRs: Lock In Retention

- **Objective:** Guarantee the "Aha!" moment in week one to secure long-term retention.
  - **KR 1:** Reduce technical onboarding setup time for Onboarding Specialists to under 48 hours.
  - **KR 2:** Achieve 99% successful call-routing rate and zero hallucinations on first 50 live calls for every new client.
  - **KR 3:** Implement real-time product usage dashboard for AMs that flags accounts where AI call volume drops by 20% WoW.

## Head of Growth Q1 OKRs: High-Velocity, Low-CAC Pipeline

- **Objective:** Build a high-velocity outbound engine that maxes out the Founder's demo calendar.
  - **KR 1:** Increase cold email to demo-booked conversion rate via tiered lead enrichment waterfall.
  - **KR 2:** Generate target of highly qualified inbound demos from lead magnet assets.
  - **KR 3:** Ensure 85%+ of all demos routed to Founder meet strict qualification criteria (3+ trucks) to eliminate wasted founder time.

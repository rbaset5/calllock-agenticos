---
id: inbound-scoring-rubric
title: Inbound Lead Scoring Rubric
graph: inbound-pipeline
owner: founder
last_reviewed: "2026-03-16"
trust_level: curated
progressive_disclosure:
  summary_tokens: 200
  full_tokens: 2000
---

# Inbound Lead Scoring Rubric

## Overview

This rubric is used by `scorer.py` to evaluate inbound emails. The scorer sends the sanitized message text, sender research, and this rubric to the LLM. The LLM returns a structured score. The `rubric_hash` on `inbound_messages` tracks which version of this rubric was used.

## Scoring Dimensions

| Dimension | Weight | Description |
|---|---|---|
| Intent signal | 35% | Is the sender explicitly asking about missed calls, answering services, call handling, or pricing? In-market language scores highest. |
| Business fit | 25% | Is this an HVAC company (or adjacent trade)? Right size (3+ techs, commercial/residential mix)? Serviceable geography? |
| Urgency | 20% | Time pressure: busy season approaching, recent staff loss, competitor switching, "need this now" language. |
| Authority | 15% | Owner or decision-maker vs. office manager vs. technician. Owner emails convert 3x. Office managers still convert but slower. |
| Budget signal | 5% | Mentions current spend, willingness to invest, price comparison. Low weight because at $149-249/mo, budget is rarely the blocker. |

## Scoring Scale

Each dimension is scored 0-100. The total score is the weighted sum.

### Dimension Scoring Guide

**Intent signal (35%)**
- 90-100: Explicitly mentions missed calls, answering service, or asks for pricing/demo
- 70-89: Mentions call handling problems or phone coverage gaps
- 40-69: General interest in business tools or customer service improvement
- 10-39: Vague inquiry, no call-handling language
- 0-9: No discernible intent related to our product

**Business fit (25%)**
- 90-100: HVAC company, 3+ techs, commercial + residential, serviceable area
- 70-89: HVAC or adjacent trade (plumbing, electrical), right size
- 40-69: Service business but not HVAC/trades, or solo operator
- 10-39: Business but wrong industry entirely
- 0-9: Not a business (consumer, student, etc.)

**Urgency (20%)**
- 90-100: "Need this now", mentions lost revenue, busy season imminent, staff just quit
- 70-89: "Looking to start soon", seasonal language, competitive pressure
- 40-69: "Exploring options", "planning for next quarter"
- 10-39: No time pressure, information-gathering tone
- 0-9: Explicitly says "not ready" or "just researching for later"

**Authority (15%)**
- 90-100: Owner, CEO, or president (signature, domain ownership, or explicit mention)
- 70-89: GM, operations manager, or partner
- 40-69: Office manager, dispatcher, or admin
- 10-39: Technician, intern, or unclear role
- 0-9: Automated system, vendor, or non-human sender

**Budget signal (5%)**
- 90-100: Mentions current spend on answering service, asks about pricing tiers
- 70-89: Implies budget awareness ("what's the investment?", "ROI question")
- 40-69: No budget language but no price sensitivity signals either
- 10-39: Price-shopping language ("cheapest option", "free trial only")
- 0-9: Explicitly says budget is zero or not applicable

## Score Thresholds

| Tier | Score range | Action | Pipeline behavior |
|---|---|---|---|
| `exceptional` | 85-100 | Escalate to founder within 1 hour | Auto-promote to prospect, generate personalized draft, emit escalation event |
| `high` | 65-84 | Auto-promote to prospect, send reply | Promote to Growth Memory, generate draft, assign stage `qualified` |
| `medium` | 40-64 | Draft reply (pending founder review) | Do NOT promote. Generate draft with `send_status: 'pending_review'`. Assign stage `new` |
| `low` | 20-39 | Log, no reply | Persist message, assign stage `new`, no draft generated |
| `spam` | 10-19 | Auto-archive | Assign stage `archived`, no draft |
| `non-lead` | 0-9 | Auto-archive | Assign stage `archived`, no draft |

## Disqualifiers

These override the score and force `action: 'non-lead'` regardless of dimension scores:

- **Wrong industry**: Not a service business (retail, manufacturing, SaaS, etc.)
- **Residential-only solo operator**: Single person, no employees, residential-only work
- **Unsubscribe request**: Message contains "unsubscribe", "remove me", "stop emailing"
- **Competitor employee**: Sender domain matches known competitor domains
- **Vendor pitch**: Sender is selling to us, not buying from us

### Known competitor domains

```yaml
competitor_domains:
  - servicetitan.com
  - housecallpro.com
  - jobber.com
  - fieldedge.com
  - successware.com
  - servicefusion.com
  - mhelpdesk.com
  - kickserv.com
  - ruby.com            # Ruby Receptionists
  - smith.ai
  - answerhero.com
  - patlive.com
  - answerconnect.com
```

## Bonus Signals

These add points on top of the weighted score (capped at 100 total):

| Signal | Bonus | Detection |
|---|---|---|
| Referral mention | +15 | Contains "referred by", "recommended by", "[name] told me", "heard about you from" |
| Multi-location | +10 | Contains "locations", "branches", "franchises", "multiple offices" |
| Named competitor switching | +10 | Mentions a competitor from the list above in context of switching or being unhappy |
| Specific call volume | +10 | Mentions numeric call volume ("50+ calls", "get about 30 calls a day") |
| After-hours pain | +5 | Mentions "after hours", "weekends", "evenings", "overnight" specifically |

## LLM Prompt Template

The scorer constructs the following prompt:

```
You are evaluating an inbound email to determine if the sender is a qualified lead for CallLock, a missed-call capture service for HVAC and trade businesses.

## Scoring rubric

{this rubric, dimensions section}

## Sender research

{sender_research JSON from enrichment_cache}

## Email to evaluate

From: {from_addr}
Subject: {subject}
Body:
{body_text}

## Instructions

Score each dimension 0-100. Then compute the weighted total.
Check for disqualifiers — if any match, set action to 'non-lead' regardless of score.
Check for bonus signals — add bonus points (cap total at 100).

Respond in this exact JSON format:
{
  "dimensions": {
    "intent_signal": <0-100>,
    "business_fit": <0-100>,
    "urgency": <0-100>,
    "authority": <0-100>,
    "budget_signal": <0-100>
  },
  "bonuses": [{"signal": "<name>", "points": <int>}],
  "disqualifier": "<name or null>",
  "total_score": <0-100>,
  "action": "<exceptional|high|medium|low|spam|non-lead>",
  "reasoning": "<2-3 sentence explanation>"
}
```

## Rubric Versioning

The `rubric_hash` stored on each scored message is `sha256(rubric_text)[:12]`. This allows tracking which rubric version produced which scores. When the rubric changes, old scores are NOT retroactively updated — the hash provides auditability.

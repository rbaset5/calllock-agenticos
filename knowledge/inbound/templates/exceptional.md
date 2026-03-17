---
id: inbound-template-exceptional
title: Reply Template — Exceptional Tier
graph: inbound-pipeline
owner: founder
last_reviewed: "2026-03-16"
trust_level: curated
progressive_disclosure:
  summary_tokens: 100
  full_tokens: 500
---

# Exceptional Tier Reply Template

## When to use

Score 85-100. Owner or decision-maker with clear intent, urgency, and business fit. These leads close fast — the reply should match their energy.

## Tone

Direct founder energy. Short. Urgent. Personal. Reference their specific pain point from the email.

## Template

```
Subject: Re: {{original_subject}}

Hey {{first_name}} —

{{pain_point_mirror}}. That's exactly what we built CallLock to fix.

We're helping HVAC shops capture every call — after hours, weekends, when the front desk is slammed. {{proof_point}}.

I'd love to show you how it works for a shop like yours. Here's my calendar — grab 15 minutes this week:

{{booking_link}}

— Rashid
Founder, CallLock
{{phone}}
```

## Variable guide

| Variable | Source | Fallback |
|---|---|---|
| `{{first_name}}` | Parsed from `from_addr` or email body signature | "there" |
| `{{pain_point_mirror}}` | LLM extracts the core pain from their email and mirrors it back in 1 sentence | "Losing calls is losing revenue" |
| `{{proof_point}}` | Selected from proof registry based on segment match | "One shop went from ~15 missed calls/week to zero in the first month" |
| `{{booking_link}}` | Config: `escalation.booking_url` | "Reply to this email and I'll send you a link" |
| `{{phone}}` | Config: `escalation.founder_phone` | omit line |

## Constraints

- Maximum 5 sentences (excluding signature)
- Must reference something specific from their email (not generic)
- CTA is always booking a call — no "learn more" or "check out our website"
- No exclamation marks. Confidence, not enthusiasm.

## Fallback (if LLM unavailable)

```
Hey {{first_name}} —

Saw your note about {{subject_keywords}}. We built CallLock specifically for HVAC shops that can't afford to miss calls.

Worth a quick conversation? Here's my calendar:

{{booking_link}}

— Rashid
Founder, CallLock
{{phone}}
```

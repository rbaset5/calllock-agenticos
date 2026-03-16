---
id: inbound-template-high
title: Reply Template — High Tier
graph: inbound-pipeline
owner: founder
last_reviewed: "2026-03-16"
trust_level: curated
progressive_disclosure:
  summary: 100
  full: 500
---

# High Tier Reply Template

## When to use

Score 65-84. Right industry + clear intent, but may not be the owner, or urgency is moderate. These leads need a warm, specific reply with one proof point.

## Tone

Warm and direct. Still founder voice, but slightly more context than exceptional. One proof point to build credibility. CTA is booking a call this week.

## Template

```
Subject: Re: {{original_subject}}

Hey {{first_name}} —

Thanks for reaching out. {{pain_point_acknowledgment}}.

We built CallLock for exactly this — HVAC shops that need every call answered, especially {{timing_context}}. {{proof_point}}.

Most shops our size are up and running in about a day. If you want, grab 15 minutes and I'll walk you through how it works:

{{booking_link}}

Either way, happy to answer any questions you've got.

— Rashid
Founder, CallLock
{{phone}}
```

## Variable guide

| Variable | Source | Fallback |
|---|---|---|
| `{{first_name}}` | Parsed from `from_addr` or email body | "there" |
| `{{pain_point_acknowledgment}}` | LLM mirrors their concern in 1 sentence | "Sounds like you're dealing with missed calls" |
| `{{timing_context}}` | LLM extracts seasonal or timing context | "during busy season" |
| `{{proof_point}}` | Selected from proof registry | "One shop went from ~15 missed calls/week to zero in the first month" |
| `{{booking_link}}` | Config | "Reply here and I'll send a link" |
| `{{phone}}` | Config | omit line |

## Constraints

- Maximum 7 sentences (excluding signature)
- Must include one proof point (number or customer outcome)
- CTA is booking a call — framed as optional ("if you want")
- Friendly but not salesy. No "amazing opportunity" or "don't miss out" language.

## Fallback (if LLM unavailable)

```
Hey {{first_name}} —

Thanks for reaching out about {{subject_keywords}}. We help HVAC shops capture the calls they miss — after hours, weekends, and when the front desk is busy.

Most shops are up and running in about a day. Want to see how it works?

{{booking_link}}

— Rashid
Founder, CallLock
{{phone}}
```

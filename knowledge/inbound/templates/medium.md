---
id: inbound-template-medium
title: Reply Template — Medium Tier
graph: inbound-pipeline
owner: founder
last_reviewed: "2026-03-16"
trust_level: curated
progressive_disclosure:
  summary: 100
  full: 500
---

# Medium Tier Reply Template

## When to use

Score 40-64. Vague interest, right industry but unclear fit, or information-gathering tone. These leads need context and credibility before they'll take a call. Reply is drafted but held for founder review (`send_status: 'pending_review'`).

## Tone

Consultative, helpful, no pressure. Information-first. Acknowledge what they asked about, provide context on how CallLock works, soft CTA. The goal is to earn the next reply, not book a call immediately.

## Template

```
Subject: Re: {{original_subject}}

Hey {{first_name}} —

Thanks for the note. {{context_acknowledgment}}.

Here's the short version of how CallLock works: when a call comes in that your team can't pick up — after hours, weekends, or when everyone's on a job — our system answers, qualifies the caller, and books the job for you. No calls slip through.

{{industry_context}}.

Most of our shops pay between $149-249/mo depending on call volume, and setup takes about a day.

If that sounds relevant, I'm happy to walk you through it:

{{booking_link}}

No pressure either way — happy to answer questions over email too.

— Rashid
Founder, CallLock
{{phone}}
```

## Variable guide

| Variable | Source | Fallback |
|---|---|---|
| `{{first_name}}` | Parsed from `from_addr` or email body | "there" |
| `{{context_acknowledgment}}` | LLM summarizes what they asked about | "Sounds like you're exploring call handling options" |
| `{{industry_context}}` | LLM tailors one sentence to their trade | "For HVAC shops, the biggest win is usually capturing after-hours emergency calls that would otherwise go to voicemail" |
| `{{booking_link}}` | Config | "Reply here and I'll send a link" |
| `{{phone}}` | Config | omit line |

## Constraints

- Maximum 9 sentences (excluding signature)
- Must explain what CallLock does (these leads may not know)
- Include pricing range (transparency builds trust at this tier)
- CTA is soft: "if that sounds relevant" or "happy to answer questions over email"
- No urgency language. These leads aren't ready for pressure.
- "No pressure" is genuine, not a sales trick.

## Fallback (if LLM unavailable)

```
Hey {{first_name}} —

Thanks for reaching out. CallLock helps HVAC and trade businesses capture every incoming call — especially after hours and weekends when your team can't pick up.

We answer, qualify the caller, and book the job for you. Most shops pay $149-249/mo and setup takes about a day.

If that sounds like it could help, I'm happy to walk you through it:

{{booking_link}}

— Rashid
Founder, CallLock
{{phone}}
```

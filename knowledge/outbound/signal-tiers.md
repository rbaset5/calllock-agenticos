---
id: outbound-signal-tiers
title: Signal Tiers
graph: outbound
owner: rashid
last_reviewed: 2026-03-22
trust_level: authoritative
progressive_disclosure: foundational
---

# Signal Tiers

## Tier 1

- `paid_demand`
  Detection: lead source shows active ad spend, LSA participation, or paid-search flags.
  Weight: 25
- `after_hours_behavior`
  Detection: silent probe after 7pm local results in `no_answer` or `voicemail`.
  Weight: 25
- `no_backup_intake`
  Detection: owner-only phone handling, no dispatcher/admin contact, or no overflow path in listing evidence.
  Weight: 20

## Tier 2

- `hours_mismatch`
  Detection: listing hours signal weekday-only or limited service windows against an emergency trade.
  Weight: 10
- `owner_operated`
  Detection: owner name present, non-franchise, small-team cues, or first-call routing to the owner.
  Weight: 10
- `no_admin_layer`
  Detection: no office manager, CSR, dispatcher, or front-desk role visible in lead evidence.
  Weight: 10

## Tier 3

- `review_pain`
  Detection: low rating, low review volume, or review text pointing to missed calls / poor response.
  Weight: 10
- `simple_ivr`
  Detection: basic voicemail tree, generic greeting, or limited menu without live coverage.
  Weight: 5

---
id: hvac-pack-migration-notes
title: HVAC Pack Migration Notes
graph: industry-pack
owner: platform
last_reviewed: 2026-03-12
trust_level: curated
progressive_disclosure:
  summary_tokens: 90
  full_tokens: 180
---

# HVAC Pack Migration Notes

- Source tree: `/Users/rashidbaset/conductor/workspaces/retellai-calllock/madrid/V2/src`
- Taxonomy tags are extracted from procedural TypeScript objects in `classification/tags.ts`.
- Phrase matching is negation-aware with a 40-character lookback in V2. The declarative pack stores aliases, but the runtime classifier still needs to respect the negation rule.
- Booking configuration is currently Cal.com-specific and includes the hardcoded event type `3877847`.
- The V2 source exposes 4 urgency tiers: `LifeSafety`, `Urgent`, `Routine`, `Estimate`.

---
id: DEC-2026-03-21-outbound-single-worker
domain: product
status: active
---

# Outbound pipeline is single-worker Scout

## Context
Original design had two workers: Scout (discovery + scoring) and Composer (email outreach via Instantly). Founder decided to cold-call personally instead of emailing, eliminating the need for Composer entirely.

## Options Considered
- **Option A:** Two workers (Scout + Composer) with Instantly email infrastructure.
- **Option B:** Single Scout worker that discovers, scores, silent-probes (Twilio AMD), and surfaces a daily ranked call list. Founder calls personally.

## Decision
Option B. Single Scout worker. Founder cold-calls 50-100/day from Discord call list.

## Consequences
- Instantly email infrastructure removed from v1 (deferred to v2).
- Composer worker eliminated.
- Discovery uses pre-existing 11GB leads database, not Google scraping.
- Call testing uses Twilio silent probe with AMD, not Retell voice agent.
- Discord channels: `#outbound-calls` (daily call list + outcome logging), `#outbound-feed` (status).
- Learning loop tracks which signals predict "interested" outcomes.

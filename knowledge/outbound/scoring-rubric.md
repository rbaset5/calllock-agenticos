---
id: outbound-scoring-rubric
title: Dispatch Maturity Scoring Rubric
graph: outbound
owner: rashid
last_reviewed: 2026-03-22
trust_level: authoritative
progressive_disclosure: foundational
---

# Dispatch Maturity Scoring

## Dimension Weights

- `paid_demand`: 25
- `after_hours`: 25
- `backup_intake`: 20
- `hours`: 10
- `owner_operated`: 10
- `review_pain`: 10

## Tier Thresholds

- `a_lead`: total score >= 75
- `b_lead`: total score >= 50
- `c_lead`: total score >= 30
- `disqualified`: total score < 30

## Operating Notes

- The score is additive and capped at 100.
- Zero detected signals yields score `0` and tier `disqualified`.
- Phone probe evidence should dominate after-hours scoring once available.

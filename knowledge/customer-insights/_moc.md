---
id: customer-insights-moc
title: Customer Insights Graph
graph: customer-insights
owner: operations
last_reviewed: 2026-03-12
trust_level: provisional
progressive_disclosure:
  summary_tokens: 60
  full_tokens: 120
---

# Customer Insights

This graph starts as a placeholder in Phase 1. Phase 4 adds the raw -> sanitized -> structured customer content pipeline.

Current implementation notes:

- Raw transcripts enter through the harness content pipeline endpoint.
- Sanitized and structured outputs are persisted tenant-scoped before reuse.
- Eval datasets can be derived from sanitized outputs only.

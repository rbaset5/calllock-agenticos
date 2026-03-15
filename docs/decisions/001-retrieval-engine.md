# ADR 001: Retrieval Engine Evaluation

Status: Accepted

## Context

The architecture spec called for evaluating QMD (Query-over-Markdown, a hybrid retrieval index combining structured YAML frontmatter queries with full-text search) or an equivalent during Phase 1.

## Decision

Accept the current file-backed retrieval approach. The knowledge volume is small enough that a heavier retrieval layer is not justified.

Current approach: file-backed retrieval via markdown/YAML traversal, wiki-link resolution, and context assembly prioritization.

## Upgrade Trigger

Revisit when:

- Measured retrieval p95 > 500ms
- Relevance is observably poor
- Context assembly starts dropping important nodes under budget pressure

Evaluate QMD or another hybrid index only when a trigger is hit.

## Consequences

- No new retrieval infrastructure needed now
- Upgrade path is documented and tied to observable metrics
- The metrics API (ADR pending) will make retrieval p95 measurable

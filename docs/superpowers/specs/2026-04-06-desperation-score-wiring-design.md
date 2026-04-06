# Desperation Score Wiring into scoring.py

**Date:** 2026-04-06
**Status:** Approved
**Branch:** Lead-Pipeline

## Problem

Two parallel scoring systems exist that don't compose:

1. **`scoring.py`** — ICP dispatch score (0-100). Uses LSA metadata signals (ads, hours, reviews count/rating, website vendors). Produces `total_score` + `score_tier`.
2. **`review_scanner.py`** — Desperation score (0-100). Uses LLM-extracted signals from actual Google review text plus metadata (response_rate, trend_delta). Stored as a separate column.

The `review_pain` signal in `scoring.py` is a blunt heuristic: `rating < 4.2 or reviews < 20` for +10 points. It ignores the rich desperation data that the review scanner already computes and persists.

Website scanner output (`vendors`, `has_call_tracking`) only feeds the binary `already_served: -15` penalty — unrelated to desperation.

## Decisions

1. **Fold desperation into `total_score`** — not a separate composite score.
2. **Replace `review_pain` when enrichment exists** — fall back to the old heuristic for un-enriched prospects.
3. **20-point weight budget** — steal from `hours` (10 -> 5) and `owner_operated` (10 -> 5).
4. **Website scan stays as penalty only** — no interaction with desperation scoring.
5. **Enrich-at-score-time (lazy)** — `scoring.py` reads the already-persisted `desperation_score` from the prospect row. No coupling between scanner and scorer at execution time.

## Weight Rebalancing

| Signal | Old | New |
|--------|-----|-----|
| paid_demand | 25 | 25 |
| after_hours | 25 | 25 |
| backup_intake | 20 | 20 |
| hours | 10 | **5** |
| owner_operated | 10 | **5** |
| review_pain | 10 | **20** |
| already_served | -15 | -15 |

The `review_pain` key name is preserved in `DISPATCH_SCORE_WEIGHTS` to avoid downstream renames.

## Scoring Logic in `extract_signal_rows`

The review_pain signal extraction (scoring.py lines 52-62) becomes a two-branch check:

### Branch 1: Enriched prospect

If `raw_source` contains a `desperation_score` that is not `None` (set by `review_scanner.py` via `store.enrich_prospect_reviews`). Note: `0` is a valid enriched value meaning the scanner ran and found no pain — this should produce a score of 0, NOT fall through to the heuristic.

```
score = round(desperation_score / 100 * 20)
```

- Desperation 80 -> 16 points
- Desperation 40 -> 8 points
- Desperation 100 -> 20 points

Signal row: `signal_type: "review_pain"`, `signal_tier: 3`, `raw_evidence` includes `desperation_score` and `enrichment_source: "review_scanner"`.

### Branch 2: Un-enriched fallback

If no `desperation_score`, apply old heuristic (`rating < 4.2 or reviews < 20`) capped at **5 points** (not the old 10). This keeps un-enriched prospects from competing equally with enriched ones on this dimension.

Signal row: same structure, `raw_evidence` includes `reviews`, `rating`, and `enrichment_source: "heuristic"`.

## Data Flow

`desperation_score` is a top-level column on the prospect row (not inside `raw_source`). It's already written by `store.enrich_prospect_reviews`.

In `score_prospects`, before calling `extract_signal_rows`, inject the enrichment field:

```python
raw_source["desperation_score"] = prospect.get("desperation_score")
```

No new DB queries — `store.list_outbound_prospects` already returns the full prospect row. No changes to `review_scanner.py` or `store.py`.

## Files Changed

| File | Change |
|------|--------|
| `harness/src/outbound/constants.py` | Update `DISPATCH_SCORE_WEIGHTS`: hours 10->5, owner_operated 10->5, review_pain 10->20 |
| `harness/src/outbound/scoring.py` | Replace review_pain extraction block with two-branch logic; inject `desperation_score` into `raw_source` in `score_prospects` |
| `harness/tests/outbound/test_scoring.py` | Update expected dimension values; add enriched prospect tests; adjust tier boundary fixtures |

## Test Plan

1. **Existing heuristic still works** — Prospect with no `desperation_score`, rating 3.5, 8 reviews -> review_pain = 5
2. **Enriched scaling** — Prospect with `desperation_score: 80` -> review_pain = 16
3. **Enriched overrides heuristic** — Prospect with both rating/reviews AND desperation_score -> uses desperation path
4. **Zero desperation** — Prospect with `desperation_score: 0` -> review_pain = 0 (enrichment ran, found nothing)
5. **Tier boundaries** — Adjust fixtures so A/B/C thresholds are tested with new weights
6. **Idempotency** — Re-scoring the same prospect produces identical results

# ADR 014: Wedge Fitness Score Computation Specification

Status: Proposed

## Context

The design doc (§11) defines the Wedge Fitness Score as a weighted composite of 9 components (0-100 scale) with 4 phase-transition gates and hard kill criteria. The component weights and gate thresholds are specified. What's missing for implementation:

1. **Normalization functions** — how raw metrics (e.g., "booked pilot rate of 3.2%") become 0-100 component scores
2. **Data source queries** — which tables and time windows feed each component
3. **Edge cases** — what happens when a component has insufficient data (cold start)

Without these, Droid cannot implement the weekly Growth Advisor computation.

## Decision

### Component normalization functions

Each component takes a raw metric and returns a score 0-100. All functions are monotonically non-decreasing (higher raw metric → higher score) and clamp at 0 and 100.

**All computations use a 28-day rolling window unless otherwise noted.**

#### 1. Booked pilot rate (weight: 15%)

```
Raw metric: pilot_starts / total_prospects_contacted (28-day window)
```

| Raw rate | Score |
|----------|-------|
| 0% | 0 |
| 1% | 25 |
| 2% | 50 |
| 3% | 75 |
| ≥ 4% | 100 |

**Linear interpolation** between breakpoints. Formula: `min(100, raw_rate / 0.04 * 100)`

**Data source:**
```sql
-- Numerator: prospects reaching PILOT_STARTED
SELECT COUNT(DISTINCT prospect_id)
FROM touchpoint_log
WHERE tenant_id = :tid AND touchpoint_type = 'pilot_started'
  AND created_at >= now() - interval '28 days';

-- Denominator: prospects with any outbound touch
SELECT COUNT(DISTINCT prospect_id)
FROM touchpoint_log
WHERE tenant_id = :tid AND touchpoint_type LIKE 'email_sent%'
  AND created_at >= now() - interval '28 days';
```

#### 2. Attribution completeness (weight: 15%)

```
Raw metric: conversions_with_full_attribution / total_conversions (28-day window)
```

"Full attribution" = touchpoint has non-null `attribution_token` AND token validates successfully.

| Raw rate | Score |
|----------|-------|
| < 40% | 0 (below hard kill threshold) |
| 40% | 10 |
| 60% | 30 |
| 80% | 60 |
| 90% | 80 |
| ≥ 95% | 100 |

**Piecewise linear interpolation** between breakpoints.

**Data source:**
```sql
-- Conversions with valid attribution
SELECT
  COUNT(*) FILTER (WHERE attribution_token IS NOT NULL) AS attributed,
  COUNT(*) AS total
FROM touchpoint_log
WHERE tenant_id = :tid
  AND touchpoint_type IN ('meeting_booked', 'pilot_started')
  AND created_at >= now() - interval '28 days';
```

#### 3. Proof coverage (weight: 15%)

```
Raw metric: objections_at_covered / total_objections_tracked
```

Uses the proof coverage map from Growth Memory. An objection is "covered" when proof_asset exists and has sample_size ≥ 5.

| Raw rate | Score |
|----------|-------|
| 0% | 0 |
| 30% | 25 |
| 50% | 50 |
| 70% | 75 |
| ≥ 90% | 100 |

**Piecewise linear interpolation** between breakpoints (same pattern as attribution completeness).

**Data source:**
```sql
SELECT
  COUNT(*) FILTER (WHERE sample_size >= 5 AND conversion_rate > 0) AS covered,
  COUNT(*) AS total
FROM segment_performance
WHERE tenant_id = :tid AND proof_asset IS NOT NULL;
```

#### 4. Founder alignment (weight: 10%)

```
Raw metric: approved_recommendations / total_recommendations (all time, not windowed)
```

Uses `founder_overrides` table. Recommendations without override entries count as "approved" (implicit approval).

| Raw rate | Score |
|----------|-------|
| < 30% | 0 |
| 50% | 25 |
| 70% | 50 |
| 85% | 75 |
| ≥ 95% | 100 |

**Data source:**
```sql
-- Total recommendations (from insight_log)
SELECT COUNT(*) AS total FROM insight_log
WHERE tenant_id = :tid AND review_status IN ('approved', 'rejected');

-- Rejections
SELECT COUNT(*) AS rejected FROM founder_overrides
WHERE tenant_id = :tid AND override_action = 'rejected';

-- Alignment = 1 - (rejected / total)
```

#### 5. Learning velocity (weight: 10%)

```
Raw metric: median days from experiment creation to winner declaration
```

Lower is better. Uses experiments with `status = 'winner_declared'` in the last 90 days.

| Median days | Score |
|-------------|-------|
| ≥ 60 | 0 |
| 45 | 25 |
| 30 | 50 |
| 21 | 75 |
| ≤ 14 | 100 |

**Inverse linear:** `max(0, min(100, (60 - median_days) / 46 * 100))`

**Data source:**
```sql
SELECT
  PERCENTILE_CONT(0.5) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (winner_declared_at - created_at)) / 86400
  ) AS median_days
FROM experiment_history
WHERE tenant_id = :tid AND status = 'winner_declared'
  AND winner_declared_at >= now() - interval '90 days';
```

#### 6. Retention quality (weight: 10%)

```
Raw metric: GTM-sourced customers retained at 60 days / total GTM-sourced customers
```

Only includes customers acquired through the growth system (has attribution chain).

| Raw rate | Score |
|----------|-------|
| < 50% | 0 |
| 60% | 25 |
| 70% | 50 |
| 80% | 75 |
| ≥ 90% | 100 |

**Linear interpolation** between breakpoints.

**Data source:** Requires external CRM integration. In Phase 1, this is manually entered via the Founder Dashboard or defaults to 50 (neutral) until data is available.

#### 7. Segment clarity (weight: 10%)

```
Raw metric: 1 - (re-segmentation events / total prospects) in 28-day window
```

"Re-segmentation" = a prospect's segment changed after initial assignment. Lower oscillation = higher clarity.

| Raw rate (clarity) | Score |
|--------------------|-------|
| < 70% | 0 |
| 80% | 25 |
| 85% | 50 |
| 90% | 75 |
| ≥ 95% | 100 |

**Data source:**
```sql
-- Prospects with segment changes
SELECT
  COUNT(DISTINCT prospect_id) FILTER (
    WHERE touchpoint_type = 'segment_reassigned'
  ) AS oscillated,
  COUNT(DISTINCT prospect_id) AS total
FROM touchpoint_log
WHERE tenant_id = :tid AND created_at >= now() - interval '28 days';
```

#### 8. Cost efficiency (weight: 10%)

```
Raw metric: cost-per-meeting trend (slope of last 4 weekly snapshots)
```

Score based on whether costs are trending down, flat, or up.

| Trend | Score |
|-------|-------|
| Rising > 20% | 0 |
| Rising 10-20% | 25 |
| Flat (±10%) | 50 |
| Declining 10-20% | 75 |
| Declining > 20% | 100 |

**Data source:**
```sql
-- Last 4 weeks of cost per meeting
SELECT
  DATE_TRUNC('week', created_at) AS week,
  AVG(total_cost_per_meeting) AS avg_cost
FROM cost_per_acquisition
WHERE tenant_id = :tid AND total_cost_per_meeting IS NOT NULL
  AND created_at >= now() - interval '28 days'
GROUP BY week
ORDER BY week;

-- Trend = (last_week - first_week) / first_week
```

#### 9. Belief depth (weight: 5%)

```
Raw metric: conversions with ≥ 2 belief shifts traced / total conversions
```

| Raw rate | Score |
|----------|-------|
| 0% | 0 |
| 10% | 25 |
| 20% | 50 |
| 30% | 75 |
| ≥ 40% | 100 |

**Data source:**
```sql
-- Prospects who converted with 2+ belief shifts
WITH converted AS (
  SELECT DISTINCT prospect_id
  FROM touchpoint_log
  WHERE tenant_id = :tid
    AND touchpoint_type IN ('meeting_booked', 'pilot_started')
    AND created_at >= now() - interval '28 days'
),
belief_counts AS (
  SELECT b.prospect_id, COUNT(*) AS shifts
  FROM belief_events b
  JOIN converted c ON b.prospect_id = c.prospect_id
  WHERE b.tenant_id = :tid AND b.belief_shift IN ('up', 'down')
  GROUP BY b.prospect_id
)
SELECT
  COUNT(*) FILTER (WHERE shifts >= 2) AS deep,
  (SELECT COUNT(*) FROM converted) AS total
FROM belief_counts;
```

### Cold start behavior

When a component has insufficient data (< 5 data points for rate-based metrics, < 2 experiments for velocity):

- **Score defaults to 50** (neutral — neither blocks nor promotes gate transition)
- **`cold_start: true`** flag is set in `component_scores` JSONB
- Dashboard displays cold-start components differently (grayed out with "insufficient data" label)
- Gate evaluation treats cold-start components as "not blocking" but "not contributing"

### Composite score computation

```python
WEIGHTS = {
    "booked_pilot_rate": 0.15,
    "attribution_completeness": 0.15,
    "proof_coverage": 0.15,
    "founder_alignment": 0.10,
    "learning_velocity": 0.10,
    "retention_quality": 0.10,
    "segment_clarity": 0.10,
    "cost_efficiency": 0.10,
    "belief_depth": 0.05,
}

def compute_wedge_fitness(component_scores: dict[str, float]) -> float:
    return sum(
        component_scores[name] * weight
        for name, weight in WEIGHTS.items()
    )
```

### Gate evaluation (reference — thresholds from design doc §11)

Gates are evaluated independently after computing the composite score. A gate passes only when ALL its conditions are met:

```python
def evaluate_gates(composite: float, components: dict, context: dict) -> dict:
    return {
        "automation_eligible": (  # Phase 1 → 2
            composite >= 40
            and components["attribution_completeness"] >= 60  # maps to raw ≥ 0.80
            and components["proof_coverage"] >= 50            # maps to raw ≥ 0.50
            and context["doctrine_stable_weeks"] >= 2
        ),
        "closed_loop_eligible": (  # Phase 2 → 3
            composite >= 60
            and components["belief_depth"] >= 100             # maps to raw ≥ 0.40 (design doc §11)
            and context["founder_override_rate"] < 0.4
        ),
        "expansion_eligible": (  # Phase 3 → 5
            composite >= 75
            and components["retention_quality"] >= 50         # maps to raw ≥ 0.70
            and context["pricing_experiment_completed"]
        ),
        "pricing_experiment_eligible": (
            composite >= 50
            and context["loss_records_count"] >= 30
            and context["price_loss_ratio"] >= 0.20
        ),
    }
```

### Persistence

Weekly computation persists to `wedge_fitness_snapshots` (schema 8.33 in the design doc, table 13 in `growth_memory_phase1`). The dedup key is `(tenant_id, wedge, snapshot_week)` where `snapshot_week` is the Monday of the reporting week (`DATE_TRUNC('week', now())::date`). Re-running the same week's computation upserts rather than creating a duplicate row. The `computed_at` column records actual execution time for observability but is not part of the uniqueness contract. The `component_scores` JSONB stores all 9 raw scores plus cold_start flags. The `gates_status` JSONB stores the 4 gate booleans. The `blocking_gaps` array lists human-readable reasons for any blocked gate.

### Computation schedule

Wedge Fitness is computed by the Growth Advisor batch job (Inngest cron, Monday 9am UTC). It can also be triggered on-demand via `GET /growth/metrics/wedge-fitness/:wedge_id` for the Founder Dashboard.

## Consequences

- All 9 components have explicit normalization functions — no implementer judgment needed
- Cold-start behavior prevents new wedges from being permanently blocked by empty tables
- Gate thresholds reference component scores (0-100) not raw metrics — avoids ambiguity about which scale the threshold applies to
- Trend-based metrics (cost efficiency) use 4-week linear regression, not point-in-time snapshots
- Retention quality defaults to neutral (50) until CRM integration provides real data
- Component weights sum to exactly 1.0 (verified: 0.15+0.15+0.15+0.10+0.10+0.10+0.10+0.10+0.05 = 1.00)

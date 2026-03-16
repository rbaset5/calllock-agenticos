# ADR 013: Fail-Closed and Duplicate-Delivery Regression Test Contract

Status: Proposed

## Context

The design doc specifies fail-closed behavior as a "hard architectural invariant" (Principle 5.10) and idempotency as a universal requirement (Principle 5.9, ADR 011). These are safety-critical properties: if either regresses, the system sends unauthorized messages or corrupts Growth Memory.

The design doc's 15 validation tests (§18) cover functional correctness but do not specify regression tests that run in CI to prevent these invariants from breaking during development. Droid needs a concrete test contract: what to test, what assertions to make, and where these tests live.

## Decision

### Test location and framework

All growth system regression tests live in `harness/tests/growth/` using pytest. They run against a test Supabase instance (not mocks — per project convention).

```
harness/tests/growth/
  test_fail_closed.py          # Outbound Health Gate fail-closed tests
  test_idempotency.py          # Duplicate-delivery dedup tests
  test_dlq.py                  # Dead-letter queue contract tests
  test_attribution_token.py    # Token validation tests (ADR 012)
  conftest.py                  # Shared fixtures: tenant setup, RLS context
```

### Fail-closed regression tests (`test_fail_closed.py`)

These tests verify Principle 5.10: "No message is ever sent without passing all gate checks."

```python
# Test 1: Gate unavailable → messages queue
async def test_gate_unavailable_queues_all_messages():
    """When the Health Gate service is unreachable, no messages are sent.
    Instead, all messages are queued for retry."""
    # Arrange: configure gate endpoint to return connection error
    # Act: submit 5 messages through the outbound pipeline
    # Assert:
    #   - 0 messages sent (send_count == 0)
    #   - 5 messages in retry queue
    #   - structured log emitted: gate_unavailable, count=5

# Test 2: Gate returns error → messages queue
async def test_gate_error_queues_messages():
    """When the Health Gate returns HTTP 500, messages queue (not send)."""
    # Arrange: configure gate to return 500
    # Act: submit message
    # Assert: 0 sent, 1 queued

# Test 3: Gate rejects message → message blocked, not queued
async def test_gate_rejection_blocks_message():
    """When gate explicitly rejects (compliance, reputation), message is blocked
    permanently (not retried)."""
    # Arrange: configure gate to return 403 with reason
    # Act: submit message
    # Assert: 0 sent, 0 queued, 1 blocked with reason logged

# Test 4: Gate timeout → messages queue
async def test_gate_timeout_queues_messages():
    """When gate does not respond within timeout, treat as unavailable."""
    # Arrange: configure gate with 10s delay, 2s timeout
    # Act: submit message
    # Assert: 0 sent, 1 queued

# Test 5: Gate passes → message sent
async def test_gate_pass_sends_message():
    """Baseline: when gate approves, message is sent."""
    # Arrange: configure gate to return 200/approved
    # Act: submit message
    # Assert: 1 sent, 0 queued

# Test 6: Partial gate failure in batch
async def test_partial_gate_failure_does_not_send_failed():
    """In a batch of 5 messages, if gate fails on message 3,
    messages 1-2 send, 3-5 queue. No message sends without gate approval."""
    # Arrange: gate passes first 2, errors on 3+
    # Act: submit 5 messages
    # Assert: 2 sent, 3 queued
```

**CI gate:** All 6 tests must pass. Any failure blocks merge.

### Duplicate-delivery regression tests (`test_idempotency.py`)

These tests verify ADR 011: database-level idempotency via UNIQUE constraints.

```python
# Test 1: Duplicate touchpoint → dedup hit, not error
async def test_duplicate_touchpoint_is_idempotent():
    """Submitting the same touchpoint_id twice results in one row,
    second attempt returns success (not error)."""
    # Arrange: create touchpoint event with fixed UUID
    # Act: submit twice
    # Assert:
    #   - 1 row in touchpoint_log
    #   - second call returned success (no exception)
    #   - structured log: dedup_hit, touchpoint_id=<uuid>

# Test 2: Duplicate belief inference → dedup hit
async def test_duplicate_belief_inference_is_idempotent():
    """Submitting belief inference for same source_touchpoint_id twice
    results in one row."""
    # Arrange: create belief event with fixed source_touchpoint_id
    # Act: submit twice
    # Assert: 1 row in belief_events, second call success

# Test 3: Duplicate experiment outcome → dedup hit
async def test_duplicate_experiment_outcome_is_idempotent():
    """Same experiment_id + arm_id + prospect_id → one row."""

# Test 4: Different touchpoint_id → two rows (not false dedup)
async def test_different_touchpoints_both_recorded():
    """Two events with different touchpoint_ids both persist.
    Ensures dedup logic doesn't over-filter."""
    # Act: submit two events with different UUIDs
    # Assert: 2 rows in touchpoint_log

# Test 5: Upsert tables increment version on update
async def test_segment_performance_upsert_increments_version():
    """segment_performance upserts on UNIQUE key and increments version."""
    # Arrange: insert segment_performance row (version=1)
    # Act: upsert with same UNIQUE key, different data
    # Assert: 1 row, version=2, data reflects update

# Test 6: Concurrent duplicate delivery
async def test_concurrent_duplicates_one_wins():
    """Two concurrent INSERTs with same touchpoint_id: one succeeds,
    one hits UNIQUE violation. Neither raises to caller."""
    # Arrange: create two concurrent tasks with same UUID
    # Act: run concurrently (asyncio.gather)
    # Assert: 1 row in touchpoint_log, no unhandled exceptions
```

### Dead-letter queue contract tests (`test_dlq.py`)

```python
# Test 1: Exhausted retries → DLQ entry
async def test_exhausted_retries_writes_to_dlq():
    """After max retries, event lands in growth_dead_letter_queue."""
    # Arrange: event handler that always raises
    # Act: simulate 3 retries + final failure
    # Assert: 1 row in growth_dead_letter_queue with correct fields

# Test 2: DLQ entry is tenant-scoped
async def test_dlq_entry_respects_rls():
    """DLQ entry for tenant A is not visible to tenant B."""
    # Arrange: write DLQ entry for tenant A
    # Act: query DLQ as tenant B
    # Assert: 0 rows returned

# Test 3: DLQ resolution lifecycle
async def test_dlq_resolution_updates_correctly():
    """Resolving a DLQ entry sets resolved_at, resolution, resolved_by."""
    # Arrange: create unresolved DLQ entry
    # Act: resolve as 'replayed'
    # Assert: resolved_at IS NOT NULL, resolution='replayed'

# Test 4: Unresolved count metric
async def test_dlq_unresolved_count():
    """COUNT(*) WHERE resolved_at IS NULL returns correct depth."""
    # Arrange: insert 3 unresolved, 2 resolved
    # Assert: unresolved count = 3
```

### Attribution token tests (`test_attribution_token.py`)

```python
# Test 1: Valid token round-trip
async def test_valid_token_creation_and_validation():
    """Create token → validate → get back original payload."""

# Test 2: Expired token rejected
async def test_expired_token_rejected():
    """Token with iat 91 days ago is rejected."""

# Test 3: Wrong tenant rejected
async def test_cross_tenant_token_rejected():
    """Token created for tenant A, validated against tenant B → rejected."""

# Test 4: Tampered payload rejected
async def test_tampered_payload_rejected():
    """Modify base64 payload after signing → signature mismatch."""

# Test 5: Key rotation — old key still validates
async def test_previous_key_validates_during_rotation():
    """Token signed with previous key validates after rotation."""

# Test 6: Key rotation — two-rotation-old key rejected
async def test_two_rotations_ago_key_rejected():
    """Token signed with key that's no longer current or previous → rejected."""
```

### CI integration

```yaml
# In CI pipeline (Render or GitHub Actions):
growth-regression:
  runs-on: ubuntu-latest
  services:
    supabase: # test instance
  steps:
    - run: pytest harness/tests/growth/ -x --tb=short
  # Blocking: merge requires all tests pass
```

**Test execution budget:** All growth regression tests must complete in < 30 seconds. Tests that exceed this budget must be optimized or moved to a nightly suite.

## Consequences

- Fail-closed behavior is verified by 6 tests covering every failure mode (unavailable, error, timeout, rejection, partial batch)
- Duplicate delivery is verified by 6 tests covering dedup, false-dedup, upsert versioning, and concurrency
- DLQ contract is verified by 4 tests covering write, RLS isolation, resolution, and metrics
- Attribution token validation is verified by 6 tests covering the full lifecycle (ADR 012)
- All tests run in CI — invariant regression blocks merge
- Test patterns follow ADR 011's handler model: catch UniqueViolation → log → return success
- Tests use real Supabase (not mocks) per project convention, ensuring constraint behavior matches production

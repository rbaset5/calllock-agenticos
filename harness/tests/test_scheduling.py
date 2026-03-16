from db.local_repository import create_tenant, create_tenant_config
from db.repository import create_audit_log, create_job
from harness.scheduling import (
    claim_due_tenants,
    due_tenants,
    finalize_scheduler_claim,
    heartbeat_scheduler_claim,
    list_scheduler_backlog_entries,
    override_scheduler_claim,
    reconcile_scheduler_backlog,
    sweep_stale_scheduler_claims,
)


def test_due_tenants_uses_local_schedule_buckets() -> None:
    due = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:00+00:00")

    assert len(due) == 1
    assert {entry["tenant_slug"] for entry in due} == {"tenant-alpha"}
    assert {entry["timezone"] for entry in due} == {"America/Detroit"}
    assert due[0]["scheduled_minute"] == 15
    assert due[0]["schedule_bucket"] == 1
    assert due[0]["lateness_minutes"] == 5


def test_scheduler_backlog_tracks_pending_and_completed_entries() -> None:
    reconcile_scheduler_backlog(job_type="retention", utc_iso="2026-01-15T08:20:00+00:00")
    pending = list_scheduler_backlog_entries(job_type="retention", status="pending")

    assert any(entry["tenant_slug"] == "tenant-alpha" for entry in pending)

    create_audit_log(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "action_type": "retention.run",
            "actor_id": "scheduler",
            "reason": "Run retention maintenance",
            "created_at": "2026-01-15T08:30:00+00:00",
        }
    )
    reconcile_scheduler_backlog(job_type="retention", utc_iso="2026-01-15T08:35:00+00:00")
    completed = list_scheduler_backlog_entries(job_type="retention", status="completed")

    alpha = next(entry for entry in completed if entry["tenant_slug"] == "tenant-alpha")
    assert alpha["completed_at"] == "2026-01-15T08:30:00+00:00"


def test_due_tenants_falls_back_to_utc_for_invalid_timezone() -> None:
    create_tenant({"id": "tenant-invalid-tz", "slug": "tenant-invalid-tz", "name": "Invalid TZ Tenant"})
    create_tenant_config(
        {
            "tenant_id": "tenant-invalid-tz",
            "slug": "tenant-invalid-tz",
            "timezone": "Mars/Olympus",
            "retention_local_hour": 8,
        }
    )

    due = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:00+00:00")
    invalid = next(entry for entry in due if entry["tenant_slug"] == "tenant-invalid-tz")

    assert invalid["configured_timezone"] == "Mars/Olympus"
    assert invalid["timezone"] == "UTC"
    assert invalid["local_hour"] == 8


def test_due_tenants_separates_tenants_within_same_local_hour() -> None:
    early = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:00+00:00")
    late = due_tenants(job_type="retention", utc_iso="2026-01-15T08:50:00+00:00")

    assert {entry["tenant_slug"] for entry in early} == {"tenant-alpha"}
    assert {entry["tenant_slug"] for entry in late} == {"tenant-alpha", "tenant-beta"}
    beta = next(entry for entry in late if entry["tenant_slug"] == "tenant-beta")
    assert beta["scheduled_minute"] == 45


def test_due_tenants_supports_catch_up_and_batch_limits() -> None:
    first_batch = due_tenants(job_type="retention", utc_iso="2026-01-15T08:50:00+00:00", max_tenants=1)

    assert [entry["tenant_slug"] for entry in first_batch] == ["tenant-alpha"]
    assert first_batch[0]["catch_up"] is True

    create_audit_log(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "action_type": "retention.run",
            "actor_id": "scheduler",
            "reason": "Run retention maintenance",
            "created_at": "2026-01-15T08:50:00+00:00",
        }
    )

    second_batch = due_tenants(job_type="retention", utc_iso="2026-01-15T08:55:00+00:00", max_tenants=1)

    assert [entry["tenant_slug"] for entry in second_batch] == ["tenant-beta"]


def test_claim_due_tenants_leases_backlog_entries() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
        claim_ttl_seconds=120,
    )

    assert len(claimed) == 1
    assert claimed[0]["status"] == "claimed"
    assert claimed[0]["claimed_by"] == "scheduler-test"

    after_claim = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:30+00:00")
    assert all(entry["tenant_slug"] != claimed[0]["tenant_slug"] for entry in after_claim)


def test_expired_claim_returns_to_pending_pool() -> None:
    claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
        claim_ttl_seconds=30,
    )

    after_expiry = due_tenants(job_type="retention", utc_iso="2026-01-15T08:21:00+00:00")

    assert any(entry["tenant_slug"] == "tenant-alpha" for entry in after_expiry)


def test_finalize_scheduler_claim_marks_completion() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
    )

    finalized = finalize_scheduler_claim(
        entry_id=claimed[0]["id"],
        action="complete",
        actor_id="scheduler-test",
        utc_iso="2026-01-15T08:22:00+00:00",
        note="completed test run",
    )

    assert finalized["status"] == "completed"
    assert finalized["completed_at"] == "2026-01-15T08:22:00+00:00"


def test_finalize_scheduler_claim_releases_back_to_pending() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
    )

    finalized = finalize_scheduler_claim(
        entry_id=claimed[0]["id"],
        action="release",
        actor_id="scheduler-test",
        utc_iso="2026-01-15T08:21:00+00:00",
        note="release test run",
    )

    assert finalized["status"] == "pending"
    assert finalized["claimed_by"] is None


def test_heartbeat_scheduler_claim_extends_lease() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
        claim_ttl_seconds=30,
    )

    heartbeat = heartbeat_scheduler_claim(
        entry_id=claimed[0]["id"],
        actor_id="scheduler-test",
        utc_iso="2026-01-15T08:20:20+00:00",
        claim_ttl_seconds=120,
    )

    assert heartbeat["claim_expires_at"] == "2026-01-15T08:22:20+00:00"

    after_original_expiry = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:40+00:00")
    assert all(entry["id"] != claimed[0]["id"] for entry in after_original_expiry)


def test_heartbeat_scheduler_claim_rejects_wrong_claimer() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
    )

    try:
        heartbeat_scheduler_claim(
            entry_id=claimed[0]["id"],
            actor_id="other-scheduler",
            utc_iso="2026-01-15T08:20:10+00:00",
        )
    except ValueError as exc:
        assert "claimed by" in str(exc)
    else:
        raise AssertionError("Expected wrong-claimer heartbeat to fail")


def test_sweep_stale_scheduler_claims_releases_expired_entries() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
        claim_ttl_seconds=30,
    )

    sweep = sweep_stale_scheduler_claims(utc_iso="2026-01-15T08:21:00+00:00")

    assert sweep["released_count"] == 1
    assert sweep["released"][0]["id"] == claimed[0]["id"]

    pending = list_scheduler_backlog_entries(status="pending")
    assert any(entry["id"] == claimed[0]["id"] for entry in pending)


def test_override_scheduler_claim_force_releases_active_claim() -> None:
    claimed = claim_due_tenants(
        job_type="retention",
        utc_iso="2026-01-15T08:20:00+00:00",
        max_tenants=1,
        claimer_id="scheduler-test",
    )

    overridden = override_scheduler_claim(
        entry_id=claimed[0]["id"],
        action="force_release",
        actor_id="operator-test",
        note="manual release",
    )

    assert overridden["status"] == "pending"
    assert overridden["claimed_by"] is None


def test_override_scheduler_claim_force_claims_pending_entry() -> None:
    due = due_tenants(job_type="retention", utc_iso="2026-01-15T08:20:00+00:00", max_tenants=1)

    overridden = override_scheduler_claim(
        entry_id=due[0]["id"],
        action="force_claim",
        actor_id="operator-test",
        new_claimer_id="operator-handoff",
        utc_iso="2026-01-15T08:20:10+00:00",
        claim_ttl_seconds=90,
        note="take over this claim",
    )

    assert overridden["status"] == "claimed"
    assert overridden["claimed_by"] == "operator-handoff"
    assert overridden["claim_expires_at"] == "2026-01-15T08:21:40+00:00"


def test_due_tenants_carries_over_missed_window_past_the_scheduled_hour() -> None:
    due = due_tenants(job_type="retention", utc_iso="2026-01-15T10:05:00+00:00", max_tenants=1)

    assert [entry["tenant_slug"] for entry in due] == ["tenant-alpha"]
    assert due[0]["catch_up"] is True
    assert due[0]["lateness_minutes"] > 60


def test_due_tenants_stops_carryover_after_lag_window() -> None:
    create_tenant({"id": "tenant-short-lag", "slug": "tenant-short-lag", "name": "Short Lag Tenant"})
    create_tenant_config(
        {
            "tenant_id": "tenant-short-lag",
            "slug": "tenant-short-lag",
            "timezone": "UTC",
            "retention_local_hour": 8,
            "max_schedule_lag_hours": 1,
        }
    )

    due = due_tenants(job_type="retention", utc_iso="2026-01-15T10:20:00+00:00")

    assert all(entry["tenant_slug"] != "tenant-short-lag" for entry in due)


def test_due_tenants_prioritizes_oldest_overdue_work() -> None:
    create_job(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-load-1",
            "job_type": "async_task",
            "status": "running",
            "idempotency_key": "load-job-1",
        }
    )

    due = due_tenants(job_type="tenant_eval", utc_iso="2026-01-15T09:55:00+00:00", max_tenants=1)

    assert [entry["tenant_slug"] for entry in due] == ["tenant-alpha"]
    assert due[0]["lateness_minutes"] > 10


def test_due_tenants_uses_load_as_tie_breaker() -> None:
    create_tenant({"id": "tenant-load-aa", "slug": "aa", "name": "Load AA"})
    create_tenant({"id": "tenant-load-cc", "slug": "cc", "name": "Load CC"})
    create_tenant_config(
        {
            "tenant_id": "tenant-load-aa",
            "slug": "aa",
            "timezone": "UTC",
            "tenant_eval_local_hour": 8,
            "max_active_jobs": 2,
        }
    )
    create_tenant_config(
        {
            "tenant_id": "tenant-load-cc",
            "slug": "cc",
            "timezone": "UTC",
            "tenant_eval_local_hour": 8,
            "max_active_jobs": 2,
        }
    )
    create_job(
        {
            "tenant_id": "tenant-load-aa",
            "origin_worker_id": "customer-analyst",
            "origin_run_id": "run-load-aa",
            "job_type": "async_task",
            "status": "running",
            "idempotency_key": "load-aa-1",
        }
    )

    due = due_tenants(job_type="tenant_eval", utc_iso="2026-01-15T08:35:00+00:00", max_tenants=1)

    assert [entry["tenant_slug"] for entry in due] == ["cc"]
    assert due[0]["capacity_remaining"] == 2


def test_due_tenants_skips_inactive_tenants() -> None:
    create_tenant(
        {
            "id": "tenant-paused",
            "slug": "tenant-paused",
            "name": "Paused Tenant",
            "status": "onboarding_failed",
        }
    )
    create_tenant_config(
        {
            "tenant_id": "tenant-paused",
            "slug": "tenant-paused",
            "timezone": "UTC",
            "tenant_eval_local_hour": 4,
        }
    )

    due = due_tenants(job_type="tenant_eval", utc_iso="2026-01-15T04:20:00+00:00")

    assert all(entry["tenant_slug"] != "tenant-paused" for entry in due)

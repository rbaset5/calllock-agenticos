from harness.jobs.dispatch import dispatch_job_requests


def test_job_dispatch_creates_idempotent_job() -> None:
    jobs = dispatch_job_requests(
        [{"idempotency_key": "job-1", "job_type": "follow_up", "payload": {"x": 1}}],
        tenant_id="tenant-alpha",
        origin_worker_id="customer-analyst",
        origin_run_id="run-1",
    )
    duplicate = dispatch_job_requests(
        [{"idempotency_key": "job-1", "job_type": "follow_up", "payload": {"x": 2}}],
        tenant_id="tenant-alpha",
        origin_worker_id="customer-analyst",
        origin_run_id="run-1",
    )
    assert jobs[0]["id"] == duplicate[0]["id"]

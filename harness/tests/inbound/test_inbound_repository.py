from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from db.local_repository import (
    _state,
    delete_expired_enrichment,
    get_email_account,
    get_emails_for_prospect,
    get_enabled_email_accounts,
    get_enrichment,
    get_inbound_draft,
    get_inbound_message,
    get_inbound_messages_by_thread,
    get_latest_stage,
    get_pending_review_drafts,
    get_pending_scoring_messages,
    get_poll_checkpoint,
    get_prospect_by_email,
    get_stage_history,
    get_tenant,
    get_tenants_with_email_accounts,
    insert_inbound_draft,
    insert_inbound_message,
    insert_prospect_email,
    insert_stage_transition,
    update_inbound_draft_gate,
    update_inbound_draft_status,
    update_inbound_message_prospect,
    update_inbound_message_scoring,
    update_inbound_message_stage,
    upsert_enrichment,
    upsert_poll_checkpoint,
)


def _tenant_id(slug: str = "tenant-alpha") -> str:
    return get_tenant(slug)["id"]


def _message_payload(*, tenant_id: str, rfc_message_id: str = "<msg-1@example.test>", received_at: str | None = None) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "account_id": "acct-1",
        "rfc_message_id": rfc_message_id,
        "thread_id": "thread-1",
        "imap_uid": 101,
        "from_addr": "owner@example.com",
        "from_domain": "example.com",
        "to_addr": "inbox@calllock.test",
        "subject": "Need help",
        "received_at": received_at or datetime.now(timezone.utc).isoformat(),
        "body_text": "We are missing calls after hours.",
        "quarantine_status": "clean",
        "quarantine_flags": [],
    }


def test_inbound_repository_empty_results() -> None:
    tenant_id = _tenant_id()

    assert get_inbound_message(tenant_id, "missing") is None
    assert get_inbound_messages_by_thread(tenant_id, "missing-thread") == []
    assert get_pending_scoring_messages(tenant_id) == []
    assert get_inbound_draft(tenant_id, "missing-message") is None
    assert get_pending_review_drafts(tenant_id) == []
    assert get_latest_stage(tenant_id, "missing-thread") is None
    assert get_stage_history(tenant_id, "missing-thread") == []
    assert get_poll_checkpoint(tenant_id, "acct-1", "INBOX") is None
    assert get_enrichment(tenant_id, "example.com", "sender_research") is None
    assert delete_expired_enrichment(tenant_id) == 0
    assert get_prospect_by_email(tenant_id, "missing@example.com") is None
    assert get_emails_for_prospect(tenant_id, "missing-prospect") == []
    assert get_enabled_email_accounts(tenant_id) == []
    assert get_email_account(tenant_id, "missing-account") is None
    assert get_tenants_with_email_accounts() == []


def test_inbound_message_crud_and_dedup(caplog) -> None:
    tenant_id = _tenant_id()
    older = datetime.now(timezone.utc) - timedelta(minutes=10)
    newer = older + timedelta(minutes=5)

    first = insert_inbound_message(
        _message_payload(tenant_id=tenant_id, rfc_message_id="<older@example.test>", received_at=older.isoformat())
    )
    second = insert_inbound_message(
        _message_payload(tenant_id=tenant_id, rfc_message_id="<newer@example.test>", received_at=newer.isoformat())
        | {"thread_id": "thread-1", "imap_uid": 102}
    )

    with caplog.at_level(logging.INFO, logger="db.local_repository"):
        duplicate = insert_inbound_message(_message_payload(tenant_id=tenant_id, rfc_message_id="<older@example.test>"))

    assert duplicate["id"] == first["id"]
    assert "dedup_hit" in caplog.text
    assert get_inbound_message(tenant_id, first["id"])["rfc_message_id"] == "<older@example.test>"
    assert [row["id"] for row in get_inbound_messages_by_thread(tenant_id, "thread-1")] == [first["id"], second["id"]]

    scored = update_inbound_message_scoring(
        tenant_id,
        first["id"],
        {
            "scoring_status": "scored",
            "action": "high",
            "total_score": 87,
            "score_dimensions": {"urgency": 40, "fit": 47},
            "score_reasoning": "Strong HVAC urgency.",
            "rubric_hash": "rubric-v1",
        },
    )
    promoted = update_inbound_message_prospect(tenant_id, first["id"], "prospect-1")
    staged = update_inbound_message_stage(tenant_id, first["id"], "qualified")

    assert scored["total_score"] == 87
    assert promoted["prospect_id"] == "prospect-1"
    assert staged["stage"] == "qualified"
    assert get_pending_scoring_messages(tenant_id) == [second]


def test_inbound_draft_crud_and_dedup() -> None:
    tenant_id = _tenant_id()
    message = insert_inbound_message(_message_payload(tenant_id=tenant_id))

    draft = insert_inbound_draft(
        {
            "tenant_id": tenant_id,
            "message_id": message["id"],
            "thread_id": message["thread_id"],
            "action": "high",
            "template_used": "reply-v1",
            "draft_text": "Can you share your current missed-call workflow?",
            "source": "llm",
        }
    )
    duplicate = insert_inbound_draft(
        {
            "tenant_id": tenant_id,
            "message_id": message["id"],
            "thread_id": message["thread_id"],
            "action": "high",
            "template_used": "reply-v2",
            "draft_text": "Ignored duplicate",
            "source": "fallback_template",
        }
    )

    assert duplicate["id"] == draft["id"]
    assert get_inbound_draft(tenant_id, message["id"])["id"] == draft["id"]
    assert get_pending_review_drafts(tenant_id) == [draft]

    gated = update_inbound_draft_gate(
        tenant_id,
        draft["id"],
        {"content_gate_status": "passed", "content_gate_flags": []},
    )
    sent = update_inbound_draft_status(tenant_id, draft["id"], "approved")

    assert gated["content_gate_status"] == "passed"
    assert sent["send_status"] == "approved"
    assert get_pending_review_drafts(tenant_id) == []


def test_stage_transitions_are_ordered_by_created_at() -> None:
    tenant_id = _tenant_id()
    message = insert_inbound_message(_message_payload(tenant_id=tenant_id))

    first = insert_stage_transition(
        {
            "tenant_id": tenant_id,
            "message_id": message["id"],
            "thread_id": message["thread_id"],
            "from_stage": None,
            "to_stage": "new",
            "changed_by": "inbound_pipeline",
            "reason": "initial assignment",
            "created_at": "2026-03-17T09:00:00+00:00",
        }
    )
    third = insert_stage_transition(
        {
            "tenant_id": tenant_id,
            "message_id": message["id"],
            "thread_id": message["thread_id"],
            "from_stage": "qualified",
            "to_stage": "engaged",
            "changed_by": "inbound_pipeline",
            "reason": "reply detected",
            "created_at": "2026-03-17T11:00:00+00:00",
        }
    )
    second = insert_stage_transition(
        {
            "tenant_id": tenant_id,
            "message_id": message["id"],
            "thread_id": message["thread_id"],
            "from_stage": "new",
            "to_stage": "qualified",
            "changed_by": "inbound_pipeline",
            "reason": "score threshold met",
            "created_at": "2026-03-17T10:00:00+00:00",
        }
    )

    history = get_stage_history(tenant_id, message["thread_id"])

    assert [row["id"] for row in history] == [first["id"], second["id"], third["id"]]
    assert get_latest_stage(tenant_id, message["thread_id"])["id"] == third["id"]


def test_poll_checkpoints_upsert_and_get() -> None:
    tenant_id = _tenant_id()

    checkpoint = upsert_poll_checkpoint(tenant_id, "acct-1", "INBOX", 42)
    updated = upsert_poll_checkpoint(tenant_id, "acct-1", "INBOX", 84, status="error", error="imap timeout")

    assert checkpoint["folder"] == "INBOX"
    assert updated["last_uid"] == 84
    assert updated["poll_status"] == "error"
    assert updated["last_error"] == "imap timeout"
    assert get_poll_checkpoint(tenant_id, "acct-1", "INBOX")["last_uid"] == 84


def test_enrichment_cache_ttl_and_cleanup() -> None:
    tenant_id = _tenant_id()
    now = datetime.now(timezone.utc)

    cached = upsert_enrichment(
        tenant_id,
        "example.com",
        "sender_research",
        "inbound_pipeline",
        {
            "prospect_id": None,
            "enrichment_data": {"company": "Example HVAC"},
            "enrichment_quality": "partial",
            "estimated_monthly_lost_revenue": 4200,
            "enriched_at": now.isoformat(),
        },
    )
    refreshed = upsert_enrichment(
        tenant_id,
        "example.com",
        "sender_research",
        "inbound_pipeline",
        {
            "enrichment_data": {"company": "Example HVAC", "reviews": 123},
            "enriched_at": now.isoformat(),
        },
    )
    upsert_enrichment(
        tenant_id,
        "old.example.com",
        "sender_research",
        "inbound_pipeline",
        {
            "enrichment_data": {"company": "Old HVAC"},
            "enriched_at": (now - timedelta(hours=400)).isoformat(),
        },
    )

    assert cached["id"] == refreshed["id"]
    assert get_enrichment(tenant_id, "example.com", "sender_research", ttl_hours=168)["enrichment_data"]["reviews"] == 123
    assert get_enrichment(tenant_id, "old.example.com", "sender_research", ttl_hours=168) is None
    assert delete_expired_enrichment(tenant_id, max_age_hours=336) == 1
    assert get_enrichment(tenant_id, "old.example.com", "sender_research", ttl_hours=999) is None


def test_prospect_email_insert_dedup_and_lookup() -> None:
    tenant_id = _tenant_id()

    first = insert_prospect_email(tenant_id, "prospect-1", "owner@example.com")
    duplicate = insert_prospect_email(tenant_id, "prospect-2", "owner@example.com", source="manual")
    second = insert_prospect_email(tenant_id, "prospect-1", "dispatch@example.com", source="inbound")

    assert duplicate["id"] == first["id"]
    assert get_prospect_by_email(tenant_id, "owner@example.com")["prospect_id"] == "prospect-1"
    assert [row["email"] for row in get_emails_for_prospect(tenant_id, "prospect-1")] == [
        "owner@example.com",
        "dispatch@example.com",
    ]
    assert second["source"] == "inbound"


def test_email_account_queries() -> None:
    tenant_alpha = _tenant_id("tenant-alpha")
    tenant_beta = _tenant_id("tenant-beta")

    _state()["email_accounts"].extend(
        [
            {
                "id": "acct-row-1",
                "tenant_id": tenant_alpha,
                "account_id": "alpha-primary",
                "imap_host": "imap.alpha.test",
                "imap_port": 993,
                "imap_username": "alpha",
                "imap_auth_type": "password",
                "imap_credential": "enc1",
                "folders": ["INBOX"],
                "enabled": True,
                "features": {"draft_generation": True},
                "created_at": "2026-03-17T09:00:00+00:00",
            },
            {
                "id": "acct-row-2",
                "tenant_id": tenant_alpha,
                "account_id": "alpha-disabled",
                "imap_host": "imap.alpha.test",
                "imap_port": 993,
                "imap_username": "alpha-disabled",
                "imap_auth_type": "password",
                "imap_credential": "enc2",
                "folders": ["INBOX"],
                "enabled": False,
                "features": {"draft_generation": False},
                "created_at": "2026-03-17T10:00:00+00:00",
            },
            {
                "id": "acct-row-3",
                "tenant_id": tenant_beta,
                "account_id": "beta-primary",
                "imap_host": "imap.beta.test",
                "imap_port": 993,
                "imap_username": "beta",
                "imap_auth_type": "oauth2",
                "imap_credential": "enc3",
                "folders": ["INBOX"],
                "enabled": True,
                "features": {"draft_generation": True},
                "created_at": "2026-03-17T11:00:00+00:00",
            },
        ]
    )

    enabled_alpha = get_enabled_email_accounts(tenant_alpha)

    assert [row["account_id"] for row in enabled_alpha] == ["alpha-primary"]
    assert get_email_account(tenant_alpha, "alpha-primary")["imap_host"] == "imap.alpha.test"
    assert get_tenants_with_email_accounts() == [tenant_alpha, tenant_beta]

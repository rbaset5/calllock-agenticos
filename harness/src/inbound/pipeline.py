from __future__ import annotations

import logging
from typing import Any, Iterable

from inbound.config import DEFAULT_CONFIG
from inbound.drafter import generate_draft
from inbound.escalation import build_escalation_payload, should_auto_archive, should_escalate
from inbound.imap_client import connect_imap, fetch_new_messages
from inbound.quarantine import run_full_quarantine
from inbound.researcher import research_sender
from inbound.scorer import score_message
from inbound.stage_tracker import assign_initial_stage, transition_stage
from inbound.types import ParsedMessage


logger = logging.getLogger(__name__)


def _effective_config(config: dict[str, Any] | None) -> dict[str, Any]:
    return config or DEFAULT_CONFIG


def _draft_send_status(action: str) -> str:
    if action == "medium":
        return "pending_review"
    return "approved"


def _reply_inferred_stage(action: str) -> str:
    if action in {"spam", "non-lead"}:
        return "archived"
    return "engaged"


async def process_message(
    msg: ParsedMessage,
    tenant_id: str,
    repository: Any,
    source: str = "organic",
    prospect_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_config = _effective_config(config)
    quarantine_result = run_full_quarantine(msg.body_html or msg.body_text)
    stored_message = repository.insert_inbound_message(
        {
            "tenant_id": tenant_id,
            "account_id": (prospect_context or {}).get("account_id", "unknown"),
            "rfc_message_id": msg.rfc_message_id,
            "thread_id": msg.thread_id,
            "imap_uid": msg.imap_uid,
            "from_addr": msg.from_addr,
            "from_domain": msg.from_domain,
            "to_addr": msg.to_addr,
            "subject": msg.subject,
            "received_at": msg.received_at.isoformat(),
            "body_text": quarantine_result.sanitized_text,
            "source": source,
            "quarantine_status": quarantine_result.status,
            "quarantine_flags": quarantine_result.flags,
            "quarantine_reason": quarantine_result.reason,
            "scoring_status": "pending" if quarantine_result.status == "clean" else "skipped",
        }
    )
    message_id = stored_message["id"]

    if quarantine_result.status == "blocked":
        logger.info("inbound_quarantine_blocked", extra={"tenant_id": tenant_id, "message_id": message_id})
        return {
            "message_id": message_id,
            "action": None,
            "total_score": None,
            "stage": stored_message.get("stage", "new"),
            "draft_generated": False,
            "escalated": False,
            "auto_archived": False,
        }

    sender_research: dict[str, Any] | None
    if source == "organic":
        sender_research = research_sender(msg.from_domain, tenant_id, repository)
    else:
        cached = repository.get_enrichment(
            tenant_id,
            msg.from_domain,
            "sender_research",
            ttl_hours=effective_config["research"]["cache_ttl_hours"],
        )
        sender_research = dict(cached.get("enrichment_data", {})) if cached else None

    scoring_result = await score_message(
        msg.from_addr,
        msg.subject,
        quarantine_result.sanitized_text,
        sender_research=sender_research,
        prospect_context=prospect_context,
        config=effective_config,
    )
    repository.update_inbound_message_scoring(
        tenant_id,
        message_id,
        {
            "scoring_status": "scored",
            "action": scoring_result.action,
            "total_score": scoring_result.total_score,
            "score_dimensions": scoring_result.dimensions,
            "score_reasoning": scoring_result.reasoning,
            "rubric_hash": scoring_result.rubric_hash,
        },
    )

    inferred_stage = assign_initial_stage(scoring_result.action)
    transition = None
    stage = inferred_stage
    if source == "reply":
        inferred_stage = _reply_inferred_stage(scoring_result.action)
        current_stage = (prospect_context or {}).get("current_stage")
        if current_stage is None:
            history = repository.get_stage_history(tenant_id, msg.thread_id)
            if history:
                current_stage = history[-1]["to_stage"]
        if current_stage:
            transition = transition_stage(str(current_stage), inferred_stage)
            stage = current_stage if transition is None else transition.to_stage
        else:
            stage = inferred_stage
            transition = {
                "from_stage": None,
                "to_stage": stage,
                "changed_by": "inbound_pipeline",
                "reason": "reply initial stage assignment",
            }
    else:
        transition = {
            "from_stage": None,
            "to_stage": stage,
            "changed_by": "inbound_pipeline",
            "reason": "initial stage assignment",
        }

    repository.update_inbound_message_stage(tenant_id, message_id, stage)
    if transition is not None:
        if isinstance(transition, dict):
            transition_payload = transition
        else:
            transition_payload = {
                "from_stage": transition.from_stage,
                "to_stage": transition.to_stage,
                "changed_by": transition.changed_by,
                "reason": transition.reason,
            }
        repository.insert_stage_transition(
            {
                "tenant_id": tenant_id,
                "message_id": message_id,
                "thread_id": msg.thread_id,
                **transition_payload,
            }
        )

    if prospect_context and prospect_context.get("prospect_id"):
        repository.update_inbound_message_prospect(tenant_id, message_id, prospect_context["prospect_id"])

    draft_generated = False
    if scoring_result.action in {"exceptional", "high", "medium"}:
        draft_result = await generate_draft(
            scoring_result.action,
            msg.from_addr,
            msg.subject,
            quarantine_result.sanitized_text,
            sender_research=sender_research,
            prospect_context=prospect_context,
            config=effective_config,
        )
        if draft_result.content_gate_status != "blocked" and draft_result.source not in {"skipped", "failed"}:
            draft = repository.insert_inbound_draft(
                {
                    "tenant_id": tenant_id,
                    "message_id": message_id,
                    "thread_id": msg.thread_id,
                    "action": scoring_result.action,
                    "template_used": draft_result.template_used,
                    "draft_text": draft_result.draft_text,
                    "source": draft_result.source,
                }
            )
            repository.update_inbound_draft_gate(
                tenant_id,
                draft["id"],
                {
                    "content_gate_status": draft_result.content_gate_status,
                    "content_gate_flags": draft_result.content_gate_flags,
                },
            )
            repository.update_inbound_draft_status(
                tenant_id,
                draft["id"],
                _draft_send_status(scoring_result.action),
            )
            draft_generated = True

    escalated = should_escalate(scoring_result.action, scoring_result.total_score)
    if escalated:
        build_escalation_payload(
            tenant_id,
            message_id,
            msg.from_addr,
            msg.subject,
            scoring_result.total_score,
            scoring_result.reasoning,
            scoring_result.action,
        )

    auto_archived = should_auto_archive(scoring_result.action)
    logger.info(
        "inbound_message_processed",
        extra={
            "tenant_id": tenant_id,
            "message_id": message_id,
            "action": scoring_result.action,
            "stage": stage,
        },
    )
    return {
        "message_id": message_id,
        "action": scoring_result.action,
        "total_score": scoring_result.total_score,
        "stage": stage,
        "draft_generated": draft_generated,
        "escalated": escalated,
        "auto_archived": auto_archived,
    }


async def run_poll(
    tenant_id: str,
    account_ids: Iterable[str],
    repository: Any,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    effective_config = _effective_config(config)
    polling_config = effective_config.get("polling", DEFAULT_CONFIG["polling"])
    results: list[dict[str, Any]] = []
    for account_id in account_ids:
        account = repository.get_email_account(tenant_id, account_id)
        if not account:
            logger.warning("inbound_poll_account_missing", extra={"tenant_id": tenant_id, "account_id": account_id})
            continue
        checkpoint = repository.get_poll_checkpoint(tenant_id, account_id, "INBOX")
        since_uid = int(checkpoint["last_uid"]) if checkpoint else 0
        client = connect_imap(
            account["imap_host"],
            int(account["imap_port"]),
            account["imap_username"],
            account["imap_credential"],
            auth_type=account.get("imap_auth_type", "password"),
        )
        messages = fetch_new_messages(
            client,
            "INBOX",
            since_uid,
            batch_size=int(polling_config.get("batch_size", 200)),
        )
        for message in messages:
            results.append(await process_message(message, tenant_id, repository, source="organic", config=effective_config))
        max_uid = max((message.imap_uid for message in messages), default=since_uid)
        repository.upsert_poll_checkpoint(tenant_id, account_id, "INBOX", max_uid)
    return results

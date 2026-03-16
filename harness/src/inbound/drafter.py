from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from inbound.config import DEFAULT_CONFIG
from inbound.content_gate import scan_draft
from inbound.types import DraftResult


SUPPORTED_ACTIONS = {"exceptional", "high", "medium"}
REPO_ROOT = Path(__file__).resolve().parents[3]
FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", flags=re.DOTALL)
VARIABLE_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


async def _call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> str:
    """Call the LLM and return the response text.

    # TODO(founder): Wire to harness LLM integration (LiteLLM or direct Anthropic client).
    # For now, raises NotImplementedError so tests can mock it.
    """
    raise NotImplementedError("LLM integration not yet wired — mock this in tests")


def _template_path(action: str) -> Path:
    return REPO_ROOT / "knowledge" / "inbound" / "templates" / f"{action}.md"


def _extract_fence(action: str, index: int) -> str | None:
    if action not in SUPPORTED_ACTIONS:
        return None
    path = _template_path(action)
    if not path.exists():
        return None
    matches = FENCE_RE.findall(path.read_text())
    if index >= len(matches):
        return None
    return matches[index].strip()


def _load_template(action: str) -> str | None:
    return _extract_fence(action, 0)


def _load_fallback_template(action: str) -> str | None:
    return _extract_fence(action, 1)


def fill_template_variables(template: str, variables: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return VARIABLE_RE.sub(_replace, template)


def _build_writer_prompt(
    action: str,
    from_addr: str,
    subject: str,
    body_text: str,
    sender_research: dict[str, Any] | None = None,
    prospect_context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    # TODO(founder): Replace this minimal writer prompt with the production founder voice prompt.
    system_prompt = (
        f"You write concise inbound email replies for action tier '{action}'. "
        "Return JSON with a single 'draft' field."
    )
    user_parts = [
        f"From: {from_addr}",
        f"Subject: {subject}",
        "Body:",
        body_text,
    ]
    if sender_research is not None:
        user_parts.extend(["", "Sender research:", json.dumps(sender_research, indent=2, sort_keys=True, default=str)])
    if prospect_context is not None:
        # TODO(founder): Expand prospect context shaping for reply-thread handling.
        user_parts.extend(["", "Prospect context:", json.dumps(prospect_context, indent=2, sort_keys=True, default=str)])
    return (system_prompt, "\n".join(user_parts))


def _build_reviewer_prompt(draft: str, action: str) -> tuple[str, str]:
    # TODO(founder): Replace this minimal reviewer prompt with the production style/safety reviewer.
    system_prompt = (
        f"You review inbound draft replies for action tier '{action}'. "
        "Return JSON with 'verdict' and optional 'revised_draft'."
    )
    user_prompt = f"Review this draft and revise only if needed:\n\n{draft}"
    return (system_prompt, user_prompt)


def _extract_json_blob(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and start < end:
        return raw[start : end + 1]
    return raw.strip()


def _parse_writer_response(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_extract_json_blob(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid writer JSON response") from exc
    if not isinstance(parsed, dict) or "draft" not in parsed:
        raise ValueError("Writer response must include 'draft'")
    return parsed


def _parse_reviewer_response(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_extract_json_blob(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid reviewer JSON response") from exc
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        raise ValueError("Reviewer response must include 'verdict'")
    return parsed


def _default_variables(from_addr: str, subject: str, body_text: str, sender_research: dict[str, Any] | None) -> dict[str, str]:
    local_part = from_addr.split("@", 1)[0] if "@" in from_addr else from_addr
    first_name = local_part.replace(".", " ").replace("_", " ").split()[0].title() if local_part else "there"
    industry = ", ".join((sender_research or {}).get("industry_signals", [])) or "HVAC shops"
    subject_keywords = subject or "your message"
    pain_point = body_text.splitlines()[0].strip() if body_text.strip() else "Losing calls is losing revenue"
    return {
        "original_subject": subject,
        "first_name": first_name or "there",
        "pain_point_mirror": pain_point,
        "proof_point": "One shop went from ~15 missed calls/week to zero in the first month",
        "booking_link": "Reply to this email and I'll send you a link",
        "phone": "",
        "subject_keywords": subject_keywords,
        "pain_point_acknowledgment": pain_point,
        "timing_context": "during busy season",
        "context_acknowledgment": "Sounds like you're exploring call handling options",
        "industry_context": f"For {industry}, the biggest win is usually capturing after-hours calls.",
    }


def _fallback_result(action: str, variables: dict[str, str]) -> DraftResult:
    template = _load_fallback_template(action)
    if template is None:
        return DraftResult(
            draft_text="",
            template_used=action,
            source="failed",
            content_gate_status="skipped",
            content_gate_flags=[],
        )
    draft_text = fill_template_variables(template, variables)
    gate_status, gate_flags = scan_draft(draft_text)
    return DraftResult(
        draft_text=draft_text,
        template_used=action,
        source="fallback_template",
        content_gate_status=gate_status,
        content_gate_flags=gate_flags,
    )


async def generate_draft(
    action: str,
    from_addr: str,
    subject: str,
    body_text: str,
    sender_research: dict[str, Any] | None = None,
    prospect_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> DraftResult:
    if action not in SUPPORTED_ACTIONS:
        return DraftResult(
            draft_text="",
            template_used=action,
            source="skipped",
            content_gate_status="skipped",
            content_gate_flags=[],
        )

    effective_config = config or DEFAULT_CONFIG
    drafting_config = effective_config.get("drafting", DEFAULT_CONFIG["drafting"])
    variables = _default_variables(from_addr, subject, body_text, sender_research)

    try:
        writer_system, writer_user = _build_writer_prompt(
            action,
            from_addr,
            subject,
            body_text,
            sender_research=sender_research,
            prospect_context=prospect_context,
        )
        writer_raw = await _call_llm(
            drafting_config["writer_model"],
            writer_system,
            writer_user,
            max_tokens=drafting_config.get("max_tokens", 2048),
            temperature=0.1,
        )
        writer_payload = _parse_writer_response(writer_raw)
        draft_text = str(writer_payload["draft"])
        gate_status, gate_flags = scan_draft(draft_text)
        if gate_status == "blocked":
            return DraftResult(
                draft_text=draft_text,
                template_used=action,
                source="llm",
                content_gate_status=gate_status,
                content_gate_flags=gate_flags,
            )

        reviewer_system, reviewer_user = _build_reviewer_prompt(draft_text, action)
        reviewer_raw = await _call_llm(
            drafting_config["reviewer_model"],
            reviewer_system,
            reviewer_user,
            max_tokens=drafting_config.get("max_tokens", 2048),
            temperature=0.1,
        )
        reviewer_payload = _parse_reviewer_response(reviewer_raw)
        if reviewer_payload.get("verdict") == "revise" and reviewer_payload.get("revised_draft"):
            draft_text = str(reviewer_payload["revised_draft"])
        gate_status, gate_flags = scan_draft(draft_text)
        return DraftResult(
            draft_text=draft_text,
            template_used=action,
            source="llm",
            content_gate_status=gate_status,
            content_gate_flags=gate_flags,
        )
    except Exception:
        return _fallback_result(action, variables)

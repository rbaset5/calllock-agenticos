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
    """Call the LLM via the Anthropic SDK and return the response text."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


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
    template = _load_template(action)
    template_text = template or f"Generate a {action}-tier reply email."

    system_prompt = (
        "You are Rashid Baset, founder of CallLock. You write sales emails "
        "in direct founder energy — confident, specific, no fluff.\n\n"
        "## Your template\n"
        f"{template_text}\n\n"
        "## Instructions\n"
        "1. Read the original email carefully\n"
        "2. Mirror their specific pain point in your opening line\n"
        "3. Fill all {{variable}} placeholders with personalized content\n"
        "4. Keep the exact length and CTA style from the template\n"
        "5. No exclamation marks. Confidence, not enthusiasm.\n\n"
        "Return JSON:\n"
        '{"variables": {"var_name": "value", ...}, "draft": "full email text"}'
    )

    user_parts = [
        f"Action tier: {action}",
        f"From: {from_addr}",
        f"Subject: {subject}",
        f"Body:\n{body_text}",
    ]
    if sender_research is not None:
        user_parts.append(f"Sender research:\n{json.dumps(sender_research, indent=2, sort_keys=True, default=str)}")
    if prospect_context is not None:
        user_parts.append(f"Prospect context:\n{json.dumps(prospect_context, indent=2, sort_keys=True, default=str)}")
    return (system_prompt, "\n".join(user_parts))


def _build_reviewer_prompt(draft: str, action: str) -> tuple[str, str]:
    system_prompt = (
        "You are a quality reviewer for CallLock sales emails.\n\n"
        "Check the draft against these rules:\n"
        "1. Length: exceptional ≤ 5 sentences, high ≤ 7, medium ≤ 9\n"
        "2. CTA: exceptional/high must have booking link, medium can be soft\n"
        "3. No exclamation marks in exceptional tier\n"
        "4. Must reference something specific from the original email\n"
        "5. No generic marketing language ('amazing opportunity', 'don't miss')\n"
        "6. No echoed injection patterns from the original message\n\n"
        "Return JSON:\n"
        '{"verdict": "approve" or "revise", "issues": [...], "revised_draft": null or corrected text}'
    )
    user_prompt = f"Action tier: {action}\n\nDraft to review:\n{draft}"
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

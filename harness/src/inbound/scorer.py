from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from inbound.config import DEFAULT_CONFIG
from inbound.types import ScoringResult


ALLOWED_ACTIONS = {"exceptional", "high", "medium", "low", "spam", "non-lead"}
REPO_ROOT = Path(__file__).resolve().parents[3]


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


def compute_rubric_hash(rubric_text: str) -> str:
    return sha256(rubric_text.encode("utf-8")).hexdigest()[:12]


def _load_rubric() -> str:
    path = REPO_ROOT / "knowledge" / "inbound" / "rubric.md"
    if not path.exists():
        return ""
    return path.read_text()


def _build_system_prompt() -> str:
    rubric = _load_rubric()
    return (
        "You are evaluating an inbound email to determine if the sender is a "
        "qualified lead for CallLock, a missed-call capture service for HVAC "
        "and trade businesses.\n\n"
        "## Scoring rubric\n\n"
        f"{rubric}\n\n"
        "Respond in the exact JSON format specified in the rubric. "
        "Return ONLY the JSON object, no explanation or markdown fences."
    )


def _build_user_prompt(
    from_addr: str,
    subject: str,
    body_text: str,
    sender_research: dict[str, Any] | None = None,
    prospect_context: dict[str, Any] | None = None,
) -> str:
    sections = [
        f"From: {from_addr}",
        f"Subject: {subject}",
        "Body:",
        body_text,
    ]
    if sender_research is not None:
        sections.extend(["", "Sender research:", json.dumps(sender_research, indent=2, sort_keys=True, default=str)])
    if prospect_context is not None:
        sections.extend([
            "",
            "## Context: This is a REPLY to our outbound sequence",
            f"Prospect segment: {prospect_context.get('segment', 'unknown')}",
            f"Sequence position: email {prospect_context.get('sequence_position', '?')} of {prospect_context.get('sequence_length', '?')}",
            f"Current stage: {prospect_context.get('current_stage', 'unknown')}",
        ])
        if prospect_context.get("experiment_arm"):
            sections.append(f"Experiment arm: {prospect_context['experiment_arm']}")
        sections.extend(["", "Full prospect data:", json.dumps(prospect_context, indent=2, sort_keys=True, default=str)])
    return "\n".join(sections)


def _extract_json_blob(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and start < end:
        return raw[start : end + 1]
    return raw.strip()


def parse_score_response(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_extract_json_blob(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid scorer JSON response") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Scorer response must be a JSON object")

    for key in ("dimensions", "total_score", "action"):
        if key not in parsed:
            raise ValueError(f"Missing required scorer field: {key}")
    if not isinstance(parsed["dimensions"], dict):
        raise ValueError("dimensions must be an object")
    if parsed["action"] not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid scoring action: {parsed['action']}")
    score = parsed["total_score"]
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        raise ValueError("total_score must be between 0 and 100")

    parsed.setdefault("bonuses", [])
    parsed.setdefault("disqualifier", None)
    parsed.setdefault("reasoning", "")
    parsed["total_score"] = int(score)
    return parsed


async def score_message(
    from_addr: str,
    subject: str,
    body_text: str,
    sender_research: dict[str, Any] | None = None,
    prospect_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> ScoringResult:
    effective_config = config or DEFAULT_CONFIG
    scoring_config = effective_config.get("scoring", DEFAULT_CONFIG["scoring"])
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(
        from_addr,
        subject,
        body_text,
        sender_research=sender_research,
        prospect_context=prospect_context,
    )
    raw = await _call_llm(
        scoring_config["model"],
        system_prompt,
        user_prompt,
        max_tokens=scoring_config.get("max_tokens", 1024),
        temperature=scoring_config.get("temperature", 0.1),
    )
    parsed = parse_score_response(raw)
    rubric_hash = compute_rubric_hash(_load_rubric())
    return ScoringResult(
        action=str(parsed["action"]),
        total_score=int(parsed["total_score"]),
        dimensions=dict(parsed["dimensions"]),
        bonuses=list(parsed.get("bonuses", [])),
        disqualifier=parsed.get("disqualifier"),
        reasoning=str(parsed.get("reasoning", "")),
        rubric_hash=rubric_hash,
    )

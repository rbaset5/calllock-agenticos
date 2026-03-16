from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from inbound.scorer import (
    _build_user_prompt,
    compute_rubric_hash,
    parse_score_response,
    score_message,
)


def test_compute_rubric_hash() -> None:
    assert compute_rubric_hash("rubric") == compute_rubric_hash("rubric")
    assert compute_rubric_hash("rubric") != compute_rubric_hash("rubric v2")


def test_build_user_prompt_organic() -> None:
    prompt = _build_user_prompt("owner@example.com", "Need help", "Missed calls are hurting us", sender_research={"domain": "example.com"})

    assert "Prospect context:" not in prompt
    assert "Sender research:" in prompt
    assert "owner@example.com" in prompt


def test_build_user_prompt_reply() -> None:
    prompt = _build_user_prompt(
        "owner@example.com",
        "Re: Need help",
        "Following up",
        prospect_context={"prospect_id": "prospect-1", "current_stage": "qualified"},
    )

    assert "Prospect context:" in prompt
    assert "prospect-1" in prompt


def test_parse_score_response_valid() -> None:
    parsed = parse_score_response(
        '{"dimensions":{"intent_signal":90},"bonuses":[],"disqualifier":null,"total_score":91,"action":"exceptional","reasoning":"Strong fit."}'
    )

    assert parsed["action"] == "exceptional"
    assert parsed["total_score"] == 91


def test_parse_score_response_with_code_fences() -> None:
    parsed = parse_score_response(
        '```json\n{"dimensions":{"intent_signal":70},"total_score":70,"action":"high","reasoning":"ok"}\n```'
    )

    assert parsed["action"] == "high"


def test_parse_score_response_missing_keys() -> None:
    with pytest.raises(ValueError):
        parse_score_response('{"total_score":70,"action":"high"}')


def test_parse_score_response_invalid_action() -> None:
    with pytest.raises(ValueError):
        parse_score_response('{"dimensions":{},"total_score":70,"action":"urgent"}')


def test_parse_score_response_score_out_of_range() -> None:
    with pytest.raises(ValueError):
        parse_score_response('{"dimensions":{},"total_score":120,"action":"high"}')


@pytest.mark.asyncio
async def test_score_message_happy_path() -> None:
    raw = '{"dimensions":{"intent_signal":90},"bonuses":[{"signal":"referral","points":15}],"disqualifier":null,"total_score":95,"action":"exceptional","reasoning":"Strong fit."}'
    with patch("inbound.scorer._call_llm", new=AsyncMock(return_value=raw)):
        result = await score_message("owner@example.com", "Need help", "We miss calls after hours")

    assert result.action == "exceptional"
    assert result.total_score == 95
    assert result.bonuses == [{"signal": "referral", "points": 15}]
    assert len(result.rubric_hash) == 12


@pytest.mark.asyncio
async def test_score_message_parse_failure() -> None:
    with patch("inbound.scorer._call_llm", new=AsyncMock(return_value="not json")):
        with pytest.raises(ValueError):
            await score_message("owner@example.com", "Need help", "bad payload")

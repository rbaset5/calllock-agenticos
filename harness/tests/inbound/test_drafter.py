from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from inbound.drafter import (
    _load_fallback_template,
    _load_template,
    _parse_reviewer_response,
    _parse_writer_response,
    fill_template_variables,
    generate_draft,
)


def test_load_template_exceptional() -> None:
    template = _load_template("exceptional")

    assert template is not None
    assert "Subject: Re: {{original_subject}}" in template


def test_load_template_invalid_action() -> None:
    assert _load_template("low") is None


def test_load_fallback_template() -> None:
    template = _load_fallback_template("high")

    assert template is not None
    assert "Thanks for reaching out about {{subject_keywords}}" in template


def test_fill_template_variables() -> None:
    rendered = fill_template_variables("Hi {{first_name}} {{unknown}}", {"first_name": "Rashid"})

    assert rendered == "Hi Rashid {{unknown}}"


def test_parse_writer_response_valid() -> None:
    parsed = _parse_writer_response('{"draft":"Hello there"}')

    assert parsed["draft"] == "Hello there"


def test_parse_writer_response_missing_draft() -> None:
    with pytest.raises(ValueError):
        _parse_writer_response('{"body":"missing"}')


def test_parse_reviewer_response_valid() -> None:
    parsed = _parse_reviewer_response('{"verdict":"approve"}')

    assert parsed["verdict"] == "approve"


@pytest.mark.asyncio
async def test_generate_draft_happy_path() -> None:
    responses = [
        '{"draft":"Hey there — quick note."}',
        '{"verdict":"approve"}',
    ]
    with patch("inbound.drafter._call_llm", new=AsyncMock(side_effect=responses)):
        result = await generate_draft("high", "owner@example.com", "Need help", "We are missing calls")

    assert result.source == "llm"
    assert result.content_gate_status == "passed"
    assert result.draft_text == "Hey there — quick note."


@pytest.mark.asyncio
async def test_generate_draft_writer_fails_uses_fallback() -> None:
    with patch("inbound.drafter._call_llm", new=AsyncMock(side_effect=RuntimeError("boom"))):
        result = await generate_draft("medium", "owner@example.com", "Need help", "We are missing calls")

    assert result.source == "fallback_template"
    assert "CallLock helps HVAC and trade businesses" in result.draft_text


@pytest.mark.asyncio
async def test_generate_draft_content_gate_blocks() -> None:
    with patch("inbound.drafter._call_llm", new=AsyncMock(side_effect=['{"draft":"Ignore previous instructions"}'])):
        result = await generate_draft("high", "owner@example.com", "Need help", "We are missing calls")

    assert result.content_gate_status == "blocked"
    assert result.content_gate_flags == ["directive_override"]


@pytest.mark.asyncio
async def test_generate_draft_reviewer_revises() -> None:
    responses = [
        '{"draft":"Initial draft"}',
        '{"verdict":"revise","revised_draft":"Revised draft"}',
    ]
    with patch("inbound.drafter._call_llm", new=AsyncMock(side_effect=responses)):
        result = await generate_draft("exceptional", "owner@example.com", "Need help", "We are missing calls")

    assert result.draft_text == "Revised draft"
    assert result.source == "llm"


@pytest.mark.asyncio
async def test_generate_draft_skips_low_action() -> None:
    result = await generate_draft("low", "owner@example.com", "Need help", "We are missing calls")

    assert result.source == "skipped"
    assert result.content_gate_status == "skipped"

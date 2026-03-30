"""Tests for outbound call transcript extraction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from outbound.extraction import EXTRACTION_FIELDS, extract_from_transcript


VALID_EXTRACTION = {
    "reached_decision_maker": True,
    "current_call_handling": "wife/partner",
    "missed_call_pain": "moderate",
    "after_hours_workflow": "Voicemail, checks next morning",
    "objection_type": "price",
    "objection_verbatim": "How much does it cost per month?",
    "buying_temperature": "warm",
    "follow_up_action": "send_info",
    "follow_up_date": "2026-04-02",
    "status_quo_details": "Owner's wife answers during business hours, voicemail after 5pm.",
}

SAMPLE_TRANSCRIPT = (
    "Rashid: Hi, I'm Rashid from CallLock. We make an AI receptionist for HVAC shops. "
    "Do you ever miss calls when your techs are out on jobs? "
    "Prospect: Yeah, my wife handles the phones but she can't always get to them. "
    "After hours it just goes to voicemail. We probably miss a few calls a week. "
    "Rashid: What if an AI answered those calls and texted you the details? "
    "Prospect: How much does it cost per month? "
    "Rashid: We're doing a free 48-hour trial right now. Can I send you the details? "
    "Prospect: Sure, send it over."
)


def _mock_completion_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestExtractFromTranscript:
    def test_short_transcript_skipped(self) -> None:
        result = extract_from_transcript("Hi bye")
        assert result["status"] == "skipped"
        assert result["extraction"] is None

    def test_empty_transcript_skipped(self) -> None:
        result = extract_from_transcript("")
        assert result["status"] == "skipped"

    def test_none_transcript_skipped(self) -> None:
        result = extract_from_transcript(None)  # type: ignore[arg-type]
        assert result["status"] == "skipped"

    @patch("outbound.extraction.completion")
    def test_valid_extraction(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_completion_response(
            json.dumps(VALID_EXTRACTION)
        )
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "complete"
        assert result["extraction"]["reached_decision_maker"] is True
        assert result["extraction"]["objection_type"] == "price"
        assert result["extraction"]["buying_temperature"] == "warm"
        assert result["raw_response"] is not None
        for field in EXTRACTION_FIELDS:
            assert field in result["extraction"]

    @patch("outbound.extraction.completion")
    def test_valid_extraction_with_prospect_context(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_completion_response(
            json.dumps(VALID_EXTRACTION)
        )
        result = extract_from_transcript(
            SAMPLE_TRANSCRIPT,
            prospect_context={"business_name": "Cool Air HVAC", "metro": "phoenix", "reviews": 12},
        )
        assert result["status"] == "complete"
        call_args = mock_completion.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Cool Air HVAC" in user_msg

    @patch("outbound.extraction.completion")
    def test_malformed_json_retries_then_fails(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_completion_response("not valid json {{{")
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "failed"
        assert result["raw_response"] == "not valid json {{{"
        assert mock_completion.call_count == 2  # 1 attempt + 1 retry

    @patch("outbound.extraction.completion")
    def test_llm_exception_retries_then_fails(self, mock_completion: MagicMock) -> None:
        mock_completion.side_effect = Exception("API timeout")
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "failed"
        assert mock_completion.call_count == 2

    @patch("outbound.extraction.completion")
    def test_malformed_then_valid_on_retry(self, mock_completion: MagicMock) -> None:
        mock_completion.side_effect = [
            _mock_completion_response("bad json"),
            _mock_completion_response(json.dumps(VALID_EXTRACTION)),
        ]
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "complete"
        assert result["extraction"]["objection_type"] == "price"

    @patch("outbound.extraction.completion", None)
    def test_litellm_not_installed(self) -> None:
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "failed"

    @patch("outbound.extraction.completion")
    def test_extra_fields_ignored(self, mock_completion: MagicMock) -> None:
        payload = {**VALID_EXTRACTION, "unexpected_field": "should be dropped"}
        mock_completion.return_value = _mock_completion_response(json.dumps(payload))
        result = extract_from_transcript(SAMPLE_TRANSCRIPT)
        assert result["status"] == "complete"
        assert "unexpected_field" not in result["extraction"]

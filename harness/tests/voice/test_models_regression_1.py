"""Regression tests for Retell webhook model behavior found by QA."""

from __future__ import annotations

import logging

from voice.models import RetellToolCallRequest


def test_nested_retell_tool_payload_does_not_warn_for_wrapper_fields(caplog) -> None:
    # Regression: ISSUE-002 - normal Retell tool wrapper fields produced warning log noise.
    # Found by /qa on 2026-06-18.
    # Report: .gstack/qa-reports/qa-report-localhost-2026-06-18.md
    with caplog.at_level(logging.WARNING):
        request = RetellToolCallRequest.model_validate(
            {
                "name": "lookup_caller",
                "args": {"phone_number": "+15125550101"},
                "call": {
                    "call_id": "ret-call-wrapper-001",
                    "metadata": {"tenant_id": "tenant-ace-001"},
                    "from_number": "+15125550101",
                    "to_number": "+13126463816",
                },
            }
        )

    assert request.call_id == "ret-call-wrapper-001"
    assert request.tool_name == "lookup_caller"
    assert request.from_number == "+15125550101"
    assert request.to_number == "+13126463816"
    assert "received unexpected fields" not in caplog.text

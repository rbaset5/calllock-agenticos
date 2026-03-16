"""Tests for post-call transcript extraction helpers."""

from __future__ import annotations

import pytest

from voice.extraction.post_call import (
    extract_address_from_transcript,
    extract_customer_name,
    extract_problem_duration,
    extract_safety_emergency,
    map_disconnection_reason,
    map_urgency_level_from_analysis,
)


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Agent: How can I help?\nUser: My name is Jonas, I have an AC problem.", "Jonas"),
        ("Agent: What's your name?\nUser: I'm Sarah Johnson.", "Sarah Johnson"),
        ("Agent: Who am I speaking with?\nUser: This is Mike Rivera.", "Mike Rivera"),
        ("Agent: Hello?\nUser: My AC is broken.", None),
        (None, None),
        ("", None),
        ("Agent: Hi, this is Maria from CallLock.\nUser: Yeah, my furnace is not working.", None),
    ],
    ids=[
        "my-name-is",
        "im-prefix",
        "this-is-prefix",
        "no-name",
        "undefined-transcript",
        "empty-transcript",
        "ignore-agent-introduction",
    ],
)
def test_extract_customer_name(transcript: str | None, expected: str | None) -> None:
    assert extract_customer_name(transcript) == expected


def test_extract_customer_name_does_not_capture_agent_name() -> None:
    transcript = "Agent: Thanks for calling, this is Alex from ACE Cooling.\nUser: Hi, I need help."
    assert extract_customer_name(transcript) != "Alex"
    assert extract_customer_name(transcript) is None


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("I smell gas in my house", True),
        ("carbon monoxide detector is going off", True),
        ("sparking from the furnace unit", True),
        ("there is smoke from the furnace", True),
        ("my AC is making a noise", False),
        (None, False),
        ("", False),
    ],
)
def test_extract_safety_emergency(transcript: str | None, expected: bool) -> None:
    assert extract_safety_emergency(transcript) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("emergency", "Emergency"),
        ("Urgent", "Urgent"),
        ("routine", "Routine"),
        ("estimate", "Estimate"),
        ("unknown", None),
        (None, None),
    ],
)
def test_map_urgency_level_from_analysis(value: str | None, expected: str | None) -> None:
    assert map_urgency_level_from_analysis(value) == expected


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("user_hangup", "customer_hangup"),
        ("voicemail", "callback_later"),
        ("agent_hangup", None),
        (None, None),
    ],
)
def test_map_disconnection_reason(reason: str | None, expected: str | None) -> None:
    assert map_disconnection_reason(reason) == expected


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("I live at 1234 Oak Street, Austin, TX 78701", "1234 Oak Street"),
        ("my AC is broken", None),
        (None, None),
    ],
)
def test_extract_address_from_transcript(transcript: str | None, expected: str | None) -> None:
    result = extract_address_from_transcript(transcript)
    if expected is None:
        assert result is None
    else:
        assert expected in result


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Agent: How can I help?\nUser: Yeah my AC stopped working this morning.", {"raw": "this morning", "category": "acute"}),
        ("Agent: What happened?\nUser: It just stopped working today.", {"raw": "today", "category": "acute"}),
        ("Agent: Tell me more.\nUser: The noise just started about an hour ago.", {"raw": "just started", "category": "acute"}),
        ("Agent: How long?\nUser: It has been making that sound for a few hours.", {"raw": "a few hours", "category": "acute"}),
        ("Agent: When did it start?\nUser: The heater stopped tonight.", {"raw": "tonight", "category": "acute"}),
        ("Agent: What is going on?\nUser: Started acting up yesterday.", {"raw": "yesterday", "category": "recent"}),
        ("Agent: How long?\nUser: It has been about 2 days now.", {"raw": "about 2 days now", "category": "recent"}),
        ("Agent: When did this start?\nUser: Since Monday it has been leaking.", {"raw": "Since Monday", "category": "recent"}),
        ("Agent: How long?\nUser: A few days now, maybe three or four.", {"raw": "A few days now", "category": "recent"}),
        ("Agent: Tell me more.\nUser: It started doing this earlier this week.", {"raw": "earlier this week", "category": "recent"}),
        ("Agent: How long?\nUser: Been going on a couple weeks now.", {"raw": "a couple weeks now", "category": "ongoing"}),
        ("Agent: When did you notice?\nUser: About a month ago it started.", {"raw": "About a month ago", "category": "ongoing"}),
        ("Agent: Tell me more.\nUser: This has been a problem for years honestly.", {"raw": "for years", "category": "ongoing"}),
        ("Agent: How long has this been happening?\nUser: It has been going on for a while now.", {"raw": "for a while", "category": "ongoing"}),
        ("Agent: When?\nUser: This has been happening for some time.", {"raw": "for some time", "category": "ongoing"}),
        ("Agent: How can I help?\nUser: My AC is not working.", None),
        (None, None),
        ("", None),
        ("Agent: How long has this been going on since this morning?\nUser: My AC is broken.", None),
        ("Agent: How long has this been happening?\nUser: Since yesterday the unit has been making noise.", {"raw": "yesterday", "category": "recent"}),
    ],
)
def test_extract_problem_duration(
    transcript: str | None, expected: dict[str, str] | None
) -> None:
    assert extract_problem_duration(transcript) == expected

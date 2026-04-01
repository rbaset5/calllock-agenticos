from __future__ import annotations

from outbound import assistant


def test_route_intent_matches_expected_commands() -> None:
    assert assistant.route_intent("what's next") == "WHAT_NEXT"
    assert assistant.route_intent("Open Dialer") == "OPEN_DIALER"
    assert assistant.route_intent("show me callbacks") == "SHOW_CALLBACKS"
    assert assistant.route_intent("who needs attention") == "SHOW_FOUNDER_TOUCH"
    assert assistant.route_intent("show full day") == "SHOW_FULL_DAY"
    assert assistant.route_intent("end my day") == "END_MY_DAY"


def test_route_intent_falls_back_for_open_ended_questions() -> None:
    assert assistant.route_intent("why did my connect rate drop?") is None

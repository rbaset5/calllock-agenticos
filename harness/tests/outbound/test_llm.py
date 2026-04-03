from __future__ import annotations

import pytest

from outbound.llm import llm_completion


def test_llm_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChoice:
        class message:
            content = "Hey, this is a test message. - Rashid"

    class FakeResponse:
        choices = [FakeChoice()]

    monkeypatch.setattr("outbound.llm.completion", lambda **kwargs: FakeResponse())

    result = llm_completion(system_prompt="test", user_prompt="test")
    assert result["status"] == "complete"
    assert result["text"] == "Hey, this is a test message. - Rashid"


def test_llm_completion_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChoice:
        class message:
            content = ""

    class FakeResponse:
        choices = [FakeChoice()]

    monkeypatch.setattr("outbound.llm.completion", lambda **kwargs: FakeResponse())

    result = llm_completion(system_prompt="test", user_prompt="test", max_retries=1)
    assert result["status"] == "failed"
    assert result["text"] is None


def test_llm_completion_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(**kwargs):
        raise RuntimeError("LLM is down")

    monkeypatch.setattr("outbound.llm.completion", raise_error)

    result = llm_completion(system_prompt="test", user_prompt="test", max_retries=1)
    assert result["status"] == "failed"
    assert result["text"] is None

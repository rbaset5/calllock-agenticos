from __future__ import annotations

from outbound import assistant


class _FlakyClient:
    def __init__(self) -> None:
        self.calls = 0

    async def start(self, token: str) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary discord outage")


def test_run_bot_forever_retries_after_failure() -> None:
    client = _FlakyClient()
    sleeps: list[float] = []

    success = assistant._run_bot_forever(client, "discord-token", sleep_fn=sleeps.append, max_attempts=2)

    assert success is True
    assert client.calls == 2
    assert sleeps == [1.0]


def test_answer_question_passes_explicit_anthropic_key(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _Message:
        tool_calls = []
        content = "ok"

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _Response()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(assistant, "completion", fake_completion)

    answer = assistant.answer_question("status?")

    assert answer == "ok"
    assert len(calls) == 1
    assert calls[0]["api_key"] == "test-anthropic-key"

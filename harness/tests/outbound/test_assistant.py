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

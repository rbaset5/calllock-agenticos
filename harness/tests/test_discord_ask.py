from __future__ import annotations

from fastapi.testclient import TestClient

from harness.server import app


class _ToThreadRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...]]] = []

    async def __call__(self, func, *args):
        self.calls.append((func, args))
        return func(*args)


def test_discord_ask_requires_secret(monkeypatch) -> None:
    monkeypatch.delenv("HARNESS_EVENT_SECRET", raising=False)
    client = TestClient(app)

    response = client.post("/discord/ask", json={"question": "status?"})

    assert response.status_code == 503
    assert response.json()["detail"] == "HARNESS_EVENT_SECRET must be configured for /discord/ask"


def test_discord_ask_uses_executor_and_returns_answer(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    recorder = _ToThreadRecorder()

    import harness.server as server
    import outbound.assistant as assistant

    monkeypatch.setattr(server.asyncio, "to_thread", recorder)
    fake_answer = lambda question: f"echo:{question}"
    monkeypatch.setattr(assistant, "answer_question", fake_answer)

    client = TestClient(app)
    response = client.post(
        "/discord/ask",
        headers={"Authorization": "Bearer test-secret"},
        json={"question": "status?"},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "echo:status?"}
    assert len(recorder.calls) == 1
    func, args = recorder.calls[0]
    assert func is fake_answer
    assert args == ("status?",)


def test_discord_ask_missing_question(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)

    response = client.post(
        "/discord/ask",
        headers={"Authorization": "Bearer test-secret"},
        json={"question": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "question is required"

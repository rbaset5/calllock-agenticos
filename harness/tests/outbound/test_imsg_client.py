from __future__ import annotations

import subprocess

import pytest

from outbound.imsg_client import send_imessage, health_check


def test_send_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outbound.imsg_client.shutil.which", lambda _: "/usr/local/bin/imsg")
    monkeypatch.setattr(
        "outbound.imsg_client.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr=""),
    )

    result = send_imessage("+16025551234", "test message")
    assert result["success"] is True
    assert result["error"] is None


def test_send_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outbound.imsg_client.shutil.which", lambda _: "/usr/local/bin/imsg")
    monkeypatch.setattr("outbound.imsg_client.RETRY_DELAY_S", 0)  # Skip delay in tests

    call_count = 0

    def mock_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="AppleScript error")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("outbound.imsg_client.subprocess.run", mock_run)

    result = send_imessage("+16025551234", "test message")
    assert result["success"] is True
    assert call_count == 2


def test_send_all_attempts_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outbound.imsg_client.shutil.which", lambda _: "/usr/local/bin/imsg")
    monkeypatch.setattr("outbound.imsg_client.RETRY_DELAY_S", 0)
    monkeypatch.setattr(
        "outbound.imsg_client.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="permission denied"),
    )

    result = send_imessage("+16025551234", "test message")
    assert result["success"] is False
    assert "permission denied" in result["error"]


def test_send_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outbound.imsg_client.shutil.which", lambda _: "/usr/local/bin/imsg")
    monkeypatch.setattr("outbound.imsg_client.RETRY_DELAY_S", 0)

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="imsg", timeout=30)

    monkeypatch.setattr("outbound.imsg_client.subprocess.run", mock_run)

    result = send_imessage("+16025551234", "test message")
    assert result["success"] is False
    assert "timed out" in result["error"]


def test_send_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outbound.imsg_client.shutil.which", lambda _: None)

    result = send_imessage("+16025551234", "test message")
    assert result["success"] is False
    assert "not found" in result["error"]

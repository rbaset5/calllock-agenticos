from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient


def _reload_server_module():
    sys.modules.pop("harness.server", None)
    return importlib.import_module("harness.server")


def test_discord_bot_does_not_start_by_default(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-token")
    monkeypatch.delenv("DISCORD_BOT_ENABLED", raising=False)

    import outbound.assistant as assistant

    with patch.object(assistant, "start_bot_background") as start_bot:
        server = _reload_server_module()
        assert start_bot.call_count == 0
        with TestClient(server.app):
            pass
        assert start_bot.call_count == 0


def test_discord_bot_starts_only_when_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "discord-token")
    monkeypatch.setenv("DISCORD_BOT_ENABLED", "true")

    import outbound.assistant as assistant

    with patch.object(assistant, "start_bot_background") as start_bot:
        server = _reload_server_module()
        assert start_bot.call_count == 0
        with TestClient(server.app):
            pass
        assert start_bot.call_count == 1

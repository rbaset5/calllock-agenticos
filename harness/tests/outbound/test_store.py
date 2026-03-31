from __future__ import annotations

from outbound import store


def test_sprint_scoreboard_accepts_dict_rpc_response(monkeypatch) -> None:
    expected = {
        "daily_dials": 0,
        "weekly_dials": 0,
        "total_dials": 0,
    }

    monkeypatch.setattr(store, "_using_supabase", lambda: True)
    monkeypatch.setattr(store.supabase_repository, "_rpc", lambda *args, **kwargs: expected)

    result = store.sprint_scoreboard(
        tenant_id="00000000-0000-0000-0000-000000000001",
        start_date="2026-03-31",
        today="2026-03-31",
    )

    assert result == expected

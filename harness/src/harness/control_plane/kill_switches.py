from __future__ import annotations

from db.repository import list_kill_switches, save_kill_switch


def upsert_kill_switch(payload: dict) -> dict:
    return save_kill_switch(payload)


def evaluate_kill_switches(*, tenant_id: str | None = None, worker_id: str | None = None) -> dict | None:
    for switch in list_kill_switches(active_only=True):
        if switch["scope"] == "global":
            return switch
        if switch["scope"] == "tenant" and switch.get("scope_id") == tenant_id:
            return switch
        if switch["scope"] == "worker" and switch.get("scope_id") == worker_id:
            return switch
    return None

from __future__ import annotations

from datetime import date
from typing import Any

from db import repository as db_repository


def insert_touchpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return db_repository.insert_growth_touchpoint(payload)


def list_touchpoints(*, tenant_id: str, touchpoint_type: str | None = None) -> list[dict[str, Any]]:
    return db_repository.list_growth_touchpoints(tenant_id=tenant_id, touchpoint_type=touchpoint_type)


def insert_belief_event(payload: dict[str, Any]) -> dict[str, Any]:
    return db_repository.insert_growth_belief_event(payload)


def list_belief_events(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_belief_events(tenant_id=tenant_id)


def insert_dlq_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return db_repository.insert_growth_dlq_entry(payload)


def resolve_dlq_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    return db_repository.resolve_growth_dlq_entry(entry_id, updates)


def list_dlq_entries(*, tenant_id: str, unresolved_only: bool = False) -> list[dict[str, Any]]:
    return db_repository.list_growth_dlq_entries(tenant_id=tenant_id, unresolved_only=unresolved_only)


def upsert_experiment_history(payload: dict[str, Any]) -> dict[str, Any]:
    return db_repository.upsert_growth_experiment_history(payload)


def get_experiment_history(experiment_id: str) -> dict[str, Any]:
    return db_repository.get_growth_experiment_history(experiment_id)


def list_experiment_history(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_experiment_history(tenant_id=tenant_id)


def list_segment_performance(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_segment_performance(tenant_id=tenant_id)


def list_cost_per_acquisition(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_cost_per_acquisition(tenant_id=tenant_id)


def list_insights(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_insights(tenant_id=tenant_id)


def list_founder_overrides(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_founder_overrides(tenant_id=tenant_id)


def list_loss_records(*, tenant_id: str) -> list[dict[str, Any]]:
    return db_repository.list_growth_loss_records(tenant_id=tenant_id)


def list_growth_wedges(*, tenant_id: str) -> list[str]:
    return db_repository.list_growth_wedges(tenant_id=tenant_id)


def upsert_wedge_fitness_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return db_repository.upsert_growth_wedge_fitness_snapshot(payload)


def get_latest_wedge_fitness_snapshot(*, tenant_id: str, wedge: str) -> dict[str, Any] | None:
    return db_repository.get_latest_growth_wedge_fitness_snapshot(tenant_id=tenant_id, wedge=wedge)


def snapshot_exists(*, tenant_id: str, wedge: str, snapshot_week: date) -> bool:
    latest = get_latest_wedge_fitness_snapshot(tenant_id=tenant_id, wedge=wedge)
    return bool(latest and latest.get("snapshot_week") == snapshot_week.isoformat())

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from harness.alerts.definitions import ALERT_TYPES
from knowledge.pack_loader import load_json_yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
VOICE_MONITOR_SPEC_PATH = REPO_ROOT / "knowledge" / "detection" / "voice-monitor-spec.yaml"
EXPECTED_SCHEMA_VERSION = "1.0"
EXPECTED_CATALOG_ID = "voice-monitor-spec"
EXPECTED_SURFACE = "voice"
EXPECTED_DOMAIN = "detection"
ALLOWED_THRESHOLD_OPERATORS = {"<", "<=", ">", ">="}
SEVERITIES = {"low", "medium", "high", "critical"}
CATALOG_KEYS = {
    "schema_version",
    "catalog_id",
    "surface",
    "domain",
    "ownership",
    "default_threshold",
    "triage_default",
    "notification_default",
    "monitors",
}
MONITOR_KEYS = {
    "monitor_id",
    "alert_type",
    "summary",
    "severity",
    "threshold",
    "surface",
    "domain",
    "ownership",
    "triage_default",
    "notification_default",
}
OWNERSHIP_KEYS = {"team", "pager"}
THRESHOLD_KEYS = {"metric", "operator", "value", "window_minutes", "min_sample_size"}
MONITOR_THRESHOLD_KEYS = {"metric", "operator", "value", "window_minutes", "min_sample_size"}
TRIAGE_DEFAULT_KEYS = {"priority", "queue"}
NOTIFICATION_DEFAULT_KEYS = {"channel", "target"}


def load_voice_monitor_catalog(path: str | Path = VOICE_MONITOR_SPEC_PATH) -> dict[str, object]:
    catalog = load_json_yaml(path)
    _validate_voice_monitor_catalog(catalog)
    return _normalize_voice_monitor_catalog(catalog)


def voice_monitor_ids(catalog: Mapping[str, object] | None = None) -> list[str]:
    current_catalog = catalog if catalog is not None else load_voice_monitor_catalog()
    monitors = current_catalog.get("monitors", [])
    return [
        str(monitor["monitor_id"])
        for monitor in monitors
        if isinstance(monitor, dict) and "monitor_id" in monitor
    ]


def _validate_voice_monitor_catalog(catalog: Mapping[str, object]) -> None:
    _reject_unknown_keys(catalog, CATALOG_KEYS, "catalog")
    _require_keys(
        catalog,
        (
            "schema_version",
            "catalog_id",
            "surface",
            "domain",
            "ownership",
            "default_threshold",
            "triage_default",
            "notification_default",
            "monitors",
        ),
        "catalog",
    )
    _validate_expected_literal(catalog["schema_version"], EXPECTED_SCHEMA_VERSION, "catalog.schema_version")
    _validate_expected_literal(catalog["catalog_id"], EXPECTED_CATALOG_ID, "catalog.catalog_id")
    _validate_expected_literal(catalog["surface"], EXPECTED_SURFACE, "catalog.surface")
    _validate_expected_literal(catalog["domain"], EXPECTED_DOMAIN, "catalog.domain")
    _validate_ownership(catalog["ownership"], "catalog.ownership")
    _validate_threshold(catalog["default_threshold"], "catalog.default_threshold")
    _validate_triage_default(catalog["triage_default"], "catalog.triage_default")
    _validate_notification_default(catalog["notification_default"], "catalog.notification_default")

    monitors = catalog["monitors"]
    if not isinstance(monitors, list) or not monitors:
        raise ValueError("catalog.monitors must be a non-empty list")

    seen_monitor_ids: set[str] = set()
    for index, monitor in enumerate(monitors):
        location = f"catalog.monitors[{index}]"
        if not isinstance(monitor, dict):
            raise ValueError(f"{location} must be an object")
        _reject_unknown_keys(monitor, MONITOR_KEYS, location)
        _require_keys(
            monitor,
            (
                "monitor_id",
                "alert_type",
                "summary",
                "severity",
                "threshold",
            ),
            location,
        )
        monitor_id = _validate_non_empty_string(monitor["monitor_id"], f"{location}.monitor_id")
        if monitor_id in seen_monitor_ids:
            raise ValueError(f"duplicate monitor_id: {monitor_id}")
        seen_monitor_ids.add(monitor_id)
        alert_type = _validate_non_empty_string(monitor["alert_type"], f"{location}.alert_type")
        if alert_type != monitor_id:
            raise ValueError(f"{location}.alert_type must match monitor_id")
        if alert_type not in ALERT_TYPES:
            raise ValueError(f"{location}.alert_type must reference a registered alert type")
        _validate_non_empty_string(monitor["summary"], f"{location}.summary")
        severity = _validate_non_empty_string(monitor["severity"], f"{location}.severity")
        if severity not in SEVERITIES:
            raise ValueError(f"{location}.severity must be one of {sorted(SEVERITIES)}")
        _validate_monitor_threshold(monitor["threshold"], f"{location}.threshold")
        _build_effective_threshold(
            monitor["threshold"],
            catalog["default_threshold"],
            f"{location}.effective_threshold",
        )
        _validate_inherited_identity(monitor, catalog, "surface", location)
        _validate_inherited_identity(monitor, catalog, "domain", location)
        _validate_inherited_identity(monitor, catalog, "ownership", location)
        if "default_threshold" in monitor:
            raise ValueError(f"{location}.default_threshold is not allowed; use catalog.default_threshold")
        if "triage_default" in monitor:
            _validate_triage_default(monitor["triage_default"], f"{location}.triage_default")
        if "notification_default" in monitor:
            _validate_notification_default(monitor["notification_default"], f"{location}.notification_default")


def _normalize_voice_monitor_catalog(catalog: Mapping[str, object]) -> dict[str, object]:
    normalized_catalog = deepcopy(dict(catalog))
    base_threshold = deepcopy(normalized_catalog["default_threshold"])
    base_surface = normalized_catalog["surface"]
    base_domain = normalized_catalog["domain"]
    base_ownership = deepcopy(normalized_catalog["ownership"])
    base_triage = deepcopy(normalized_catalog["triage_default"])
    base_notification = deepcopy(normalized_catalog["notification_default"])

    normalized_monitors = []
    for raw_monitor in normalized_catalog["monitors"]:
        monitor = deepcopy(raw_monitor)
        effective_threshold = _build_effective_threshold(
            monitor["threshold"],
            base_threshold,
            "catalog.monitors[].effective_threshold",
        )
        monitor["threshold"] = deepcopy(effective_threshold)
        monitor["effective_threshold"] = deepcopy(effective_threshold)
        monitor.setdefault("surface", base_surface)
        monitor.setdefault("domain", base_domain)
        monitor.setdefault("ownership", deepcopy(base_ownership))
        monitor.setdefault("triage_default", deepcopy(base_triage))
        monitor.setdefault("notification_default", deepcopy(base_notification))
        normalized_monitors.append(monitor)

    normalized_catalog["monitors"] = normalized_monitors
    return normalized_catalog


def _require_keys(payload: Mapping[str, object], keys: tuple[str, ...], location: str) -> None:
    for key in keys:
        if key not in payload:
            raise ValueError(f"{location}.{key} is required")


def _reject_unknown_keys(payload: Mapping[str, object], allowed_keys: set[str], location: str) -> None:
    unknown_keys = sorted(set(payload) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"{location} contains unknown keys: {', '.join(unknown_keys)}")


def _validate_expected_literal(value: object, expected: str, location: str) -> None:
    string_value = _validate_non_empty_string(value, location)
    if string_value != expected:
        raise ValueError(f"{location} must be {expected!r}")


def _validate_non_empty_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value


def _validate_ownership(payload: object, location: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{location} must be an object")
    _reject_unknown_keys(payload, OWNERSHIP_KEYS, location)
    _require_keys(payload, ("team", "pager"), location)
    _validate_non_empty_string(payload["team"], f"{location}.team")
    _validate_non_empty_string(payload["pager"], f"{location}.pager")


def _validate_threshold(payload: object, location: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{location} must be an object")
    _reject_unknown_keys(payload, THRESHOLD_KEYS, location)
    _require_keys(payload, ("metric", "operator", "value", "window_minutes", "min_sample_size"), location)
    _validate_non_empty_string(payload["metric"], f"{location}.metric")
    operator = _validate_non_empty_string(payload["operator"], f"{location}.operator")
    if operator not in ALLOWED_THRESHOLD_OPERATORS:
        raise ValueError(f"{location}.operator must be one of {sorted(ALLOWED_THRESHOLD_OPERATORS)}")
    _validate_positive_number(payload["value"], f"{location}.value")
    _validate_positive_number(payload["window_minutes"], f"{location}.window_minutes")
    _validate_positive_number(payload["min_sample_size"], f"{location}.min_sample_size")


def _validate_monitor_threshold(payload: object, location: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{location} must be an object")
    _reject_unknown_keys(payload, MONITOR_THRESHOLD_KEYS, location)
    _require_keys(payload, ("metric", "value"), location)
    _validate_non_empty_string(payload["metric"], f"{location}.metric")
    _validate_positive_number(payload["value"], f"{location}.value")

    optional_operator = payload.get("operator")
    if optional_operator is not None:
        operator = _validate_non_empty_string(optional_operator, f"{location}.operator")
        if operator not in ALLOWED_THRESHOLD_OPERATORS:
            raise ValueError(f"{location}.operator must be one of {sorted(ALLOWED_THRESHOLD_OPERATORS)}")

    optional_window = payload.get("window_minutes")
    if optional_window is not None:
        _validate_positive_number(optional_window, f"{location}.window_minutes")

    optional_sample = payload.get("min_sample_size")
    if optional_sample is not None:
        _validate_positive_number(optional_sample, f"{location}.min_sample_size")


def _validate_triage_default(payload: object, location: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{location} must be an object")
    _reject_unknown_keys(payload, TRIAGE_DEFAULT_KEYS, location)
    _require_keys(payload, ("priority", "queue"), location)
    _validate_non_empty_string(payload["priority"], f"{location}.priority")
    _validate_non_empty_string(payload["queue"], f"{location}.queue")


def _validate_notification_default(payload: object, location: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{location} must be an object")
    _reject_unknown_keys(payload, NOTIFICATION_DEFAULT_KEYS, location)
    _require_keys(payload, ("channel", "target"), location)
    _validate_non_empty_string(payload["channel"], f"{location}.channel")
    _validate_non_empty_string(payload["target"], f"{location}.target")


def _validate_positive_number(value: object, location: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{location} must be a positive number")


def _validate_inherited_identity(
    monitor: Mapping[str, object],
    catalog: Mapping[str, object],
    field_name: str,
    location: str,
) -> None:
    if field_name not in monitor:
        return
    if monitor[field_name] != catalog[field_name]:
        raise ValueError(f"{location}.{field_name} must match catalog.{field_name}")


def _build_effective_threshold(
    threshold: object,
    default_threshold: object,
    location: str,
) -> dict[str, object]:
    if not isinstance(default_threshold, dict):
        raise ValueError(f"{location} requires a valid catalog.default_threshold")
    if not isinstance(threshold, dict):
        raise ValueError(f"{location} requires a valid monitor threshold")
    merged_threshold = deepcopy(default_threshold)
    merged_threshold.update(threshold)
    _validate_threshold(merged_threshold, location)
    return merged_threshold

import json
from pathlib import Path

import pytest

from harness.alerts.definitions import ALERT_TYPES


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MONITOR_IDS = [
    "voice_empty_structured_output_spike",
    "voice_required_field_missing_spike",
    "voice_warning_rate_spike",
    "voice_route_missing_spike",
    "voice_safety_emergency_mismatch_signal",
]


def _valid_catalog() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "catalog_id": "voice-monitor-spec",
        "surface": "voice",
        "domain": "detection",
        "ownership": {"team": "voice-platform", "pager": "ops-voice"},
        "default_threshold": {
            "metric": "rate",
            "operator": ">=",
            "value": 0.05,
            "window_minutes": 60,
            "min_sample_size": 20,
        },
        "triage_default": {"priority": "investigate_today", "queue": "voice-monitoring"},
        "notification_default": {"channel": "ops", "target": "voice-monitoring"},
        "monitors": [
            {
                "monitor_id": "voice_empty_structured_output_spike",
                "alert_type": "voice_empty_structured_output_spike",
                "summary": "Structured post-call payloads are arriving empty more often than expected.",
                "severity": "high",
                "threshold": {
                    "metric": "empty_structured_output_rate",
                    "operator": ">=",
                    "value": 0.2,
                    "window_minutes": 60,
                    "min_sample_size": 20,
                },
            }
        ],
    }


def _write_catalog(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload))


def test_voice_monitor_catalog_loads_required_monitors() -> None:
    from harness.detection.catalog import load_voice_monitor_catalog, voice_monitor_ids

    catalog = load_voice_monitor_catalog(REPO_ROOT / "knowledge" / "detection" / "voice-monitor-spec.yaml")
    monitors = {monitor["monitor_id"]: monitor for monitor in catalog["monitors"]}

    assert catalog["catalog_id"] == "voice-monitor-spec"
    assert catalog["surface"] == "voice"
    assert catalog["domain"] == "detection"
    assert catalog["ownership"] == {"team": "voice-platform", "pager": "ops-voice"}
    assert catalog["default_threshold"] == {
        "metric": "rate",
        "operator": ">=",
        "value": 0.05,
        "window_minutes": 60,
        "min_sample_size": 20,
    }
    assert catalog["triage_default"] == {
        "priority": "investigate_today",
        "queue": "voice-monitoring",
    }
    assert catalog["notification_default"] == {
        "channel": "ops",
        "target": "voice-monitoring",
    }
    assert voice_monitor_ids(catalog) == REQUIRED_MONITOR_IDS
    assert [monitor["alert_type"] for monitor in catalog["monitors"]] == REQUIRED_MONITOR_IDS
    assert set(REQUIRED_MONITOR_IDS).issubset(ALERT_TYPES)
    assert monitors["voice_empty_structured_output_spike"]["severity"] == "high"
    assert monitors["voice_empty_structured_output_spike"]["threshold"] == {
        "metric": "empty_structured_output_rate",
        "operator": ">=",
        "value": 0.2,
        "window_minutes": 60,
        "min_sample_size": 20,
    }
    assert monitors["voice_empty_structured_output_spike"]["effective_threshold"] == {
        "metric": "empty_structured_output_rate",
        "operator": ">=",
        "value": 0.2,
        "window_minutes": 60,
        "min_sample_size": 20,
    }
    assert monitors["voice_warning_rate_spike"]["severity"] == "medium"
    assert monitors["voice_warning_rate_spike"]["threshold"] == {
        "metric": "warning_rate",
        "operator": ">=",
        "value": 0.3,
        "window_minutes": 60,
        "min_sample_size": 20,
    }
    assert monitors["voice_route_missing_spike"]["surface"] == "voice"
    assert monitors["voice_route_missing_spike"]["domain"] == "detection"
    assert monitors["voice_route_missing_spike"]["ownership"] == {
        "team": "voice-platform",
        "pager": "ops-voice",
    }
    assert "default_threshold" not in monitors["voice_route_missing_spike"]
    assert monitors["voice_route_missing_spike"]["triage_default"] == {
        "priority": "investigate_today",
        "queue": "voice-monitoring",
    }
    assert monitors["voice_route_missing_spike"]["notification_default"] == {
        "channel": "ops",
        "target": "voice-monitoring",
    }
    assert monitors["voice_safety_emergency_mismatch_signal"]["triage_default"] == {
        "priority": "page_immediately",
        "queue": "voice-monitoring",
    }
    assert monitors["voice_safety_emergency_mismatch_signal"]["notification_default"] == {
        "channel": "oncall",
        "target": "ops-voice",
    }
    assert monitors["voice_safety_emergency_mismatch_signal"]["effective_threshold"] == {
        "metric": "safety_emergency_mismatch_rate",
        "operator": ">=",
        "value": 0.02,
        "window_minutes": 60,
        "min_sample_size": 20,
    }


def test_voice_monitor_catalog_rejects_missing_required_contract_fields(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-voice-monitor-spec.yaml"
    payload = _valid_catalog()
    payload["default_threshold"] = {"metric": "rate", "operator": ">=", "value": 0.05, "window_minutes": 60}
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="threshold"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_invalid_schema_version(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-values-voice-monitor-spec.yaml"
    payload = _valid_catalog()
    payload["schema_version"] = "2.0"
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="schema_version"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "unknown-top-level-key.yaml"
    payload = _valid_catalog()
    payload["surfaec"] = "voice"
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="surfaec|unknown"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_unknown_monitor_keys(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "unknown-monitor-key.yaml"
    payload = _valid_catalog()
    payload["monitors"] = [
        {
            "monitor_id": "voice_empty_structured_output_spike",
            "alert_type": "voice_empty_structured_output_spike",
            "summary": "Structured post-call payloads are arriving empty more often than expected.",
            "severity": "high",
            "threshold": {
                "metric": "empty_structured_output_rate",
                "value": 0.2,
            },
            "triage_defualt": {"priority": "investigate_today", "queue": "voice-monitoring"},
        }
    ]
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="triage_defualt|unknown"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_empty_catalog_id(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "empty-catalog-id.yaml"
    payload = _valid_catalog()
    payload["catalog_id"] = ""
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="catalog_id"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_invalid_domain(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-domain.yaml"
    payload = _valid_catalog()
    payload["domain"] = "wrong-domain"
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="domain"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_invalid_threshold_operator(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-operator.yaml"
    payload = _valid_catalog()
    payload["default_threshold"] = {
        "metric": "rate",
        "operator": "!=",
        "value": 0.05,
        "window_minutes": 60,
        "min_sample_size": 20,
    }
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="operator"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_non_positive_threshold_window(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-window.yaml"
    payload = _valid_catalog()
    payload["default_threshold"] = {
        "metric": "rate",
        "operator": ">=",
        "value": 0.05,
        "window_minutes": 0,
        "min_sample_size": 20,
    }
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="window_minutes"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_non_positive_threshold_sample_size(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-sample-size.yaml"
    payload = _valid_catalog()
    payload["default_threshold"] = {
        "metric": "rate",
        "operator": ">=",
        "value": 0.05,
        "window_minutes": 60,
        "min_sample_size": 0,
    }
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="min_sample_size"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_malformed_severity_value(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    invalid_catalog_path = tmp_path / "invalid-severity.yaml"
    payload = _valid_catalog()
    payload["monitors"] = [
        {
            "monitor_id": "voice_empty_structured_output_spike",
            "alert_type": "voice_empty_structured_output_spike",
            "summary": "Structured post-call payloads are arriving empty more often than expected.",
            "severity": [],
            "threshold": {
                "metric": "empty_structured_output_rate",
                "value": 0.2,
            },
        }
    ]
    _write_catalog(invalid_catalog_path, payload)

    with pytest.raises(ValueError, match="severity"):
        load_voice_monitor_catalog(invalid_catalog_path)


def test_voice_monitor_catalog_rejects_monitor_surface_drift(tmp_path: Path) -> None:
    from harness.detection.catalog import load_voice_monitor_catalog

    drift_catalog_path = tmp_path / "drift-voice-monitor-spec.yaml"
    payload = _valid_catalog()
    payload["monitors"] = [
        {
            "monitor_id": "voice_empty_structured_output_spike",
            "alert_type": "voice_empty_structured_output_spike",
            "summary": "Structured post-call payloads are arriving empty more often than expected.",
            "surface": "email",
            "severity": "high",
            "threshold": {
                "metric": "empty_structured_output_rate",
                "operator": ">=",
                "value": 0.2,
                "window_minutes": 60,
                "min_sample_size": 20,
            },
        }
    ]
    _write_catalog(drift_catalog_path, payload)

    with pytest.raises(ValueError, match="surface"):
        load_voice_monitor_catalog(drift_catalog_path)


def test_voice_monitor_ids_respects_explicit_empty_mapping() -> None:
    from harness.detection.catalog import voice_monitor_ids

    assert voice_monitor_ids({}) == []

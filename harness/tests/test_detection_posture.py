from db.repository import create_alert_and_sync_incident

from harness.detection.posture import build_detection_posture


def test_detection_posture_filters_to_meaningful_active_threads() -> None:
    create_alert_and_sync_incident(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_safety_emergency_mismatch_signal",
            "severity": "critical",
            "message": "Safety mismatch detected",
            "metrics": {
                "detection": {
                    "notification_outcome": "founder_notify",
                }
            },
        }
    )
    create_alert_and_sync_incident(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_route_missing_spike",
            "severity": "high",
            "message": "Route missing spike",
            "metrics": {
                "detection": {
                    "notification_outcome": "internal_only",
                }
            },
        }
    )

    posture = build_detection_posture(tenant_id="tenant-alpha")

    assert "active_threads" in posture
    assert "counts" in posture
    assert posture["counts"]["open_threads"] == 1
    assert posture["counts"]["founder_visible_threads"] == 1
    assert all(
        thread["notification_outcome"] in {"operator_notify", "founder_notify"}
        for thread in posture["active_threads"]
    )

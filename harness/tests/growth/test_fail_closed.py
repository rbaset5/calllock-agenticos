from __future__ import annotations

from growth.gate.health_gate import HealthGateTimeoutError, check_health_gate


def test_growth_routes_require_bearer_secret(client, auth_headers) -> None:
    unauthorized = client.post(
        "/growth/gate/check",
        json={"messages": [{"message_id": "msg-1"}]},
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/growth/gate/check",
        headers=auth_headers,
        json={"messages": [{"message_id": "msg-1"}]},
    )
    assert authorized.status_code == 200


def test_health_gate_fail_closed_on_timeout() -> None:
    def timeout_evaluator(message: dict[str, object]) -> dict[str, object]:
        raise HealthGateTimeoutError("timeout")

    result = check_health_gate(
        [{"message_id": "msg-1"}, {"message_id": "msg-2"}],
        evaluator=timeout_evaluator,
    )

    assert result["sent_count"] == 0
    assert result["queued_count"] == 2
    assert result["blocked_count"] == 0
    assert [outcome["status"] for outcome in result["outcomes"]] == ["queued", "queued"]
    assert all(outcome["reason"] == "gate_timeout" for outcome in result["outcomes"])


def test_health_gate_rejection_blocks_instead_of_queueing() -> None:
    result = check_health_gate(
        [
            {"message_id": "msg-1", "duplicate_send": True},
            {"message_id": "msg-2"},
        ]
    )

    assert result["sent_count"] == 1
    assert result["queued_count"] == 0
    assert result["blocked_count"] == 1
    assert result["outcomes"][0] == {"message_id": "msg-1", "status": "blocked", "reason": "duplicate_send"}
    assert result["outcomes"][1] == {"message_id": "msg-2", "status": "sent", "reason": "approved"}

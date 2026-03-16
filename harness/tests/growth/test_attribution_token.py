from __future__ import annotations

import pytest

from growth.attribution.tokens import mint_token, validate_token
from growth.memory.models import InvalidAttributionTokenError


def test_attribution_token_round_trip() -> None:
    token = mint_token(
        "tenant-alpha",
        "00000000-0000-0000-0000-00000000c101",
        experiment_id="00000000-0000-0000-0000-00000000d101",
        arm_id="arm-a",
        issued_at=1_700_000_000,
    )

    payload = validate_token(token, "tenant-alpha", now=1_700_000_100)
    assert payload.tenant_id == "00000000-0000-0000-0000-000000000001"
    assert payload.prospect_id == "00000000-0000-0000-0000-00000000c101"
    assert payload.arm_id == "arm-a"


def test_cross_tenant_token_validation_fails() -> None:
    token = mint_token("tenant-alpha", "00000000-0000-0000-0000-00000000c102", issued_at=1_700_000_000)

    with pytest.raises(InvalidAttributionTokenError, match="tenant_mismatch"):
        validate_token(token, "tenant-beta", now=1_700_000_100)


def test_tampered_and_expired_tokens_fail() -> None:
    token = mint_token("tenant-alpha", "00000000-0000-0000-0000-00000000c103", issued_at=1_700_000_000)
    tampered = f"{token[:-1]}x"

    with pytest.raises(InvalidAttributionTokenError):
        validate_token(tampered, "tenant-alpha", now=1_700_000_100)

    with pytest.raises(InvalidAttributionTokenError, match="expired"):
        validate_token(token, "tenant-alpha", now=1_700_000_000 + (91 * 24 * 60 * 60))


def test_malformed_token_fails() -> None:
    with pytest.raises(InvalidAttributionTokenError, match="malformed"):
        validate_token("not-a-token", "tenant-alpha")


def test_unknown_key_fails() -> None:
    token = mint_token("tenant-alpha", "00000000-0000-0000-0000-00000000c104", issued_at=1_700_000_000)
    payload_b64, signature = token.rsplit(".", 1)
    mutated = token.replace('"kid":"k1"', '"kid":"k999"') if '"kid":"k1"' in token else None
    if mutated is None:
        import base64
        import json

        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(f"{payload_b64}{padding}"))
        payload["kid"] = "k999"
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).rstrip(b"=").decode("ascii")
        mutated = f"{encoded}.{signature}"

    with pytest.raises(InvalidAttributionTokenError, match="unknown_key"):
        validate_token(mutated, "tenant-alpha", now=1_700_000_100)

# ADR 012: Attribution Token Lifecycle

Status: Proposed

## Context

The design doc (§7.16) defines signed attribution tokens as `?t=base64(payload).HMAC_SIGNATURE` using HMAC-SHA256, replacing plain URL parameters. The format is specified but several implementation-critical details are not:

1. **Token expiry duration** — "includes timestamp for expiry" but no duration defined
2. **Payload structure** — which fields are encoded, and in what order
3. **Tenant binding** — unclear if tenant_id is embedded in the token or only in surrounding context
4. **Key rotation** — no strategy for rotating HMAC secrets without invalidating in-flight tokens
5. **Replay defense** — timestamp validates expiry but no explicit replay prevention beyond idempotency

Without these, Droid cannot implement token creation or validation.

## Decision

### Token payload structure

The token payload is a JSON object, base64url-encoded (RFC 4648 §5, no padding):

```json
{
  "v": 1,
  "tid": "tenant_uuid",
  "pid": "prospect_uuid",
  "eid": "experiment_uuid_or_null",
  "aid": "arm_id_or_null",
  "iat": 1710400000,
  "kid": "key_version"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `v` | integer | yes | Token format version (always `1` in Phase 1) |
| `tid` | string (UUID) | yes | Tenant ID — binds token to tenant |
| `pid` | string (UUID) | yes | Prospect ID |
| `eid` | string (UUID) | no | Experiment ID (null if no active experiment) |
| `aid` | string | no | Arm ID (null if no active experiment) |
| `iat` | integer | yes | Issued-at timestamp (Unix seconds, UTC) |
| `kid` | string | yes | Key ID used to sign (for rotation, see below) |

The full token is: `base64url(json_payload) + "." + base64url(hmac_sha256(signing_key, base64url(json_payload)))`

### Token expiry

**Duration: 90 days from `iat`.**

Rationale: B2B sales cycles for HVAC/trades run 30-60 days from first touch to pilot. 90 days covers the longest reasonable cycle with buffer. Tokens older than 90 days are rejected at validation time.

```python
TOKEN_EXPIRY_SECONDS = 90 * 24 * 60 * 60  # 7,776,000 seconds

def is_expired(iat: int) -> bool:
    return time.time() - iat > TOKEN_EXPIRY_SECONDS
```

### Tenant binding

**Tenant ID is embedded in the token payload (`tid` field).** Validation MUST check that the `tid` in the decoded token matches the tenant context of the request. This prevents cross-tenant token reuse even if an attacker obtains a valid token from another tenant.

```python
def validate_token(token: str, expected_tenant_id: str) -> TokenPayload:
    payload_b64, signature_b64 = token.rsplit(".", 1)

    payload = json.loads(base64url_decode(payload_b64))
    kid = payload["kid"]

    # 1. Verify signature with the correct key version
    signing_key = get_signing_key(expected_tenant_id, kid)
    expected_sig = hmac_sha256(signing_key, payload_b64.encode())
    if not hmac.compare_digest(base64url_decode(signature_b64), expected_sig):
        raise InvalidTokenError("signature_mismatch")

    # 2. Check tenant binding
    if payload["tid"] != expected_tenant_id:
        raise InvalidTokenError("tenant_mismatch")

    # 3. Check expiry
    if is_expired(payload["iat"]):
        raise InvalidTokenError("expired")

    return TokenPayload(**payload)
```

### HMAC key management and rotation

**Keys are per-tenant, stored in `tenant_configs` JSONB.**

```json
{
  "attribution_keys": {
    "current": { "kid": "k2", "secret": "base64_secret", "created_at": "2026-03-01T00:00:00Z" },
    "previous": { "kid": "k1", "secret": "base64_secret", "created_at": "2026-01-15T00:00:00Z" }
  }
}
```

**Rotation protocol:**

1. Generate new key, assign next `kid` (e.g., `k2` → `k3`)
2. Move `current` to `previous`, set new key as `current`
3. New tokens are signed with `current` key
4. Validation tries `current` key first; if signature fails AND `kid` matches `previous`, tries `previous` key
5. After 90 days (token expiry window), `previous` key can be deleted — no valid tokens signed with it remain
6. At most 2 active keys at any time

**Key generation:** 256-bit random secret via `secrets.token_bytes(32)`, base64-encoded for storage.

**Rotation trigger:** Manual via admin API or scheduled (recommended: every 180 days). No automated rotation in Phase 1.

### Replay defense

Replay is mitigated by three layers:

1. **Expiry window** — tokens older than 90 days are rejected (limits replay window)
2. **Idempotency** — touchpoint_log deduplicates on `touchpoint_id` (ADR 011). Replaying the same click with the same touchpoint_id is a no-op.
3. **Attribution is append-only** — recording the same attribution event twice does not change experiment outcomes because touchpoint_log uses `INSERT ... ON CONFLICT DO NOTHING` semantics.

Explicit nonce-based replay prevention is NOT implemented in Phase 1. The cost of a successful replay (one extra touchpoint_log row if touchpoint_id differs) is low and detectable via Signal Quality scoring. Phase 2 can add rate limiting per prospect_id if replay volume becomes a concern.

### Error handling

| Condition | Action | Metric |
|-----------|--------|--------|
| Malformed token (can't split on `.`) | Reject, log `attribution.malformed` | `attribution_errors{type="malformed"}` |
| Base64 decode failure | Reject, log `attribution.decode_error` | `attribution_errors{type="decode"}` |
| Signature mismatch | Reject, log `attribution.signature_invalid` | `attribution_errors{type="signature"}` |
| Tenant mismatch | Reject, log `attribution.tenant_mismatch` | `attribution_errors{type="tenant"}` |
| Expired token | Reject, log `attribution.expired` | `attribution_errors{type="expired"}` |
| Unknown `kid` | Reject, log `attribution.unknown_key` | `attribution_errors{type="unknown_key"}` |
| Valid token | Record touchpoint, log `attribution.valid` | `attribution_valid_total` |

All rejections return HTTP 204 (no content) to the client — do not leak validation details. Rejected tokens are logged with the full token for forensic review (tokens contain no PII beyond UUIDs).

## Consequences

- Token payload is self-describing (version field enables future format changes)
- Tenant binding prevents cross-tenant token reuse without requiring separate signing infrastructure
- Two-key rotation window matches token expiry — no valid token is ever unverifiable
- Replay defense is proportional to risk: idempotency handles the common case, rate limiting deferred to Phase 2
- All validation failures emit structured metrics for the Learning Integrity Monitor
- `kid` in token payload enables key rotation without coordinating deployment timing

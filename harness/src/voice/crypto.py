"""AES-256-GCM encryption helpers for tenant voice credentials."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(Exception):
    """Failed to decrypt with the current or previous credential key."""


def _get_key(env_var: str = "VOICE_CREDENTIAL_KEY") -> bytes:
    hex_key = os.environ.get(env_var)
    if not hex_key:
        raise RuntimeError(f"{env_var} environment variable is not set")

    try:
        key = bytes.fromhex(hex_key)
    except ValueError as exc:
        raise RuntimeError(f"{env_var} must be valid hex") from exc

    if len(key) != 32:
        raise RuntimeError(f"{env_var} must decode to exactly 32 bytes")

    return key


def encrypt_config(data: dict[str, Any]) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_config(encrypted: str) -> dict[str, Any]:
    try:
        raw = base64.b64decode(encrypted)
    except Exception as exc:
        raise DecryptionError("Failed to decode encrypted credential payload") from exc

    if len(raw) < 13:
        raise DecryptionError("Encrypted credential payload is too short")

    nonce, ciphertext = raw[:12], raw[12:]
    for key in _candidate_keys():
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
            data = json.loads(plaintext)
            if not isinstance(data, dict):
                raise DecryptionError("Decrypted credential payload is not a JSON object")
            return data
        except DecryptionError:
            raise
        except Exception:
            continue

    raise DecryptionError("Failed to decrypt with current or previous key")


def _candidate_keys() -> list[bytes]:
    keys = [_get_key()]
    previous_key = os.environ.get("VOICE_CREDENTIAL_KEY_PREV")
    if previous_key:
        try:
            prev = bytes.fromhex(previous_key)
        except ValueError as exc:
            raise RuntimeError("VOICE_CREDENTIAL_KEY_PREV must be valid hex") from exc
        if len(prev) != 32:
            raise RuntimeError("VOICE_CREDENTIAL_KEY_PREV must decode to exactly 32 bytes")
        keys.append(prev)
    return keys


__all__ = ["DecryptionError", "decrypt_config", "encrypt_config"]

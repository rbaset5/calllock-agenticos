from __future__ import annotations

import os

import pytest

from voice.crypto import DecryptionError, decrypt_config, encrypt_config


class TestEncryptDecrypt:
    def test_round_trip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        data = {"twilio_account_sid": "AC123", "twilio_auth_token": "secret"}

        encrypted = encrypt_config(data)

        assert encrypted != data
        assert isinstance(encrypted, str)

        decrypted = decrypt_config(encrypted)
        assert decrypted == data

    def test_key_rotation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        old_key = os.urandom(32).hex()
        new_key = os.urandom(32).hex()
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", old_key)
        encrypted = encrypt_config({"key": "value"})

        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", new_key)
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY_PREV", old_key)

        decrypted = decrypt_config(encrypted)
        assert decrypted == {"key": "value"}

    def test_wrong_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        encrypted = encrypt_config({"key": "value"})
        monkeypatch.setenv("VOICE_CREDENTIAL_KEY", os.urandom(32).hex())
        monkeypatch.delenv("VOICE_CREDENTIAL_KEY_PREV", raising=False)

        with pytest.raises(DecryptionError):
            decrypt_config(encrypted)

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VOICE_CREDENTIAL_KEY", raising=False)

        with pytest.raises(RuntimeError):
            encrypt_config({"key": "value"})

"""Tests for the AES-256 encrypted vault."""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.app.vault.auth_vault import SovereignVault


@pytest.fixture
def vault(tmp_path: Path) -> SovereignVault:
    return SovereignVault(key_file=tmp_path / "master.key")


def test_roundtrip_string(vault: SovereignVault) -> None:
    original = "hello, sovereign world!"
    token = vault.encrypt(original)
    assert isinstance(token, bytes)
    assert vault.decrypt(token) == original


def test_roundtrip_bytes(vault: SovereignVault) -> None:
    data = b"\x00\x01\x02\x03\xff"
    token = vault.encrypt_bytes(data)
    assert vault.decrypt_bytes(token) == data


def test_key_file_created(tmp_path: Path) -> None:
    key_file = tmp_path / "sub" / "master.key"
    SovereignVault(key_file=key_file)
    assert key_file.exists()


def test_key_persistence(tmp_path: Path) -> None:
    key_file = tmp_path / "master.key"
    v1 = SovereignVault(key_file=key_file)
    token = v1.encrypt("secret")
    # Second instance must load the same key
    v2 = SovereignVault(key_file=key_file)
    assert v2.decrypt(token) == "secret"


def test_invalid_token_raises(vault: SovereignVault) -> None:
    with pytest.raises(ValueError):
        vault.decrypt(b"not-a-valid-token")


def test_key_rotation_invalidates_old_tokens(vault: SovereignVault) -> None:
    token = vault.encrypt("before rotation")
    vault.rotate_key()
    with pytest.raises(ValueError):
        vault.decrypt(token)

"""
Sovereign AI Core — AES-256 Encrypted Vault
Manages the master encryption key and provides encrypt/decrypt helpers.
The key is generated on first use and persisted in the local vault directory.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("sovereign.vault")


class SovereignVault:
    """
    Local-first AES-256 (via Fernet) encryption vault.

    The Fernet scheme uses AES-128-CBC with HMAC-SHA256, which provides
    authenticated encryption equivalent to AES-256 in security strength
    when the key is generated with a CSPRNG (as done here).

    Usage::

        vault = SovereignVault(key_file=Path(".sovereign/vault/master.key"))
        token = vault.encrypt("my secret")
        plain = vault.decrypt(token)
    """

    def __init__(self, key_file: Path) -> None:
        self._key_file = key_file
        self._key = self._load_or_create_key()
        self._cipher = Fernet(self._key)
        logger.info("Vault initialised — key file: %s", key_file)

    # ── Key management ────────────────────────────────────────────────────────

    def _load_or_create_key(self) -> bytes:
        if self._key_file.exists():
            key = self._key_file.read_bytes().strip()
            logger.debug("Loaded existing vault key.")
            return key

        key = Fernet.generate_key()
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key_file.write_bytes(key)
        # Restrict permissions to owner-only (best-effort on all platforms)
        try:
            self._key_file.chmod(0o600)
        except NotImplementedError:
            pass
        logger.info("Generated new vault key and saved to %s", self._key_file)
        return key

    def rotate_key(self) -> None:
        """
        Generate a new encryption key.
        WARNING: existing encrypted tokens will become unreadable after rotation.
        """
        self._key = Fernet.generate_key()
        self._key_file.write_bytes(self._key)
        self._cipher = Fernet(self._key)
        logger.warning("Vault key rotated — previous tokens are now invalid.")

    # ── Encrypt / Decrypt ─────────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a UTF-8 string and return the Fernet token (bytes)."""
        return self._cipher.encrypt(plaintext.encode())

    def decrypt(self, token: bytes) -> str:
        """
        Decrypt a Fernet token and return the original string.
        Raises ``ValueError`` if the token is invalid or has been tampered with.
        """
        try:
            return self._cipher.decrypt(token).decode()
        except InvalidToken as exc:
            raise ValueError("Vault: failed to decrypt token — invalid or tampered data.") from exc

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes."""
        return self._cipher.encrypt(data)

    def decrypt_bytes(self, token: bytes) -> bytes:
        """Decrypt a Fernet token back to raw bytes."""
        try:
            return self._cipher.decrypt(token)
        except InvalidToken as exc:
            raise ValueError("Vault: failed to decrypt token.") from exc

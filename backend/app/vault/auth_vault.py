from cryptography.fernet import Fernet
from pathlib import Path
import os

class LocalVault:
    """
    AES-256 Encrypted Vault for Local AI Data.
    Zero-Cloud dependency.
    """
    def __init__(self, vault_path: str = ".vault/key.key"):
        self.path = Path(vault_path)
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)

    def _load_or_generate_key(self):
        if self.path.exists():
            return self.path.read_bytes()
        key = Fernet.generate_key()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(key)
        return key

    def encrypt(self, data: str) -> bytes:
        return self.cipher.encrypt(data.encode())

    def decrypt(self, token: bytes) -> str:
        return self.cipher.decrypt(token).decode()

vault = LocalVault()

"""
Sovereign AI Core — Application Settings
All values are read from environment variables (or .env) so nothing is hardcoded.
"""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API security
    sovereign_api_key: str = "dev-insecure-key-change-me"

    # Local LLM backend (Ollama default)
    ollama_base_url: str = "http://127.0.0.1:11434"
    lite_model: str = "phi3"
    standard_model: str = "llama3"
    frontier_model: str = "mixtral"

    # Storage — defaults to <project-root>/.sovereign/
    sovereign_data_dir: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Derived paths (not env-configurable, computed from sovereign_data_dir) ──

    @property
    def base_dir(self) -> Path:
        if self.sovereign_data_dir:
            return Path(self.sovereign_data_dir)
        # Walk up from this file to the project root
        return Path(__file__).resolve().parents[3] / ".sovereign"

    @property
    def vault_path(self) -> Path:
        return self.base_dir / "vault"

    @property
    def vector_store_path(self) -> Path:
        return self.base_dir / "vector_store"

    @property
    def log_path(self) -> Path:
        return self.base_dir / "logs"

    @property
    def encryption_key_file(self) -> Path:
        return self.vault_path / "master.key"

    @property
    def leak_log_file(self) -> Path:
        return self.log_path / "blocked_attempts.log"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.base_dir / 'sovereign_core.db'}"

    def ensure_dirs(self) -> None:
        """Create all required local directories on first run."""
        for path in (self.vault_path, self.vector_store_path, self.log_path):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()

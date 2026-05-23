"""
ASEF Configuration Module
==========================

Centralised, type-safe configuration powered by Pydantic Settings.
Values are loaded (in priority order) from:

1. Environment variables
2. ``.env`` file in the project root
3. Hard-coded defaults below

.. warning::
    This framework is for **defensive AI alignment research only**.
    Never commit real API keys to version control.
"""

from __future__ import annotations

import enum
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModelProvider(str, enum.Enum):
    """Supported LLM provider backends."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class LogLevel(str, enum.Enum):
    """Application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Root configuration for the AI Safety Evaluation Framework.

    All fields can be overridden via environment variables (case-insensitive)
    or a ``.env`` file.
    """

    # -- Provider API Keys --------------------------------------------------
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key. Required when default_model_provider is 'openai'.",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key. Required when default_model_provider is 'anthropic'.",
    )

    # -- Database -----------------------------------------------------------
    database_url: str = Field(
        default="sqlite+aiosqlite:///./asef.db",
        description="Async SQLAlchemy database URL.",
    )

    # -- Logging ------------------------------------------------------------
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Minimum log level emitted by the application.",
    )
    log_format: str = Field(
        default="json",
        description="Log output format. 'json' for structured logs, 'console' for human-readable.",
    )

    # -- Mode ---------------------------------------------------------------
    mock_mode: bool = Field(
        default=True,
        description="When True, use mock model responses instead of real API calls.",
    )
    default_model_provider: ModelProvider = Field(
        default=ModelProvider.MOCK,
        description="Default LLM provider used by evaluation agents.",
    )

    # -- API Server ---------------------------------------------------------
    api_host: str = Field(
        default="0.0.0.0",
        description="Bind address for the Uvicorn server.",
    )
    api_port: int = Field(
        default=8000,
        description="Port for the Uvicorn server.",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins for the API.",
    )

    # -- Sandbox ------------------------------------------------------------
    sandbox_max_files: int = Field(
        default=1000,
        description="Maximum number of files an agent may create in the sandbox.",
    )
    sandbox_max_file_size: int = Field(
        default=1_000_000,
        description="Maximum size in bytes for any single file in the sandbox.",
    )

    # -- Evaluation ---------------------------------------------------------
    default_max_turns: int = Field(
        default=20,
        description="Default maximum conversation turns per evaluation run.",
    )
    default_timeout_seconds: int = Field(
        default=300,
        description="Default timeout in seconds for a single evaluation run.",
    )

    # -- Pydantic v2 model config -------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton.

    The first call reads the environment / ``.env`` file; subsequent calls
    return the same instance.  Call ``get_settings.cache_clear()`` after
    mutating the environment if you need a fresh instance (useful in tests).
    """
    return Settings()

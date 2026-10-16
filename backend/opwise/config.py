"""Application configuration and settings using Pydantic Settings.

Governed by PROJECT_RULES.md (Rule 1 & 7) and ARCHITECTURE.md.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opwise backend configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="OPWISE_",
        env_file=".env",
        extra="ignore",
    )

    db_url: str = Field(
        default="sqlite+aiosqlite:///./opwise.sqlite3",
        description="Async SQLite database connection string.",
    )
    db_echo: bool = Field(
        default=False,
        description="Enable SQLAlchemy statement echo logging.",
    )
    db_timeout_seconds: int = Field(
        default=15,
        description="SQLite connection timeout in seconds.",
    )
    db_busy_timeout_ms: int = Field(
        default=5000,
        description="SQLite busy timeout in milliseconds.",
    )
    db_synchronous: str = Field(
        default="NORMAL",
        description="SQLite synchronous PRAGMA level (NORMAL or FULL).",
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="API route version prefix.",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        description="Allowed CORS origins for local development.",
    )


def get_settings() -> Settings:
    """Retrieve application settings singleton."""
    return Settings()

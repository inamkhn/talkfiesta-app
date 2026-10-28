"""Application settings loaded from the environment or ``.env``."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API and workers.

    One database URL serves both the async API session factory and the
    synchronous worker factory because the psycopg 3 driver supports both
    modes with the same ``postgresql+psycopg://`` scheme.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TalkFiesta API"
    environment: str = "local"
    debug: bool = False

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/talkfiesta"
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""

    return Settings()


settings = get_settings()

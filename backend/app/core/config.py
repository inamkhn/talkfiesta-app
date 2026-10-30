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

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/talkfiesta"
    )
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    rate_limit_enabled: bool = True

    # Auth. The secret must be injected per environment; the default only keeps
    # local development runnable and is rejected outside the local environment.
    jwt_secret_key: str = "local-development-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    refresh_cookie_name: str = "tf_refresh"
    refresh_cookie_path: str = "/api/v1/auth"
    refresh_cookie_secure: bool = True
    register_rate_limit_per_ip_per_hour: int = 10
    login_rate_limit_per_ip_per_hour: int = 10
    auth_action_rate_limit_per_ip_per_hour: int = 10
    password_reset_ttl_minutes: int = 30
    email_verification_ttl_minutes: int = 1440
    password_reset_url: str = "http://localhost:3000/reset-password"
    email_verification_url: str = "http://localhost:3000/verify-email"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 10
    google_client_id: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""

    return Settings()


settings = get_settings()

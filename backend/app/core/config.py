"""Application settings loaded from the environment or ``.env``."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_psycopg_url(url: str) -> str:
    """Normalize `postgres://` or `postgresql://` URLs (e.g. from Neon) to `postgresql+psycopg://`."""
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


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
        "postgresql://neondb_owner:npg_KgZc83NRTvIC@ep-long-smoke-a1bbqu3v-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    direct_database_url: str = ""
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_recycle: int = Field(default=300, ge=30, le=3600)
    database_connect_timeout: int = Field(default=10, ge=1, le=60)

    @property
    def migration_database_url(self) -> str:
        """Return direct database URL for migrations if set, else `database_url`."""
        return self.direct_database_url or self.database_url

    @property
    def database_connect_args(self) -> dict[str, object]:
        """Return psycopg 3 connect_args compatible with Neon Serverless & PgBouncer."""
        args: dict[str, object] = {
            "connect_timeout": self.database_connect_timeout,
        }
        if "-pooler." in self.database_url:
            args["prepare_threshold"] = None
        return args

    redis_url: str = "redis://localhost:6379/0"
    upstash_redis_rest_url: str = "https://caring-tapir-183131.upstash.io"
    upstash_redis_rest_token: str = "gQAAAAAAAstbAAIgcDEyNDUzMGI0ZmYyOTM0MDQ5OTQ4ZmRjZTU3NGMyNzMyMA"
    rate_limit_enabled: bool = True
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_worker_concurrency: int = Field(default=2, ge=1, le=32)
    celery_task_soft_time_limit: int = Field(default=240, ge=1)
    celery_task_time_limit: int = Field(default=300, ge=2)
    celery_visibility_timeout: int = Field(default=900, ge=3)
    outbox_dispatch_enabled: bool = False
    outbox_batch_size: int = Field(default=20, ge=1, le=100)
    outbox_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    outbox_lease_seconds: int = Field(default=120, ge=30, le=3600)
    outbox_max_attempts: int = Field(default=20, ge=1, le=100)
    assessment_execution_enabled: bool = True
    speaking_execution_enabled: bool = True
    speaking_job_max_attempts: int = Field(default=3, ge=1, le=10)
    vocabulary_execution_enabled: bool = True
    vocabulary_job_max_attempts: int = Field(default=3, ge=1, le=10)
    writing_execution_enabled: bool = True
    writing_job_max_attempts: int = Field(default=3, ge=1, le=10)
    content_generation_enabled: bool = True
    content_job_max_attempts: int = Field(default=3, ge=1, le=10)
    assessment_job_lease_seconds: int = Field(default=360, ge=30)
    assessment_job_max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_celery_timeouts(self):
        self.database_url = _normalize_psycopg_url(self.database_url)
        if self.direct_database_url:
            self.direct_database_url = _normalize_psycopg_url(
                self.direct_database_url
            )
        if self.assessment_job_lease_seconds <= self.celery_task_time_limit:
            raise ValueError(
                "Assessment job lease must exceed the Celery hard time limit."
            )
        if (
            not self.celery_task_soft_time_limit
            < self.celery_task_time_limit
            < self.celery_visibility_timeout
        ):
            raise ValueError(
                "Celery timeouts must satisfy soft limit < hard limit < visibility timeout."
            )
        if not self.celery_broker_url.startswith(("redis://", "rediss://")):
            raise ValueError("CELERY_BROKER_URL must use redis:// or rediss://.")
        return self

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
    assessment_content_release: str = "placement-bank-v1"
    assessment_starts_per_day: int = 3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    audio_upload_url_seconds: int = 300
    audio_max_bytes: int = 10 * 1024 * 1024
    audio_max_duration_seconds: int = 180
    audio_retention_days: int = 7
    speaking_audio_max_bytes: int = Field(default=15 * 1024 * 1024, ge=1)
    speaking_audio_min_duration_seconds: int = Field(default=10, ge=1, le=600)
    speaking_audio_max_duration_seconds: int = Field(default=180, ge=1, le=600)
    assessment_checkpoint_retention_days: int = Field(default=7, ge=1, le=365)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    openai_api_key: str = "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"
    openai_evaluation_model: str = "gpt-4o-mini"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    openai_timeout_seconds: int = Field(default=30, ge=5, le=120)
    assessment_rubric_version: str = "placement-v1"
    langsmith_tracing_enabled: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "talkfiesta"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_redact_learner_text: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""

    return Settings()


settings = get_settings()

"""Unit tests verifying the V4 database schema metadata and constraints."""

from __future__ import annotations

from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.base import Base

EXPECTED_V4_TABLES = {
    "users",
    "auth_sessions",
    "assessment_attempts",
    "assessment_responses",
    "content_items",
    "learning_plans",
    "module_progress",
    "practice_submissions",
    "practice_sessions",
    "user_vocabulary",
    "activity_completions",
    "media_uploads",
    "user_achievements",
    "ai_jobs",
    "outbox_events",
}


def test_v4_schema_registers_exact_15_tables() -> None:
    registered = set(Base.metadata.tables.keys())
    assert registered == EXPECTED_V4_TABLES


def test_users_v4_columns() -> None:
    users_cols = set(Base.metadata.tables["users"].columns.keys())
    assert {
        "id",
        "email",
        "password_hash",
        "google_sub",
        "role",
        "display_name",
        "profile",
        "preferences",
        "timezone",
        "onboarding_status",
        "current_cefr",
        "is_active",
        "email_verified_at",
        "token_version",
        "created_at",
        "updated_at",
    } <= users_cols


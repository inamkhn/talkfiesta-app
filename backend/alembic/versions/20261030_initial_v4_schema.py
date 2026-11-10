"""Initial V4 base schema (15 core tables).

Revision ID: 20261030_initial_v4
Revises: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision = "20261030_initial_v4"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if inspector.has_table("users"):
            return

    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("google_sub", sa.String(255), nullable=True, unique=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="LEARNER"),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "preferences", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column(
            "onboarding_status",
            sa.String(40),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        sa.Column("current_cefr", sa.String(2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('LEARNER','CONTENT_REVIEWER','ADMIN')", name="role"
        ),
        sa.CheckConstraint(
            "onboarding_status IN ('NOT_STARTED','PREFERENCES_SAVED','ASSESSING','RESULT_READY','COMPLETED')",
            name="onboarding_status",
        ),
    )
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )

    # 2. auth_sessions
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jti", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "rotated_from_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(30), nullable=True),
        sa.CheckConstraint(
            "revoked_reason IS NULL OR revoked_reason IN "
            "('LOGOUT','ROTATED','REUSE_DETECTED','PASSWORD_RESET','ADMIN')",
            name="revoked_reason",
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])

    # 3. content_items
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("module", sa.String(20), nullable=True),
        sa.Column("release_key", sa.String(60), nullable=False),
        sa.Column("cycle", sa.SmallInteger(), nullable=True),
        sa.Column("day", sa.SmallInteger(), nullable=True),
        sa.Column("cefr_level", sa.String(10), nullable=True),
        sa.Column("goal_variant", sa.String(40), nullable=True),
        sa.Column("slot", sa.String(20), nullable=True),
        sa.Column("domain", sa.String(40), nullable=True),
        sa.Column("agent_type", sa.String(20), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="HUMAN"),
        sa.Column("generation_batch_key", sa.String(80), nullable=True),
        sa.Column(
            "content_version", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('ASSESSMENT_QUESTION','SPEAKING_LESSON','VOCABULARY_LESSON',"
            "'WRITING_LESSON','VOCAB_WORD','INTERVIEW_QUESTION','LIVE_TOPIC')",
            name="valid_content_kind",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','REVIEW','PUBLISHED','ARCHIVED')",
            name="valid_content_status",
        ),
        sa.CheckConstraint("origin IN ('HUMAN','AI')", name="valid_content_origin"),
        sa.CheckConstraint(
            "cycle IS NULL OR cycle BETWEEN 1 AND 5", name="valid_content_cycle"
        ),
        sa.CheckConstraint(
            "day IS NULL OR day BETWEEN 1 AND 21", name="valid_content_day"
        ),
        sa.CheckConstraint("content_version >= 1", name="valid_content_version"),
    )
    op.create_index(
        "ix_content_items_lookup",
        "content_items",
        ["kind", "status", "release_key", "cefr_level", "goal_variant"],
    )
    op.create_index(
        "ix_content_items_curriculum",
        "content_items",
        ["release_key", "module", "cycle", "day", "goal_variant", "slot"],
    )
    op.create_index(
        "ix_content_items_interview",
        "content_items",
        ["kind", "domain", "agent_type"],
    )
    op.create_index(
        "uq_published_core_lesson",
        "content_items",
        ["release_key", "module", "cycle", "day", "cefr_level", "goal_variant"],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED' AND slot = 'CORE'"),
    )

    # 4. media_uploads (base columns prior to 20261101_audio_binding)
    op.create_table(
        "media_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(8, 2), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="INITIATED"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("object_key", name="uq_media_uploads_object_key"),
        sa.CheckConstraint(
            "purpose IN ('ASSESSMENT','SPEAKING','PRONUNCIATION','INTERVIEW')",
            name="valid_media_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('INITIATED','VERIFIED','REJECTED','DELETED')",
            name="valid_media_status",
        ),
    )
    op.create_index("ix_media_uploads_user_id", "media_uploads", ["user_id"])

    # 5. assessment_attempts
    op.create_table(
        "assessment_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False, server_default="INITIAL"),
        sa.Column(
            "status", sa.String(30), nullable=False, server_default="IN_PROGRESS"
        ),
        sa.Column(
            "content_release",
            sa.String(60),
            nullable=False,
            server_default="starter-v1",
        ),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("placement_cefr", sa.String(2), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('INITIAL','REASSESSMENT')", name="valid_attempt_kind"
        ),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','SUBMITTED','PROCESSING','COMPLETED','FAILED_RETRYABLE','FAILED_FINAL')",
            name="valid_attempt_status",
        ),
    )
    op.create_index(
        "ix_assessment_attempts_user_started",
        "assessment_attempts",
        ["user_id", "started_at"],
    )
    op.create_index(
        "uq_active_initial_attempt",
        "assessment_attempts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "kind = 'INITIAL' AND status IN ('IN_PROGRESS','SUBMITTED','PROCESSING','FAILED_RETRYABLE')"
        ),
    )

    # 6. assessment_responses
    op.create_table(
        "assessment_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assessment_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="ASSIGNED"
        ),
        sa.Column("answer", postgresql.JSONB(), nullable=True),
        sa.Column(
            "media_upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_uploads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("grading", postgresql.JSONB(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "assessment_attempt_id",
            "position",
            name="uq_assessment_response_attempt_position",
        ),
        sa.UniqueConstraint(
            "assessment_attempt_id",
            "question_content_id",
            name="uq_assessment_response_attempt_question",
        ),
        sa.CheckConstraint(
            "status IN ('ASSIGNED','ANSWERED','SKIPPED')",
            name="valid_assessment_response_status",
        ),
    )

    # 7. learning_plans
    op.create_table(
        "learning_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cycle", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("placement_cefr", sa.String(2), nullable=False),
        sa.Column(
            "plan_config", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("cycle BETWEEN 1 AND 5", name="valid_plan_cycle"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','PAUSED','SUPERSEDED')",
            name="valid_plan_status",
        ),
    )
    op.create_index(
        "uq_one_active_plan",
        "learning_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    # 8. module_progress
    op.create_table(
        "module_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "learning_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(20), nullable=False),
        sa.Column("content_release", sa.String(60), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column(
            "goal_variant", sa.String(40), nullable=False, server_default="GENERAL"
        ),
        sa.Column(
            "current_day", sa.SmallInteger(), nullable=False, server_default="1"
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="AWAITING_CONTENT",
        ),
        sa.Column(
            "prioritized", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "learning_plan_id", "module", name="uq_plan_module_progress"
        ),
        sa.CheckConstraint(
            "module IN ('SPEAKING','VOCABULARY','WRITING')",
            name="valid_progress_module",
        ),
        sa.CheckConstraint(
            "current_day BETWEEN 1 AND 21", name="valid_progress_day"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','AWAITING_CONTENT','COMPLETED')",
            name="valid_progress_status",
        ),
    )

    # 9. practice_submissions (base columns prior to 20261104..20261106)
    op.create_table(
        "practice_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "module_progress_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("module_progress.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="SUBMITTED"
        ),
        sa.Column(
            "evaluation_status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column(
            "media_upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_uploads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("feedback", postgresql.JSONB(), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "revision_group_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "revision_number", sa.SmallInteger(), nullable=False, server_default="1"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('RECORDED_SPEAKING','WRITING','VOCAB_QUIZ','VOCAB_REVIEW','PRONUNCIATION')",
            name="valid_submission_mode",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')",
            name="valid_submission_status",
        ),
        sa.CheckConstraint(
            "evaluation_status IN ('NOT_REQUIRED','PENDING','PROCESSING','COMPLETED','FAILED')",
            name="valid_submission_eval_status",
        ),
        sa.CheckConstraint(
            "revision_number BETWEEN 1 AND 4",
            name="valid_submission_revision_number",
        ),
    )
    op.create_index(
        "ix_practice_submissions_user_created",
        "practice_submissions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "uq_submission_revision_group",
        "practice_submissions",
        ["revision_group_id", "revision_number"],
        unique=True,
        postgresql_where=sa.text("revision_group_id IS NOT NULL"),
    )

    # 10. practice_sessions
    op.create_table(
        "practice_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("session_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "config", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "transcript", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("feedback", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "session_type IN ('LIVE_CONVERSATION','MOCK_INTERVIEW','INTERVIEW_PANEL')",
            name="valid_practice_session_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','ENDED','ABANDONED','ERROR')",
            name="valid_practice_session_status",
        ),
    )
    op.create_index(
        "ix_practice_sessions_user_started",
        "practice_sessions",
        ["user_id", "started_at", "session_type"],
    )

    # 11. user_vocabulary
    op.create_table(
        "user_vocabulary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "word_content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("word_key", sa.String(120), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="LEARNING"
        ),
        sa.Column(
            "mastery_level", sa.SmallInteger(), nullable=False, server_default="1"
        ),
        sa.Column("review_interval_days", sa.SmallInteger(), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "times_practiced", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("source_details", postgresql.JSONB(), nullable=True),
        sa.Column("learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id", "word_key", name="uq_user_vocabulary_word_key"
        ),
        sa.CheckConstraint(
            "status IN ('SUGGESTED','LEARNING','REVIEWING','MASTERED','DISMISSED')",
            name="valid_user_vocab_status",
        ),
        sa.CheckConstraint(
            "mastery_level BETWEEN 1 AND 5", name="valid_user_vocab_mastery"
        ),
    )
    op.create_index(
        "ix_user_vocabulary_due_review",
        "user_vocabulary",
        ["user_id", "next_review_at"],
    )

    # 12. activity_completions
    op.create_table(
        "activity_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "module_progress_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("module_progress.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_submissions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "source_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("local_practice_date", sa.Date(), nullable=False),
        sa.Column(
            "duration_seconds", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "module_progress_id",
            "content_item_id",
            name="uq_module_progress_content_completion",
        ),
        sa.UniqueConstraint(
            "source_submission_id", name="uq_activity_completion_submission"
        ),
        sa.UniqueConstraint(
            "source_session_id", name="uq_activity_completion_session"
        ),
        sa.CheckConstraint(
            "(source_submission_id IS NOT NULL AND source_session_id IS NULL) OR "
            "(source_submission_id IS NULL AND source_session_id IS NOT NULL)",
            name="exactly_one_completion_source",
        ),
    )
    op.create_index(
        "ix_activity_completions_user_date",
        "activity_completions",
        ["user_id", "local_practice_date"],
    )

    # 13. user_achievements
    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("achievement_key", sa.String(60), nullable=False),
        sa.Column(
            "context", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "achievement_key", name="uq_user_achievement_key"
        ),
    )

    # 14. ai_jobs (base columns prior to 20261101_job_execution)
    op.create_table(
        "ai_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column(
            "assessment_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "practice_submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_submissions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "practice_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="PENDING"
        ),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(60), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("rubric_version", sa.String(40), nullable=True),
        sa.Column("langsmith_run_id", sa.String(80), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_jobs_idempotency_key"),
        sa.CheckConstraint(
            "job_type IN ('TRANSCRIBE','ASSESSMENT','SPEAKING_FEEDBACK',"
            "'WRITING_FEEDBACK','VOCAB_CONTEXT','CONTENT_AUTHORING','SESSION_FEEDBACK')",
            name="valid_ai_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','RETRYABLE','FAILED')",
            name="valid_ai_job_status",
        ),
    )
    op.create_index(
        "ix_ai_jobs_status_created", "ai_jobs", ["status", "created_at"]
    )

    # 15. outbox_events (base columns prior to 20261101_outbox_delivery)
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ai_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_jobs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    for table in (
        "outbox_events",
        "ai_jobs",
        "user_achievements",
        "activity_completions",
        "user_vocabulary",
        "practice_sessions",
        "practice_submissions",
        "module_progress",
        "learning_plans",
        "assessment_responses",
        "assessment_attempts",
        "media_uploads",
        "content_items",
        "auth_sessions",
        "users",
    ):
        op.drop_table(table)

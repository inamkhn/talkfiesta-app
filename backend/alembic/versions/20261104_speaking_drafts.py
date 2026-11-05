"""Durable speaking draft keys and one active draft per assigned activity."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261104_speaking_drafts"
down_revision = "20261101_job_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "speaking_draft_requests",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_speaking_active_draft",
        "practice_submissions",
        ["module_progress_id", "content_item_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'DRAFT' AND mode = 'RECORDED_SPEAKING' AND module_progress_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_speaking_active_draft", table_name="practice_submissions")
    op.drop_table("speaking_draft_requests")

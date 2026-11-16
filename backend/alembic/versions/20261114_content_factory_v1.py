"""Add additive Content Factory V1 batch and review columns to ai_jobs and content_items.

Revision ID: 20261114_content_factory_v1
Revises: 20261106_vocab_writing_v4
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261114_content_factory_v1"
down_revision = "20261106_vocab_writing_v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_jobs",
        sa.Column(
            "parent_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_jobs.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column("generation_batch_key", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_jobs",
        sa.Column(
            "job_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column(
            "result_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column(
            "cancel_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_index(
        "ix_ai_jobs_batch_key", "ai_jobs", ["generation_batch_key"]
    )
    op.create_index(
        "ix_ai_jobs_parent_job_id", "ai_jobs", ["parent_job_id"]
    )

    op.add_column(
        "content_items",
        sa.Column("generation_item_key", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_content_items_generation_item_key",
        "content_items",
        ["generation_item_key"],
        unique=True,
        postgresql_where=sa.text("generation_item_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_content_items_generation_item_key", table_name="content_items"
    )
    op.drop_column("content_items", "review_notes")
    op.drop_column("content_items", "reviewed_at")
    op.drop_column("content_items", "generation_item_key")

    op.drop_index("ix_ai_jobs_parent_job_id", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_batch_key", table_name="ai_jobs")
    op.drop_column("ai_jobs", "cancel_requested_at")
    op.drop_column("ai_jobs", "result_summary")
    op.drop_column("ai_jobs", "job_context")
    op.drop_column("ai_jobs", "generation_batch_key")
    op.drop_column("ai_jobs", "parent_job_id")


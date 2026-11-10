"""Add edit_version and vocabulary/writing partial indexes on practice_submissions.

Revision ID: 20261106_vocab_writing_v4
Revises: 20261105_speaking_history
"""

import sqlalchemy as sa

from alembic import op

revision = "20261106_vocab_writing_v4"
down_revision = "20261105_speaking_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "practice_submissions",
        sa.Column(
            "edit_version", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.create_index(
        "uq_vocab_quiz_active_draft",
        "practice_submissions",
        ["module_progress_id", "content_item_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'DRAFT' AND mode = 'VOCAB_QUIZ' AND module_progress_id IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_writing_active_draft",
        "practice_submissions",
        ["module_progress_id", "content_item_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'DRAFT' AND mode = 'WRITING' AND revision_number = 1 AND module_progress_id IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_writing_portfolio",
        "practice_submissions",
        [
            "user_id",
            "mode",
            "revision_group_id",
            sa.text("submitted_at DESC NULLS LAST"),
        ],
        postgresql_where=sa.text(
            "mode = 'WRITING' AND revision_group_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_writing_portfolio", table_name="practice_submissions")
    op.drop_index("uq_writing_active_draft", table_name="practice_submissions")
    op.drop_index("uq_vocab_quiz_active_draft", table_name="practice_submissions")
    op.drop_column("practice_submissions", "edit_version")


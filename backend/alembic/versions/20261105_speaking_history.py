"""Indexes for owner-scoped Speaking keyset pagination."""

import sqlalchemy as sa

from alembic import op

revision = "20261105_speaking_history"
down_revision = "20261104_speaking_submit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, prefix in (
        ("ix_speaking_history", ["user_id"]),
        ("ix_speaking_history_status", ["user_id", "evaluation_status"]),
    ):
        op.create_index(
            name,
            "practice_submissions",
            [*prefix, sa.text("submitted_at DESC NULLS LAST"), sa.text("id DESC")],
            postgresql_where=sa.text("mode = 'RECORDED_SPEAKING'"),
        )


def downgrade() -> None:
    op.drop_index("ix_speaking_history_status", table_name="practice_submissions")
    op.drop_index("ix_speaking_history", table_name="practice_submissions")

"""Durable speaking acceptance receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261104_speaking_submit"
down_revision = "20261104_speaking_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "speaking_submit_requests",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("practice_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_upload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_speaking_submit_requests_submission_id",
        "speaking_submit_requests",
        ["submission_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_speaking_submit_requests_submission_id",
        table_name="speaking_submit_requests",
    )
    op.drop_table("speaking_submit_requests")

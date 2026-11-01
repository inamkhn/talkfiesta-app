"""Persist user-scoped assessment submission keys."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261101_submit_keys"
down_revision = "20261031_start_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_submit_requests",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column(
            "assessment_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("assessment_submit_requests")

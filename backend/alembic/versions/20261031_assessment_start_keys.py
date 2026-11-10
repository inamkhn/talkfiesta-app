"""Add durable start keys to an existing V4 database.

Revision ID: 20261031_start_keys
Revises: 20261030_initial_v4
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision = "20261031_start_keys"
down_revision = "20261030_initial_v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if not all(
            inspector.has_table(name)
            for name in ("users", "assessment_attempts")
        ):
            raise RuntimeError(
                "Initialize the V4 schema before applying the assessment start-key migration."
            )
    op.create_table(
        "assessment_start_requests",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
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
    op.drop_table("assessment_start_requests")

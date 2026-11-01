"""Persist job stages, execution leases and retry scheduling."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261101_job_execution"
down_revision = "20261101_outbox_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_jobs",
        sa.Column(
            "stage", sa.String(40), server_default="WAITING_FOR_WORKER", nullable=False
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    for name in ("lease_expires_at", "next_attempt_at"):
        op.add_column(
            "ai_jobs", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
        )
    op.add_column("ai_jobs", sa.Column("last_error_code", sa.String(60), nullable=True))


def downgrade() -> None:
    for name in (
        "last_error_code",
        "next_attempt_at",
        "lease_expires_at",
        "claim_token",
        "stage",
    ):
        op.drop_column("ai_jobs", name)

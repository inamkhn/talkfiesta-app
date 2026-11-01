"""Add durable outbox leases, backoff, and failure quarantine."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261101_outbox_delivery"
down_revision = "20261101_audio_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
    )
    for name in ("lease_expires_at", "next_attempt_at", "failed_at"):
        op.add_column(
            "outbox_events", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
        )
    op.add_column(
        "outbox_events", sa.Column("last_error_code", sa.String(60), nullable=True)
    )


def downgrade() -> None:
    for name in (
        "last_error_code",
        "failed_at",
        "next_attempt_at",
        "lease_expires_at",
        "claim_token",
    ):
        op.drop_column("outbox_events", name)

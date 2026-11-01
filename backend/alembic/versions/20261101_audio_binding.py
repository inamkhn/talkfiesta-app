"""Bind assessment audio uploads and persist signed upload expectations."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261101_audio_binding"
down_revision = "20261101_submit_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_uploads",
        sa.Column(
            "assessment_response_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        "media_uploads", sa.Column("expected_size_bytes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "media_uploads", sa.Column("checksum_sha256", sa.String(44), nullable=True)
    )
    op.add_column(
        "media_uploads",
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_media_assessment_response",
        "media_uploads",
        "assessment_responses",
        ["assessment_response_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_media_uploads_assessment_response_id",
        "media_uploads",
        ["assessment_response_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_uploads_assessment_response_id", table_name="media_uploads")
    op.drop_constraint(
        "fk_media_assessment_response", "media_uploads", type_="foreignkey"
    )
    for name in (
        "upload_expires_at",
        "checksum_sha256",
        "expected_size_bytes",
        "assessment_response_id",
    ):
        op.drop_column("media_uploads", name)

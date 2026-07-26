"""add unique active submission index on writing_submissions

Revision ID: c4e2b8d95f37
Revises: b3d1a9c47e21
Create Date: 2026-07-25 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e2b8d95f37'
down_revision: Union[str, Sequence[str], None] = 'b3d1a9c47e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Defensively resolve pre-existing duplicates: keep the most recent
    # active submission per (user_id, prompt_id), mark the rest FAILED.
    op.execute(
        """
        UPDATE writing_submissions ws
        SET status = 'FAILED'
        WHERE ws.status IN ('PENDING', 'PROCESSING')
          AND ws.id NOT IN (
              SELECT DISTINCT ON (user_id, prompt_id) id
              FROM writing_submissions
              WHERE status IN ('PENDING', 'PROCESSING')
              ORDER BY user_id, prompt_id, submitted_at DESC
          )
        """
    )
    op.create_index(
        'uq_writing_submissions_active',
        'writing_submissions',
        ['user_id', 'prompt_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'PROCESSING')"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_writing_submissions_active', table_name='writing_submissions')

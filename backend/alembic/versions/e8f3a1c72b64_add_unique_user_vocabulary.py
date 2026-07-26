"""add unique constraint on user_vocabulary (user_id, word_id)

Revision ID: e8f3a1c72b64
Revises: c4e2b8d95f37
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8f3a1c72b64"
down_revision: Union[str, None] = "c4e2b8d95f37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dedupe: for each (user_id, word_id) keep the most-progressed record
    # (highest mastery, then most reviews, then earliest learned), drop the rest.
    op.execute(
        """
        DELETE FROM user_vocabulary
        WHERE id NOT IN (
            SELECT DISTINCT ON (user_id, word_id) id
            FROM user_vocabulary
            ORDER BY user_id, word_id,
                     mastery_level DESC,
                     times_reviewed DESC,
                     learned_at ASC
        )
        """
    )
    op.create_unique_constraint(
        "uq_user_vocabulary_user_word",
        "user_vocabulary",
        ["user_id", "word_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_vocabulary_user_word", "user_vocabulary", type_="unique"
    )

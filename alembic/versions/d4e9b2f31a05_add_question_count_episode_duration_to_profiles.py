"""add_question_count_episode_duration_to_profiles

Revision ID: d4e9b2f31a05
Revises: c3f8a1e29d74
Create Date: 2026-04-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9b2f31a05"
down_revision: str | Sequence[str] | None = "c3f8a1e29d74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add question_count and episode_duration_min columns to profiles table."""
    op.add_column(
        "profiles",
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "profiles",
        sa.Column("episode_duration_min", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    """Remove question_count and episode_duration_min columns from profiles table."""
    op.drop_column("profiles", "episode_duration_min")
    op.drop_column("profiles", "question_count")

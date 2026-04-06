"""add learning_strategy to profiles

Revision ID: c3f8a1e29d74
Revises: b3c4d5e6f7a8
Create Date: 2026-04-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a1e29d74"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add learning_strategy column to profiles table."""
    op.add_column(
        "profiles",
        sa.Column(
            "learning_strategy",
            postgresql.JSONB(),
            nullable=False,
            server_default='["reading","writing","listening","vocab"]',
        ),
    )


def downgrade() -> None:
    """Remove learning_strategy column from profiles table."""
    op.drop_column("profiles", "learning_strategy")

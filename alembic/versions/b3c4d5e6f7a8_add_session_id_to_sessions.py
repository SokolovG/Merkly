"""add session_id to sessions

Revision ID: b3c4d5e6f7a8
Revises: 67719c0c10a4
Create Date: 2026-04-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "67719c0c10a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add session_id column to sessions table."""
    op.add_column("sessions", sa.Column("session_id", sa.Text(), nullable=False, server_default=""))
    op.create_unique_constraint("uq_sessions_session_id", "sessions", ["session_id"])
    # Remove the server_default after adding (only needed for the ADD COLUMN on existing rows)
    op.alter_column("sessions", "session_id", server_default=None)


def downgrade() -> None:
    """Remove session_id column from sessions table."""
    op.drop_constraint("uq_sessions_session_id", "sessions", type_="unique")
    op.drop_column("sessions", "session_id")

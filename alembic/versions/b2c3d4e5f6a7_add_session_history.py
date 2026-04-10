"""add session_history

Revision ID: b2c3d4e5f6a7
Revises: 2361ec75771d
Create Date: 2026-04-11

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "2361ec75771d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_history",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_history_user", "session_history", ["user_id"], unique=False)
    op.create_index(
        "ix_session_history_user_url", "session_history", ["user_id", "url"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_session_history_user_url", table_name="session_history")
    op.drop_index("ix_session_history_user", table_name="session_history")
    op.drop_table("session_history")

"""added_user_id

Revision ID: 2c133629059c
Revises: 619744d0ec7b
Create Date: 2026-04-12 08:54:14.304266

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c133629059c"
down_revision: str | Sequence[str] | None = "619744d0ec7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILD_TABLES = ["sessions", "vocab_history", "vocab_pool", "session_history"]
_FK_NAMES = {
    "sessions": "sessions_user_id_fkey",
    "vocab_history": "vocab_history_user_id_fkey",
    "vocab_pool": "vocab_pool_user_id_fkey",
    "session_history": "session_history_user_id_fkey",
}
_COMPOSITE_INDEXES = {
    "vocab_history": "ix_vocab_history_user_lang",
    "vocab_pool": "ix_vocab_pool_user_lang",
    "session_history": "ix_session_history_user_url",
}


def upgrade() -> None:
    """Migrate all integer PKs to UUID; cascade FK user_id columns in child tables."""

    # ── Step 1: Add new_id to profiles (auto-filled by server_default) ──────
    op.add_column(
        "profiles",
        sa.Column(
            "new_id",
            sa.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )

    # ── Step 2: Add new_user_id to each child table (nullable, filled via JOIN) ─
    for table in _CHILD_TABLES:
        op.add_column(table, sa.Column("new_user_id", sa.UUID(as_uuid=True), nullable=True))

    # ── Step 3: Populate new_user_id using the mapping profiles.id → profiles.new_id ─
    for table in _CHILD_TABLES:
        op.execute(
            f"UPDATE {table} SET new_user_id = p.new_id "  # noqa: S608
            f"FROM profiles p WHERE {table}.user_id = p.id"
        )

    # ── Step 4: Drop FK constraints on child tables ──────────────────────────
    for table, fk in _FK_NAMES.items():
        op.drop_constraint(fk, table, type_="foreignkey")

    # ── Step 5: Drop composite indexes (depend on user_id column) ────────────
    for table, idx in _COMPOSITE_INDEXES.items():
        op.drop_index(idx, table_name=table)

    # ── Step 6: Swap profiles.id: drop integer PK, rename new_id → id ───────
    op.drop_constraint("profiles_pkey", "profiles", type_="primary")
    op.drop_column("profiles", "id")
    op.alter_column("profiles", "new_id", new_column_name="id", nullable=False)
    op.create_primary_key("profiles_pkey", "profiles", ["id"])
    op.alter_column("profiles", "id", server_default=sa.text("gen_random_uuid()"))

    # ── Step 7: Swap child table user_id columns ─────────────────────────────
    for table in _CHILD_TABLES:
        op.drop_column(table, "user_id")
        op.alter_column(table, "new_user_id", new_column_name="user_id", nullable=False)

    # ── Step 8: Swap child table own PKs (integer → UUID) ───────────────────
    for table in _CHILD_TABLES:
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.drop_column(table, "id")
        op.add_column(
            table,
            sa.Column(
                "id",
                sa.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
        )
        op.create_primary_key(f"{table}_pkey", table, ["id"])

    # ── Step 9: Re-add FK constraints ────────────────────────────────────────
    for table, fk in _FK_NAMES.items():
        op.create_foreign_key(fk, table, "profiles", ["user_id"], ["id"], ondelete="CASCADE")

    # ── Step 10: Recreate indexes ─────────────────────────────────────────────
    op.create_index("ix_vocab_history_user_id", "vocab_history", ["user_id"])
    op.create_index("ix_vocab_pool_user_id", "vocab_pool", ["user_id"])
    op.create_index("ix_session_history_user_id", "session_history", ["user_id"])

    op.create_index("ix_vocab_history_user_lang", "vocab_history", ["user_id", "target_lang"])
    op.create_index("ix_vocab_pool_user_lang", "vocab_pool", ["user_id", "target_lang"])
    op.create_index("ix_session_history_user_url", "session_history", ["user_id", "url"])


def downgrade() -> None:
    """UUID → INTEGER is not reversible without data loss. Manual intervention required."""
    raise NotImplementedError(
        "Downgrade from UUID PKs to integer PKs requires manual data migration."
    )

import uuid

from sqlalchemy import UUID, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.infrastructure.database.models.base import Base


class WritingThemeHistoryModel(Base):
    """Tracks which writing themes each user has already been shown."""

    __tablename__ = "writing_theme_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("writing_theme_pool.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "theme_id", name="uq_writing_theme_history_user_theme"),
        Index("ix_writing_theme_history_user", "user_id"),
    )

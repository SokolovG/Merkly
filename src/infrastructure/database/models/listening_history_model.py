import uuid

from sqlalchemy import UUID, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class ListeningHistoryModel(Base):
    __tablename__ = "listening_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    episode_url: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_listening_history_user_lang", "user_id", "target_lang"),
        UniqueConstraint("user_id", "episode_url", name="uq_listening_history_user_episode"),
    )

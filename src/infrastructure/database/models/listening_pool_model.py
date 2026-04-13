import uuid

from sqlalchemy import UUID, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class ListeningPoolModel(Base):
    __tablename__ = "listening_pool"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    episode_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    level: Mapped[str] = mapped_column(Text, nullable=False, server_default="B1")

    __table_args__ = (Index("ix_listening_pool_user_lang", "user_id", "target_lang"),)

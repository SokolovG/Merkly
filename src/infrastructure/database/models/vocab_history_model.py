import uuid

from sqlalchemy import UUID, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class VocabHistoryModel(Base):
    __tablename__ = "vocab_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    word: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_vocab_history_user_lang", "user_id", "target_lang"),)

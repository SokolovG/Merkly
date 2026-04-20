import uuid

from sqlalchemy import UUID, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.infrastructure.database.models.base import Base


class SessionHistoryModel(Base):
    __tablename__ = "session_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)  # "reading" | "listening"

    __table_args__ = (Index("ix_session_history_user_url", "user_id", "url"),)

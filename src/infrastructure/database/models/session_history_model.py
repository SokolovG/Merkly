from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class SessionHistoryModel(Base):
    __tablename__ = "session_history"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)  # "reading" | "listening"

    __table_args__ = (Index("ix_session_history_user_url", "user_id", "url"),)

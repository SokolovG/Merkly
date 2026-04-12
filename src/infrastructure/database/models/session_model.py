import uuid

from sqlalchemy import UUID, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    article_url: Mapped[str] = mapped_column(Text, nullable=False)
    article_title: Mapped[str] = mapped_column(Text, nullable=False)
    article_text: Mapped[str] = mapped_column(Text, nullable=False)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    user_answers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    feedback: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cards_created: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

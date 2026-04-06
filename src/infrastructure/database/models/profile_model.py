from sqlalchemy import BigInteger, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class ProfileModel(Base):
    __tablename__ = "profiles"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    native_lang: Mapped[str] = mapped_column(Text, nullable=False)
    session_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    target_lang: Mapped[str] = mapped_column(Text, nullable=False, server_default="de")
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    reminder_time: Mapped[str] = mapped_column(Text, nullable=False, server_default="11:00")
    utc_offset: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    vocab_card_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    decks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    active_deck_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    vocab_scheduler_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    vocab_scheduler_time: Mapped[str] = mapped_column(Text, nullable=False, server_default="09:00")
    vocab_scheduler_deck_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    learning_strategy: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default='["reading","writing","listening","vocab"]'
    )

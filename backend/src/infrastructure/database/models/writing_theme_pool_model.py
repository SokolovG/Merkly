from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.infrastructure.database.models.base import Base


class WritingThemePoolModel(Base):
    """Global catalog of exam-style writing topics, keyed by language."""

    __tablename__ = "writing_theme_pool"

    theme: Mapped[str] = mapped_column(Text, nullable=False)
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_writing_theme_pool_lang_level", "target_lang", "level"),)

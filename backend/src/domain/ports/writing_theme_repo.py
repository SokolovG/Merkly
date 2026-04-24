from abc import ABC, abstractmethod
from uuid import UUID

from backend.src.domain.constants import WRITING_THEME_CHOOSE_COUNT
from backend.src.domain.entities import WritingTheme


class IWritingThemeRepository(ABC):
    @abstractmethod
    async def get_unseen(
        self,
        user_id: UUID,
        target_lang: str,
        level: str | None,
        limit: int = WRITING_THEME_CHOOSE_COUNT,
    ) -> list[WritingTheme]:
        """Return themes the user has not yet used.

        If fewer than ``limit`` unseen themes exist, the history for this user
        is cleared and all themes become available again (cycling pool).
        """
        ...

    @abstractmethod
    async def mark_seen(self, user_id: UUID, theme_id: UUID) -> None:
        """Record that the user was shown (and used) this theme."""
        ...

    @abstractmethod
    async def get_by_id(self, theme_id: UUID) -> WritingTheme | None: ...

    @abstractmethod
    async def count_unseen(self, user_id: UUID, target_lang: str, level: str | None) -> int:
        """Return number of themes not yet seen by this user for the given lang/level."""
        ...

    @abstractmethod
    async def seed(self, themes: list[WritingTheme]) -> None:
        """Insert themes that do not already exist (idempotent upsert by text+lang)."""
        ...

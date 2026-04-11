from abc import ABC, abstractmethod

from src.domain.entities import PooledVocabCard, VocabCard


class IVocabPoolRepository(ABC):
    @abstractmethod
    async def pool_count(self, user_id: int, target_lang: str) -> int: ...

    @abstractmethod
    async def get_pool_cards(
        self, user_id: int, target_lang: str, count: int
    ) -> list[PooledVocabCard]: ...

    @abstractmethod
    async def add_to_pool(self, user_id: int, cards: list[VocabCard], target_lang: str) -> None:
        """Insert cards that are NOT already in vocab_history for this user+lang."""
        ...

    @abstractmethod
    async def mark_shown(self, user_id: int, card_ids: list[int]) -> None:
        """Delete cards from vocab_pool by id, insert words into vocab_history."""
        ...

    @abstractmethod
    async def get_history_words(
        self, user_id: int, target_lang: str, limit: int, oldest_first: bool = False
    ) -> list[str]:
        """Return shown words ordered by shown_at.
        oldest_first=True for /repeat (spaced repetition);
        oldest_first=False (default) for soft LLM exclusion hint (newest first)."""
        ...

    @abstractmethod
    async def clear_pool(self, user_id: int, target_lang: str) -> int:
        """Delete all pending cards from vocab_pool for this user+lang.
        Returns the number of cards deleted."""
        ...

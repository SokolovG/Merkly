from abc import ABC, abstractmethod

from src.domain.entities import VocabCard


class ICardGateway(ABC):
    @abstractmethod
    async def create_card(self, card: VocabCard, deck_id: str | None = None) -> str | None:
        """Create card. Returns backend ID on success, None on failure."""

    @abstractmethod
    async def delete_card(self, card_id: str) -> bool: ...

    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def create_deck(self, name: str) -> str:
        """Create a named deck. Returns backend_id (name for Anki, UUID for Mochi)."""

    @abstractmethod
    async def list_decks(self) -> list[tuple[str, str]]:
        """List available decks. Returns list of (display_name, backend_id)."""

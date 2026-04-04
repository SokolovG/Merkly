from typing import Protocol

from src.domain.entities import VocabCard


class ICardGateway(Protocol):
    async def create_card(self, card: VocabCard, deck_id: str | None = None) -> str | None:
        """Create card. Returns backend ID on success, None on failure."""

    async def delete_card(self, card_id: str) -> bool: ...
    async def is_available(self) -> bool: ...

    async def create_deck(self, name: str) -> str:
        """Create a named deck. Returns backend_id (name for Anki, UUID for Mochi)."""

    async def list_decks(self) -> list[tuple[str, str]]:
        """List available decks. Returns list of (display_name, backend_id)."""
